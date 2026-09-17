"""Index a book's explanatory content, section by section.

Questions are half of what a textbook holds. The other half is the prose that
teaches the thing the questions test, and a revision sheet that can point a
student at "Chapter 6.3, p. 142" for the dot point they are stuck on is worth
more than one that only tests them on it.

Sections are found by typography, not by parsing a contents page: a heading is
a short line set noticeably larger than the book's body text. Everything from
one heading to the next is one passage. Each passage is tagged to the dot
points it covers using the same lexicon the question tagger uses, and prose is
a far easier target than a question stem — a section on the photoelectric
effect says "photoelectric" many times.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .segment import NOISE
from .textflow import Line, build_lines

# A heading is at least this much larger than body text.
HEADING_RATIO = 1.15
# ...and set in a size that is RARE. Checkpoints sets every question stem in a
# 14.5pt maths font against 10pt prose, so size alone called "D 250 m s⁻¹" a
# heading and swept whole questions in as teaching content. A size carrying
# more than this share of the book's characters is body text of some kind,
# whatever its ratio to the modal size.
HEADING_MAX_SHARE = 0.08
# Lines that are maths, options or answers, whatever their size.
NOT_A_HEADING = re.compile(
    r"=|^[A-E]\s+\S|^[a-e][.)]\s|\d\s*(m|s|kg|eV|J|Hz|N|V|A|T|Wb)\b|×\s*10|"
    r"^[\d.\s×⁻⁺⁰-⁹₀-₉]+$",
)
# And no longer than this — long lines in a big font are pull quotes, not headings.
HEADING_MAX_CHARS = 90
# Passages shorter than this are captions, labels and stragglers.
MIN_PASSAGE_CHARS = 220
# Passages longer than this are split at paragraph breaks so a tag means something.
MAX_PASSAGE_CHARS = 6000

NUMBERED = re.compile(r"^\s*\d{1,3}\s*[.)]\s+\S")
TOC_LEADERS = re.compile(r"\.{5,}\s*\d+\s*$")
CHAPTER = re.compile(r"^(chapter|unit|section|topic)\s+\d+", re.IGNORECASE)
SECTION_NUMBER = re.compile(r"^(\d+(?:\.\d+)+)\s+\S")
# Sections that are apparatus, not teaching.
SKIP_TITLES = re.compile(
    r"^(contents|index|glossary|acknowledg|answers?|solutions?|references|"
    r"appendix|about (the|this) book|how to use|preface|foreword)",
    re.IGNORECASE)


@dataclass
class Passage:
    title: str
    body: str
    page_start: int
    page_end: int
    level: int = 2                 # 1 = chapter, 2 = section, 3 = subsection
    section_number: str | None = None
    kk_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def chars(self) -> int:
        return len(self.body)

    @property
    def is_question_list(self) -> bool:
        """Mostly numbered items: that is the exercises block, not teaching."""
        lines = [l for l in self.body.split("\n") if l.strip()]
        if len(lines) < 4:
            return False
        numbered = sum(1 for l in lines if NUMBERED.match(l))
        return numbered / len(lines) > 0.45


def size_profile(doc, sample: int = 30) -> Counter:
    """Characters set in each font size, across a sample of pages."""
    n = doc.page_count
    step = max(1, n // sample)
    sizes: Counter[float] = Counter()
    for i in range(0, n, step):
        for line in build_lines(doc[i]):
            sizes[round(line.size, 1)] += len(line.text)
    return sizes


def body_font_size(doc, sample: int = 30, profile: Counter | None = None) -> float:
    """The modal font size across the book — what a paragraph is set in."""
    profile = profile or size_profile(doc, sample)
    prose = Counter({k: v for k, v in profile.items()})
    if not prose:
        return 10.0
    return prose.most_common(1)[0][0]


def heading_sizes(profile: Counter, body: float) -> set[float]:
    """Font sizes that are both larger than body text and rare."""
    total = sum(profile.values()) or 1
    return {
        size for size, chars in profile.items()
        if size >= body * HEADING_RATIO and chars / total <= HEADING_MAX_SHARE
    }


def _is_heading(line: Line, body: float, sizes: set[float] | None = None) -> bool:
    t = line.text.strip()
    if not t or len(t) > HEADING_MAX_CHARS:
        return False
    if sizes is not None:
        if round(line.size, 1) not in sizes:
            return False
    elif line.size < body * HEADING_RATIO:
        return False
    if TOC_LEADERS.search(t) or NUMBERED.match(t) or NOT_A_HEADING.search(t):
        return False
    # A heading has words in it.
    letters = sum(ch.isalpha() for ch in t)
    return letters >= max(4, len(t) * 0.5)


def _level(line: Line, body: float) -> int:
    ratio = line.size / body
    t = line.text.strip()
    if CHAPTER.match(t) or ratio >= 1.6:
        return 1
    if ratio >= 1.3:
        return 2
    return 3


def extract_passages(doc, first: int = 0, last: int | None = None,
                     body: float | None = None) -> list[Passage]:
    """Every teaching section in the book, in order."""
    last = doc.page_count if last is None else min(last, doc.page_count)
    profile = size_profile(doc)
    body = body or body_font_size(doc, profile=profile)
    sizes = heading_sizes(profile, body)

    passages: list[Passage] = []
    current: Passage | None = None
    buffer: list[str] = []

    def close(page_index: int) -> None:
        nonlocal current, buffer
        if current is not None:
            current.body = _tidy("\n".join(buffer))
            current.page_end = page_index
            passages.append(current)
        current, buffer = None, []

    for index in range(first, last):
        for line in build_lines(doc[index]):
            t = line.text.strip()
            if not t or NOISE.match(t):
                continue
            if _is_heading(line, body, sizes):
                close(index)
                m = SECTION_NUMBER.match(t)
                current = Passage(
                    title=t, body="", page_start=index, page_end=index,
                    level=_level(line, body),
                    section_number=m.group(1) if m else None,
                )
                continue
            if current is None:
                # Prose before the first heading — front matter, usually.
                continue
            buffer.append(t)
    close(last - 1)

    return [p for chunk in passages for p in _split(chunk) if _keep(p)]


def _keep(p: Passage) -> bool:
    from .textbook import QUESTION_BLOCK, WORKED_EXAMPLE

    if SKIP_TITLES.match(p.title):
        return False
    # Question blocks and worked examples are indexed as questions, not prose.
    if QUESTION_BLOCK.match(p.title) or WORKED_EXAMPLE.match(p.title):
        return False
    if p.chars < MIN_PASSAGE_CHARS:
        return False
    if p.is_question_list:
        return False
    return True


def _split(p: Passage) -> list[Passage]:
    """Break a very long section at paragraph boundaries."""
    if p.chars <= MAX_PASSAGE_CHARS:
        return [p]
    paras = [x for x in re.split(r"\n{2,}|(?<=[.!?])\n", p.body) if x.strip()]
    out: list[Passage] = []
    buf: list[str] = []
    size = 0
    part = 1
    for para in paras:
        if size + len(para) > MAX_PASSAGE_CHARS and buf:
            out.append(Passage(
                title=f"{p.title} ({part})", body="\n".join(buf),
                page_start=p.page_start, page_end=p.page_end, level=p.level,
                section_number=p.section_number))
            buf, size, part = [], 0, part + 1
        buf.append(para)
        size += len(para)
    if buf:
        out.append(Passage(
            title=f"{p.title} ({part})" if part > 1 else p.title,
            body="\n".join(buf), page_start=p.page_start, page_end=p.page_end,
            level=p.level, section_number=p.section_number))
    return out


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"(?<=[a-z,;])\n(?=[a-z])", " ", text)   # rejoin wrapped lines
    return text.strip()


def tag_passages(passages: list[Passage], tagger, top: int = 3,
                 min_hits: float = 2.0) -> None:
    """Tag each passage to the dot points it teaches, in place.

    Prose gives the lexicon far more to work with than a question stem, so the
    bar is higher: a passage has to accumulate real weight for a dot point, not
    brush past a single term.
    """
    lexicon = getattr(tagger, "lexicon", None)
    for p in passages:
        text = f"{p.title}\n{p.body}"
        if lexicon:
            scores = lexicon.score_all(text)
            ranked = sorted(scores.items(), key=lambda kv: -kv[1])
            keep = [(kk, s) for kk, s in ranked[:top] if s >= min_hits]
            if keep:
                best = keep[0][1]
                p.kk_ids = [kk for kk, s in keep if s >= best * 0.4]
                p.confidence = min(0.5 + best / 20, 0.95)
                continue
        result = tagger.tag(text[:2000])
        if not result.rejected:
            p.kk_ids = result.kk_ids
            p.confidence = result.confidence
