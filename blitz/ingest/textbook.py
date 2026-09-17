"""Question extraction for textbooks, as opposed to Checkpoints.

A textbook does not head each question "Question 12/ 11". It gathers them: a
"Worked example 6.2" with its solution, a "Questions" block at the end of a
section, "Chapter review" at the end of a chapter — each a numbered list under a
heading. So the unit of segmentation is the block, found by its heading, and the
questions are the numbered items inside it.

Written against synthetic pages shaped like a Cambridge/Heinemann/Jacaranda
textbook, not a real one. The heading vocabulary below is the first thing to
tune when a real textbook arrives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .segment import (
    MARKS_INLINE, MARKS_LINE, OPTION, PART, RawQuestion, _Entry, _PageInfo,
    _split_options, _stream,
)
from .textflow import Line

# Headings that open a block of questions. Case-insensitive, start of line.
QUESTION_BLOCK = re.compile(
    r"^(review questions?|questions?|exercises?|chapter review|section review|"
    r"end[- ]of[- ]chapter|test yourself|check your understanding|"
    r"try (this|these)|practice questions?|exam[- ]style questions?|"
    r"multiple[- ]choice questions?|short[- ]answer questions?|"
    r"key questions?|section questions?)\b[^\n]{0,40}$",
    re.IGNORECASE)
WORKED_EXAMPLE = re.compile(r"^worked example\s*(\d+(?:\.\d+)*)?", re.IGNORECASE)
SOLUTION = re.compile(r"^(solution|answer|working)\s*:?\s*$", re.IGNORECASE)
NUMBERED = re.compile(r"^\s*(\d{1,3})\s*[.)]\s+(?=\S)")
# Anything that ends a question block: the next teaching heading.
BLOCK_END_RATIO = 1.15


@dataclass
class _Block:
    kind: str                     # "questions" | "worked-example"
    label: str
    entries: list[_Entry]


def _blocks(entries: list[_Entry], body_size: float) -> list[_Block]:
    """Slice the stream into question blocks and worked examples."""
    blocks: list[_Block] = []
    current: _Block | None = None

    for e in entries:
        t = e.line.text.strip()
        is_heading = e.line.size >= body_size * BLOCK_END_RATIO and len(t) < 90

        if WORKED_EXAMPLE.match(t):
            if current:
                blocks.append(current)
            current = _Block("worked-example", t, [])
            continue
        if QUESTION_BLOCK.match(t):
            if current:
                blocks.append(current)
            current = _Block("questions", t, [])
            continue
        if is_heading and current:
            # A new teaching heading closes the block.
            blocks.append(current)
            current = None
            continue
        if current is not None:
            current.entries.append(e)

    if current:
        blocks.append(current)
    return blocks


def _split_numbered(entries: list[_Entry]) -> list[list[_Entry]]:
    """Split a block into its numbered items, restarting on each number."""
    items: list[list[_Entry]] = []
    current: list[_Entry] = []
    for e in entries:
        if NUMBERED.match(e.line.text) and current:
            items.append(current)
            current = [e]
        else:
            current.append(e)
    if current:
        items.append(current)
    return [i for i in items if NUMBERED.match(i[0].line.text)]


def _make_question(item: list[_Entry], info: dict[int, _PageInfo],
                   block_label: str, printed_offset: int) -> RawQuestion | None:
    from .segment import _bars_inside, _bbox, _looks_mangled

    lines = [e.line.text for e in item]
    m = NUMBERED.match(lines[0])
    number = m.group(1) if m else None
    lines[0] = NUMBERED.sub("", lines[0], count=1)

    body_lines, options = _split_options(lines)
    marks = 0
    stem: list[str] = []
    parts: list[str] = []
    current: list[str] | None = None
    for line in body_lines:
        mk = MARKS_LINE.match(line.strip())
        if mk:
            marks += int(mk.group(1))
            continue
        inline = MARKS_INLINE.search(line)
        if inline:
            marks += int(inline.group(1))
            line = MARKS_INLINE.sub("", line).strip()
        if PART.match(line):
            if current:
                parts.append(" ".join(current).strip())
            current = [line]
        elif current is not None:
            current.append(line)
        else:
            stem.append(line)
    if current:
        parts.append(" ".join(current).strip())

    text = " ".join(stem).strip()
    if not text and parts:
        text = parts.pop(0)
    if len(text) < 15:
        return None

    mangled, reason = _looks_mangled(lines)
    if not mangled and _bars_inside(item, info):
        mangled, reason = True, "fraction bar(s) — stacked maths can't be reflowed"

    page = item[0].page_index
    return RawQuestion(
        number=number,
        printed_page=str(page + 1 + printed_offset) if printed_offset is not None else None,
        text=text, options=options, parts=parts, marks=marks or None,
        page_index=page, end_page_index=item[-1].page_index,
        bbox=_bbox(item, page),
        needs_crop=mangled, crop_reason=reason,
        provenance=block_label if block_label else None,
    )


def _worked_example(block: _Block, info: dict[int, _PageInfo],
                    printed_offset: int) -> RawQuestion | None:
    """A worked example is a question with its solution attached."""
    from .segment import _bars_inside, _bbox, _looks_mangled

    q_entries: list[_Entry] = []
    a_entries: list[_Entry] = []
    in_answer = False
    for e in block.entries:
        if SOLUTION.match(e.line.text.strip()):
            in_answer = True
            continue
        (a_entries if in_answer else q_entries).append(e)
    if not q_entries:
        return None

    text = " ".join(e.line.text for e in q_entries).strip()
    if len(text) < 15:
        return None
    answer = " ".join(e.line.text for e in a_entries).strip() or None

    q_mangled, q_reason = _looks_mangled([e.line.text for e in q_entries])
    if not q_mangled and _bars_inside(q_entries, info):
        q_mangled, q_reason = True, "fraction bar(s)"
    a_mangled, a_reason = (False, "")
    if a_entries:
        a_mangled, a_reason = _looks_mangled([e.line.text for e in a_entries])
        if not a_mangled and _bars_inside(a_entries, info):
            a_mangled, a_reason = True, "fraction bar(s)"

    page = q_entries[0].page_index
    m = WORKED_EXAMPLE.match(block.label)
    return RawQuestion(
        number=m.group(1) if m and m.group(1) else None,
        printed_page=str(page + 1 + printed_offset) if printed_offset is not None else None,
        text=text, answer=answer,
        page_index=page, end_page_index=block.entries[-1].page_index,
        bbox=_bbox(q_entries, page),
        answer_bbox=_bbox(a_entries, a_entries[0].page_index) if a_entries else None,
        needs_crop=q_mangled, crop_reason=q_reason,
        answer_needs_crop=a_mangled, answer_crop_reason=a_reason,
        provenance=block.label,
    )


def segment_textbook(doc, first: int = 0, last: int | None = None,
                     body_size: float | None = None,
                     printed_offset: int = 0) -> list[RawQuestion]:
    """Every question and worked example in a textbook."""
    from .passages import body_font_size

    entries, info = _stream(doc, first, last)
    body_size = body_size or body_font_size(doc)
    out: list[RawQuestion] = []
    for block in _blocks(entries, body_size):
        if block.kind == "worked-example":
            q = _worked_example(block, info, printed_offset)
            if q:
                out.append(q)
            continue
        for item in _split_numbered(block.entries):
            q = _make_question(item, info, block.label, printed_offset)
            if q:
                out.append(q)
    return out
