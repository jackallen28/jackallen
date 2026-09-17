"""Split a page of a Checkpoints book or textbook into individual questions.

This is heuristic and deliberately conservative: it is better to emit a slightly
over-long question (which still prints fine) than to chop one in half. The
tagging pass downstream sees the text and can reject anything that isn't
actually a question.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Block, PageContent

# "1." / "12)" / "Question 3" / "Q4" at the start of a line.
NUMBERED = re.compile(r"^\s*(?:Question\s+|Q)?(\d{1,3})\s*[.)]\s+(?=\S)", re.IGNORECASE)
# "a." / "(b)" / "ii." sub-parts.
SUBPART = re.compile(r"^\s*\(?([a-h]|i{1,3}v?|iv|vi{0,3})\)?[.)]\s+(?=\S)", re.IGNORECASE)
OPTION = re.compile(r"^\s*\(?([A-E])\)?[.)]?\s+(?=\S)")
MARKS = re.compile(r"\((\d{1,2})\s*marks?\)", re.IGNORECASE)
# Running heads, page furniture and copyright lines we never want in a question.
NOISE = re.compile(
    r"^(chapter\s+\d|unit\s+[1-4]\b|area of study|isbn|©|copyright|cambridge "
    r"university press|photocopying is restricted|\d{1,4}$)",
    re.IGNORECASE,
)

# Command terms are matched ANYWHERE in the text, not just at the start of a
# line. A question number ("4. State Lenz's law") and ordinary line wrapping
# ("The diagram below shows... / Explain the direction...") both push the command
# term off the line start, and anchoring here silently dropped both. Segmentation
# is deliberately permissive; the tagger is the strict gate that rejects prose.
QUESTION_CUE = re.compile(
    r"\?|\b(calculate|determine|explain|describe|state|identify|outline|"
    r"discuss|evaluate|analyse|analyze|compare|distinguish|justify|propose|"
    r"show that|sketch|draw|estimate|define|list|name|suggest|find)\b",
    re.IGNORECASE,
)


@dataclass
class RawQuestion:
    """A candidate question, still untagged and unvalidated."""

    number: str | None
    text: str
    options: list[str] = field(default_factory=list)
    marks: int | None = None
    page_index: int = 0
    printed_page: str | None = None
    # Bounding box of the blocks this came from, used to look for a nearby figure.
    bbox: tuple[float, float, float, float] | None = None
    blocks: list[Block] = field(default_factory=list)

    @property
    def looks_like_question(self) -> bool:
        if len(self.text) < 25:
            return False
        if NOISE.match(self.text):
            return False
        return bool(QUESTION_CUE.search(self.text)) or bool(self.options)


def segment_page(page: PageContent) -> list[RawQuestion]:
    """Group blocks into questions by looking for numbering restarts."""
    groups: list[list[Block]] = []
    numbers: list[str | None] = []

    for block in page.blocks:
        first_line = block.text.splitlines()[0] if block.text else ""
        if NOISE.match(first_line.strip()):
            continue
        m = NUMBERED.match(first_line)
        if m or not groups:
            groups.append([block])
            numbers.append(m.group(1) if m else None)
        else:
            groups[-1].append(block)

    out: list[RawQuestion] = []
    for number, group in zip(numbers, groups):
        text = "\n".join(b.text for b in group).strip()
        body, options = _split_options(text)
        body = NUMBERED.sub("", body, count=1).strip()
        marks_match = MARKS.search(text)
        rq = RawQuestion(
            number=number,
            text=_tidy(body),
            options=[_tidy(o) for o in options],
            marks=int(marks_match.group(1)) if marks_match else None,
            page_index=page.index,
            printed_page=page.printed,
            bbox=_bbox(group),
            blocks=group,
        )
        if rq.looks_like_question:
            out.append(rq)
    return out


def _split_options(text: str) -> tuple[str, list[str]]:
    """Pull trailing A/B/C/D lines off a multiple-choice stem."""
    lines = text.splitlines()
    options: list[str] = []
    cut = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        m = OPTION.match(lines[i])
        if m and len(options) < 6:
            options.insert(0, OPTION.sub("", lines[i], count=1).strip())
            cut = i
        elif options:
            break
    if len(options) < 3:          # 2 "options" is almost always a false positive
        return text, []
    return "\n".join(lines[:cut]).strip(), options


def _tidy(text: str) -> str:
    text = MARKS.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\.{4,}", "", text)          # dotted answer lines
    text = re.sub(r"_{3,}", " ", text)
    return text.strip()


def _bbox(blocks: list[Block]) -> tuple[float, float, float, float] | None:
    if not blocks:
        return None
    return (
        min(b.x0 for b in blocks),
        min(b.y0 for b in blocks),
        max(b.x1 for b in blocks),
        max(b.y1 for b in blocks),
    )


def nearest_figure(
    rq: RawQuestion, regions: list[tuple[float, float, float, float]],
    max_gap: float = 90.0,
) -> tuple[float, float, float, float] | None:
    """The figure region most likely to belong to this question.

    Prefers a region that sits inside the question's vertical span, then the
    closest one below it — which is how figures are laid out in both books.
    """
    if not rq.bbox or not regions:
        return None
    _, qy0, _, qy1 = rq.bbox

    inside = [r for r in regions if qy0 - 8 <= r[1] and r[3] <= qy1 + 8]
    if inside:
        return max(inside, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))

    below = [(r[1] - qy1, r) for r in regions if 0 <= r[1] - qy1 <= max_gap]
    if below:
        return min(below)[1]

    above = [(qy0 - r[3], r) for r in regions if 0 <= qy0 - r[3] <= max_gap / 2]
    if above:
        return min(above)[1]
    return None
