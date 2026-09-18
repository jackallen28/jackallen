"""Per-subject concept lexicons: the vocabulary questions actually use.

A study design says "investigate and apply Newton's three laws of motion". A
question says "a speeding motorbike travels past a stationary police car".
Nothing useful overlaps, and what does overlap misleads — "motion" is also in
"motion approaching the speed of light", so kinematics questions land under
special relativity.

A lexicon supplies the missing half for one subject: for each dot point, the
terms a question about it is likely to contain. It is hand-written subject
knowledge, kept beside the study design in
``blitz/studydesign/data/<subject>-lexicon.yaml``, and it is optional — without
one the tagger falls back on IDF-weighted overlap alone.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ..config import STUDY_DESIGN_DIR


@dataclass(frozen=True)
class Concept:
    """The trigger vocabulary for one dot point."""

    kk_id: str
    triggers: tuple[str, ...] = ()
    requires: tuple[str, ...] = ()
    avoid: tuple[str, ...] = ()
    # Tie-break between concepts that both fire. Named phenomena ("de Broglie",
    # "muon") should beat the generic apparatus they happen to use ("electron
    # gun"), and the investigation-skills dot points should only win when no
    # content dot point fires at all.
    weight: float = 1.0

    def vetoed(self, haystack: str) -> bool:
        """True when this dot point is ruled out for this question.

        Applied wherever a dot point is proposed, not just by the lexicon — the
        word-overlap fallback made exactly this mistake, filing a speed-time
        graph under "motion approaching the speed of light" after the lexicon
        had already ruled it out.
        """
        if self.avoid and any(_present(a, haystack) for a in self.avoid):
            return True
        if self.requires and not any(_present(r, haystack) for r in self.requires):
            return True
        return False

    def matches(self, haystack: str) -> float:
        """How strongly this dot point is indicated. 0.0 means no.

        A multi-word phrase is much better evidence than a bare word — "work
        function" says photoelectric effect, while "work" on its own says
        almost nothing — so phrases score higher and short words need a token
        boundary to count at all.
        """
        if self.vetoed(haystack):
            return 0.0

        hits = [t for t in self.triggers if _present(t, haystack)]
        # One piece of evidence counts once. Listing "key performance
        # indicator" and "key performance indicators" is the natural way to
        # write a lexicon, and both match the plural — which doubled the
        # score and let a dot point with a long trigger list beat a named
        # theory that fired precisely. A trigger contained in a longer trigger
        # that also matched is the same hit, so only the longest counts.
        hits = [t for t in hits
                if not any(t != o and t in o for o in hits)]
        score = 0.0
        for trigger in hits:
            words = trigger.count(" ") + 1
            score += 1.0 if words == 1 else 1.0 + 0.8 * (words - 1)
        return score * self.weight


@dataclass
class Lexicon:
    subject_id: str
    concepts: dict[str, Concept] = field(default_factory=dict)

    def score_all(self, haystack: str) -> dict[str, float]:
        low = haystack.lower()
        out: dict[str, float] = {}
        for kk_id, concept in self.concepts.items():
            hit = concept.matches(low)
            if hit > 0:
                out[kk_id] = hit
        return out

    def vetoes(self, kk_id: str, haystack: str) -> bool:
        concept = self.concepts.get(kk_id)
        return bool(concept and concept.vetoed(haystack.lower()))

    def __bool__(self) -> bool:
        return bool(self.concepts)


@functools.lru_cache(maxsize=None)
def _boundary(term: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")


@functools.lru_cache(maxsize=None)
def _prefix(stem: str) -> re.Pattern:
    """A word starting with this stem: "motivat*" for motivate/motivation."""
    return re.compile(rf"(?<![a-z0-9]){re.escape(stem)}")


def _present(term: str, haystack: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
    if term.endswith("*"):
        # A trailing star is the only wildcard, and it earns its keep: a word
        # family ("motivate", "motivation", "motivating", "motivated") is four
        # entries without it, and writing the bare stem instead does not work
        # — a single word is matched on both boundaries, so "motivat" matches
        # nothing at all. That silently killed several dot points here before
        # a held-out probe caught it.
        stem = term[:-1]
        return bool(stem) and bool(_prefix(stem).search(haystack))
    if " " in term or "-" in term or "/" in term or not term.isalnum():
        # Phrases and symbols are matched as substrings: the surrounding
        # punctuation in a question is unpredictable.
        return term in haystack
    return bool(_boundary(term).search(haystack))


def _parse(raw: dict) -> Lexicon:
    concepts = {}
    for kk_id, entry in (raw.get("dot_points") or {}).items():
        entry = entry or {}
        concepts[kk_id] = Concept(
            kk_id=kk_id,
            triggers=tuple(t.lower() for t in entry.get("triggers", [])),
            requires=tuple(t.lower() for t in entry.get("requires", [])),
            avoid=tuple(t.lower() for t in entry.get("avoid", [])),
            weight=float(entry.get("weight", 1.0)),
        )
    return Lexicon(subject_id=raw.get("subject_id", ""), concepts=concepts)


@functools.lru_cache(maxsize=None)
def load_lexicon(subject_id: str, directory: Path | None = None) -> Lexicon:
    """The lexicon for a subject, or an empty one if it has none."""
    if directory is not None:
        candidates = [Path(directory) / f"{subject_id}-lexicon.yaml"]
    else:
        from ..studydesign.loader import design_dirs

        candidates = [d / f"{subject_id}-lexicon.yaml" for d in design_dirs()]
    path = next((c for c in candidates if c.exists()), None)
    if path is None:
        return Lexicon(subject_id=subject_id)
    with path.open(encoding="utf-8") as fh:
        return _parse(yaml.safe_load(fh) or {})


def truncated_terms(lexicon: Lexicon) -> list[tuple[str, str]]:
    """Terms that look like a stem someone forgot to put a `*` on.

    Writing `motivat` where `motivat*` was meant is silent and expensive: a
    single word is matched on both boundaries, so `motivat` matches neither
    "motivation" nor "motivate" nor anything else, and in a `requires` list it
    switches the whole dot point off for good. Nothing complains; the dot point
    simply stops being used.

    The signature is precise enough to test on: a one-word term that never
    occurs as a whole word anywhere in the lexicon, but does occur as the start
    of a longer word that does. Real guard words like "objective" survive,
    because the lexicon uses them as words somewhere.
    """
    # Every word the lexicon uses, and which entries it came from.
    sources: dict[str, set[str]] = {}
    for c in lexicon.concepts.values():
        for term in (*c.triggers, *c.requires, *c.avoid):
            for word in re.findall(r"[a-z0-9]+", term):
                sources.setdefault(word, set()).add(term)

    out = []
    for kk_id, c in lexicon.concepts.items():
        for term in (*c.triggers, *c.requires, *c.avoid):
            if term.endswith("*") or not term.isalnum():
                continue
            if sources.get(term, set()) - {term}:
                continue        # some other entry uses it as a word, so it is one
            longer = [w for w in sources if w != term and w.startswith(term)]
            # "bonus" beside "bonuses" is a deliberate pair, not a stem: both
            # forms are listed on purpose and both match what they should.
            if all(w in (term + "s", term + "es", term + "d") for w in longer):
                continue
            if longer:
                out.append((kk_id, term))
    return sorted(set(out))


def validate(lexicon: Lexicon, valid_kk_ids: set[str]) -> list[str]:
    """Dot point ids in the lexicon that the study design no longer has.

    Ids are positional, so a study design re-import can leave a lexicon pointing
    at the wrong concepts. Checked on load and in the tests.
    """
    return sorted(set(lexicon.concepts) - valid_kk_ids)
