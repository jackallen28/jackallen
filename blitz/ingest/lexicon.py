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

        score = 0.0
        for trigger in self.triggers:
            if not _present(trigger, haystack):
                continue
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


def _present(term: str, haystack: str) -> bool:
    term = term.lower().strip()
    if not term:
        return False
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
    directory = Path(directory or STUDY_DESIGN_DIR)
    path = directory / f"{subject_id}-lexicon.yaml"
    if not path.exists():
        return Lexicon(subject_id=subject_id)
    with path.open(encoding="utf-8") as fh:
        return _parse(yaml.safe_load(fh) or {})


def validate(lexicon: Lexicon, valid_kk_ids: set[str]) -> list[str]:
    """Dot point ids in the lexicon that the study design no longer has.

    Ids are positional, so a study design re-import can leave a lexicon pointing
    at the wrong concepts. Checked on load and in the tests.
    """
    return sorted(set(lexicon.concepts) - valid_kk_ids)
