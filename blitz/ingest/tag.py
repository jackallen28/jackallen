"""Attach each extracted question to study design dot points and a question type.

Two taggers:

* `KeywordTagger` — offline, no API key, no cost. Scores a question against the
  vocabulary of each dot point. Good enough to be useful, wrong often enough
  that you'll want to spot-check it.
* `ClaudeTagger` — one pass over the corpus at ingest time, batching questions
  into a single call per chunk. This is the only place the tool talks to a
  model; once the index is built, generating sheets is offline and instant.

Both return `TagResult`s, so the pipeline doesn't care which one ran.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from ..studydesign import StudyDesign

_TOKEN = re.compile(r"[a-z][a-z'-]{2,}")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
    "was", "were", "not", "but", "its", "their", "such", "including", "used",
    "use", "using", "both", "any", "may", "can", "will", "each", "other",
    "between", "within", "into", "when", "which", "these", "those", "than",
    "student", "students", "following", "shown", "figure", "diagram", "above",
    "below", "question", "questions", "marks", "mark", "answer", "give",
    # Number words and exam boilerplate. These are rare *among dot points*, so
    # IDF rates them highly, but they carry no topic at all — "one" (from "one
    # dimension") was enough to file "Which one of the following is closest?"
    # under conservation of momentum.
    "one", "two", "three", "four", "first", "second", "third", "next",
    "closest", "best", "correct", "true", "false", "most", "least", "some",
    "given", "shows", "show", "describes", "describe", "consider", "considered",
    "turn", "ready", "chapter", "you", "your", "they",
    "only", "also", "then", "there", "here", "what", "how", "why", "where",
}


@dataclass
class TagResult:
    kk_ids: list[str] = field(default_factory=list)
    question_type: str | None = None
    difficulty: int | None = None
    confidence: float = 0.0
    rejected: bool = False          # not actually a question
    reason: str = ""


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOP}


class KeywordTagger:
    """Offline tagger: IDF-weighted term overlap against each dot point.

    Plain overlap does not work here. Study design dot points share a lot of
    vocabulary — "investigate", "apply", "theoretically", "analyse" appear in
    dozens of them, and "speed" appears both in kinematics and in "all
    electromagnetic waves travel at the same speed, c". Matching on those put
    projectile questions under special relativity.

    So terms are weighted by how rare they are across the dot points: a term in
    one dot point is strong evidence, a term in thirty is noise. A question is
    only tagged when it matches something genuinely distinctive, and is left
    untagged otherwise — a question filed under the wrong dot point is worse
    than one that is missing, because it silently corrupts every sheet built
    from that dot point.
    """

    # Minimum share of the best possible score before a match is believed.
    THRESHOLD = 0.30
    # A match must include at least one term this distinctive (idf), or it is
    # just common vocabulary lining up.
    DISTINCTIVE_IDF = 1.15
    # One shared word is never enough on its own, however rare it looks. A real
    # topic match brings its whole vocabulary with it: a transformer question
    # says "transformer", "turns", "primary" and "secondary", not just one of
    # them. A single hit is a coincidence.
    MIN_SHARED_TERMS = 2
    # Very short questions ("Which one is closest?") carry no topic, and belong
    # to the stem or figure above them rather than to any dot point.
    MIN_QUESTION_TERMS = 4

    def __init__(self, design: StudyDesign, threshold: float | None = None):
        self.design = design
        self.threshold = self.THRESHOLD if threshold is None else threshold
        self._vocab = {
            kk.id: _tokens(f"{kk.text} {kk.label or ''}")
            for kk in design.all_key_knowledge()
        }
        self._idf = _idf(list(self._vocab.values()))
        self._type_cues = _type_cues(design)

    def _score(self, kk_id: str, toks: set[str]) -> tuple[float, float]:
        vocab = self._vocab.get(kk_id) or set()
        shared = toks & vocab
        if len(shared) < self.MIN_SHARED_TERMS:
            return 0.0, 0.0
        earned = sum(self._idf.get(t, 0.0) for t in shared)
        available = sum(self._idf.get(t, 0.0) for t in vocab) or 1.0
        best_term = max(self._idf.get(t, 0.0) for t in shared)
        # Normalise by what this dot point could possibly award, so a long dot
        # point isn't automatically the best match for everything.
        return earned / (available ** 0.55), best_term

    def tag(self, text: str, options: list[str] | None = None,
            marks: int | None = None) -> TagResult:
        haystack = " ".join([text or "", *(options or [])])
        toks = _tokens(haystack)
        if not toks:
            return TagResult(rejected=True, reason="no usable text")
        if len(toks) < self.MIN_QUESTION_TERMS:
            return TagResult(
                question_type=self.guess_type(haystack, options, marks),
                difficulty=_guess_difficulty(haystack, marks),
                rejected=True,
                reason="too little content to place",
            )

        scored = []
        for kk_id in self._vocab:
            score, best_term = self._score(kk_id, toks)
            if score > 0:
                scored.append((score, best_term, kk_id))
        scored.sort(reverse=True)

        keep = [
            (score, kk_id) for score, best_term, kk_id in scored[:3]
            if score >= self.threshold and best_term >= self.DISTINCTIVE_IDF
        ]
        question_type = self.guess_type(haystack, options, marks)
        if not keep:
            return TagResult(
                question_type=question_type,
                difficulty=_guess_difficulty(haystack, marks),
                rejected=True,
                reason="no dot point matched distinctively",
            )

        # Drop weak runners-up: a second dot point only rides along if it is
        # close to the best one.
        best = keep[0][0]
        kk_ids = [kk for score, kk in keep if score >= best * 0.7]
        return TagResult(
            kk_ids=kk_ids,
            question_type=question_type,
            difficulty=_guess_difficulty(haystack, marks),
            confidence=min(best, 1.0),
        )

    def guess_type(self, text: str, options: list[str] | None,
                   marks: int | None) -> str | None:
        if options:
            mc = next((qt.id for qt in self.design.question_types
                       if qt.id.endswith("-mc")), None)
            if mc:
                return mc
        lowered = text.lower()
        best, best_hits = None, 0
        for qt_id, cues in self._type_cues.items():
            hits = sum(1 for c in cues if c in lowered)
            if hits > best_hits:
                best, best_hits = qt_id, hits
        if best:
            return best
        if marks and marks >= 6:
            heavy = [qt for qt in self.design.question_types
                     if qt.typical_marks and max(qt.typical_marks) >= 6]
            if heavy:
                return heavy[0].id
        types = self.design.question_types
        return types[1].id if len(types) > 1 else (types[0].id if types else None)


def _idf(vocabs: list[set[str]]) -> dict[str, float]:
    """Inverse document frequency of every term across the dot points."""
    import math

    n = max(len(vocabs), 1)
    df: dict[str, int] = {}
    for vocab in vocabs:
        for term in vocab:
            df[term] = df.get(term, 0) + 1
    return {term: math.log(n / count) for term, count in df.items()}


def _type_cues(design: StudyDesign) -> dict[str, list[str]]:
    """Cue words per question type, derived from the study design where possible."""
    generic = {
        "mc": [],
        "calculation": ["calculate", "determine the value", "how far", "how fast",
                        "find the", "magnitude of", "in m s", "in joules"],
        "multi-step": ["hence", "then calculate", "using your answer"],
        "explanation": ["explain why", "explain how", "account for", "why does",
                        "explain the"],
        "graph": ["graph", "gradient", "area under", "axes", "plot", "sketch a graph"],
        "diagram": ["diagram", "figure", "shown in the", "field lines", "circuit",
                    "free-body", "ray"],
        "experimental": ["uncertainty", "systematic error", "random error",
                         "repeatab", "validity", "independent variable",
                         "controlled variable"],
        "derivation": ["show that", "derive", "prove that"],
        "short": ["state", "identify", "outline", "define", "list", "name"],
        "case-study": ["case study", "refer to the", "with reference to the business",
                       "in the above", "scenario"],
        "extended": ["discuss", "evaluate", "analyse", "justify", "to what extent",
                     "propose and justify"],
        "theory-application": ["maslow", "locke and latham", "lawrence and nohria",
                               "force field", "lewin", "senge", "porter",
                               "learning organisation"],
        "definition": ["define", "what is meant by", "key term"],
    }
    cues: dict[str, list[str]] = {}
    for qt in design.question_types:
        suffix = qt.id.split("-", 1)[-1]
        cues[qt.id] = generic.get(suffix, [])
    return cues


def _guess_difficulty(text: str, marks: int | None) -> int:
    score = 3
    if marks:
        score = 1 if marks <= 1 else 2 if marks <= 2 else 3 if marks <= 4 else 4 if marks <= 6 else 5
    lowered = text.lower()
    if any(w in lowered for w in ("evaluate", "to what extent", "justify", "hence")):
        score = min(5, score + 1)
    if any(w in lowered for w in ("state", "define", "name", "list")):
        score = max(1, score - 1)
    return score


class ClaudeTagger:
    """Tag with Claude. Used once at ingest; the generated index is then offline.

    Needs `pip install vce-blitz[tag]` and ANTHROPIC_API_KEY in the environment.
    Falls back to the keyword tagger for anything the model declines to place.
    """

    MODEL = "claude-sonnet-5"

    def __init__(self, design: StudyDesign, model: str | None = None,
                 batch_size: int = 20):
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise RuntimeError(
                "ClaudeTagger needs the 'tag' extra: pip install -e '.[tag]'"
            ) from exc
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic()
        self.design = design
        self.model = model or self.MODEL
        self.batch_size = batch_size
        self.fallback = KeywordTagger(design)

    def _catalogue(self) -> str:
        lines = []
        for area in self.design.all_areas():
            lines.append(f"## {area.id} — {area.display}")
            for kk in area.key_knowledge:
                lines.append(f"- {kk.id}: {kk.text}")
        lines.append("\n## question types")
        for qt in self.design.question_types:
            lines.append(f"- {qt.id}: {qt.label} — {qt.description}")
        return "\n".join(lines)

    def tag_batch(self, items: list[dict]) -> list[TagResult]:
        prompt = (
            "You are indexing questions from a VCE exam preparation book against "
            "the official VCAA study design.\n\n"
            f"STUDY DESIGN — {self.design.subject_name}\n{self._catalogue()}\n\n"
            "For each numbered item below, decide:\n"
            "  kk_ids: 1-3 key knowledge ids the question genuinely assesses, best first. "
            "Use [] if it assesses none of them.\n"
            "  question_type: one question type id from the list.\n"
            "  difficulty: 1 (recall) to 5 (hardest exam standard).\n"
            "  is_question: false if this is prose, a heading, a worked example, "
            "an answer key or page furniture rather than a question a student answers.\n\n"
            "Anchor strictly to the dot points. Do not invent ids. Return ONLY a JSON "
            'array: [{"i":0,"kk_ids":[...],"question_type":"...","difficulty":3,'
            '"is_question":true}, ...]\n\nITEMS\n'
            + "\n\n".join(
                f"[{i}] {it['text'][:1200]}"
                + (f"\nOPTIONS: {' | '.join(it['options'])}" if it.get("options") else "")
                for i, it in enumerate(items)
            )
        )
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        return self._parse(raw, items)

    def _parse(self, raw: str, items: list[dict]) -> list[TagResult]:
        valid_kk = {kk.id for kk in self.design.all_key_knowledge()}
        valid_qt = {qt.id for qt in self.design.question_types}
        results = [TagResult(rejected=True, reason="not returned by model")
                   for _ in items]
        try:
            start, end = raw.index("["), raw.rindex("]") + 1
            parsed = json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            return [self.fallback.tag(it["text"], it.get("options"), it.get("marks"))
                    for it in items]

        for entry in parsed:
            i = entry.get("i")
            if not isinstance(i, int) or not 0 <= i < len(items):
                continue
            if entry.get("is_question") is False:
                results[i] = TagResult(rejected=True, reason="model: not a question")
                continue
            kk_ids = [k for k in entry.get("kk_ids", []) if k in valid_kk]
            qt = entry.get("question_type")
            results[i] = TagResult(
                kk_ids=kk_ids[:3],
                question_type=qt if qt in valid_qt else None,
                difficulty=entry.get("difficulty"),
                confidence=0.9 if kk_ids else 0.0,
                rejected=not kk_ids,
                reason="" if kk_ids else "model matched no dot point",
            )
        # Anything the model dropped still gets a keyword attempt.
        for i, r in enumerate(results):
            if r.rejected and r.reason == "not returned by model":
                results[i] = self.fallback.tag(
                    items[i]["text"], items[i].get("options"), items[i].get("marks"))
        return results

    def tag_all(self, items: list[dict]) -> list[TagResult]:
        out: list[TagResult] = []
        for i in range(0, len(items), self.batch_size):
            chunk = items[i:i + self.batch_size]
            try:
                out.extend(self.tag_batch(chunk))
            except Exception as exc:
                print(f"  tagging batch {i // self.batch_size} failed ({exc}); "
                      "falling back to keywords")
                out.extend(
                    self.fallback.tag(it["text"], it.get("options"), it.get("marks"))
                    for it in chunk
                )
        return out


def get_tagger(design: StudyDesign, prefer_model: bool = True):
    """Claude if it's available and configured, keywords otherwise."""
    if prefer_model:
        try:
            return ClaudeTagger(design)
        except RuntimeError as exc:
            print(f"  (using keyword tagger: {exc})")
    return KeywordTagger(design)
