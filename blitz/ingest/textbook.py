"""Question extraction for textbooks, as opposed to Checkpoints.

A textbook does not head each question "Question 12/ 11". It gathers them: a
"Worked example 6.2" with its solution, a "Questions" block at the end of a
section, "Chapter review" at the end of a chapter — each a numbered list under a
heading. So the unit of segmentation is the block, found by its heading, and the
questions are the numbered items inside it.

The heading vocabulary below was written against synthetic pages and then
tuned against two real books, which disagreed about almost every word:

* a Jacaranda-style VCE Physics textbook heads its worked examples
  "Sample problem 1.6", not "Worked example", and scatters single questions
  through the prose as "Revision question 1.5";
* an Edrolo-style VCE Business Management textbook heads each question
  "Question 1" with "(2 MARKS)" on the line below, opens a block with
  "Exam-style questions", puts a shared "Case study" above it, and cites
  "Adapted from VCAA 2020 exam Section A Q1a" under each one.

Both are handled below. A third publisher will use a third vocabulary, and
this is still the first place to look when a new book comes out empty.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .segment import (
    MARKS_INLINE, MARKS_LINE, OPTION, PART, PROVENANCE, RESOURCE_HEADING,
    RawQuestion, _Entry, _PageInfo, _split_options, _stream, is_resource_note,
    normalise_part, rejoin_wrapped_marks,
)
from .textflow import Line

# Headings that open a block of questions. Case-insensitive, start of line.
QUESTION_BLOCK = re.compile(
    r"^("
    # The plain ones.
    r"questions?|review questions?|chapter review|section review|unit review|"
    r"exercises?|problems|activities|"
    # "Check your ..." — Oxford, Pearson and Jacaranda each chose a different
    # noun, and a book that uses one never uses the others.
    r"check your (learning|understanding|knowledge|recall)|"
    r"quick check|learning check|self[- ]check|knowledge check|"
    r"test yourself|try (this|these|it yourself)|now try this|"
    # End of chapter.
    r"end[- ]of[- ]chapter( questions?)?|chapter questions?|"
    r"consolidation( questions?)?|revision questions?|further questions?|"
    # Exam practice.
    r"practice questions?|exam[- ]style questions?|exam questions?|"
    r"multiple[- ]choice( questions?)?|short[- ]answer( questions?)?|"
    r"extended[- ]response( questions?)?|"
    r"key questions?|section questions?|"
    r"application questions?|analysis questions?|"
    r"skills and applications|apply your (understanding|knowledge)|"
    r"knowledge and understanding"
    r")\b[^\n]{0,40}$",
    re.IGNORECASE)
WORKED_EXAMPLE = re.compile(
    r"^(worked example|sample problem|worked solution)\s*(\d+(?:\.\d+)*)?",
    re.IGNORECASE)
# A single question set in the middle of the teaching prose, which is how the
# Physics book paces its chapters. It opens a block of exactly one question.
REVISION_QUESTION = re.compile(
    r"^revision question\s*([a-z]?\d+(?:\.\d+)*)", re.IGNORECASE)
SOLUTION = re.compile(r"^(solution|answer|working)\s*:?\s*$", re.IGNORECASE)
# "1. Define ...", "1) Define ...", and — Oxford, Pearson and most Australian
# textbooks — a bare "1 Define ...". The bare form needs a capital letter after
# it or it swallows measurements and stray numbers: "10 m/s is the speed",
# "2 marks", "5.0 kg". Three digits at most, so a year like 2019 cannot match.
NUMBERED = re.compile(r"^\s*(\d{1,3})(?:\s*[.)]\s+(?=\S)|\s+(?=[A-Z]))")
# "Question 1" on a line of its own, with the question under it. Distinct from
# Checkpoints' "Question 12/ 11", which carries a page number after a slash.
# The marks often sit on the same line as the number rather than under it,
# and some books bracket it: "Question 1 (2 MARKS)", "Question 1.", "Q3".
QUESTION_MARKER = re.compile(
    r"^q(?:uestion)?\s*(\d{1,3})\s*[.):]?\s*(?:\(\s*\d+\s*marks?\s*\))?\s*$",
    re.IGNORECASE)
# A shared stimulus every question in the block refers back to. Without it the
# questions under it are unanswerable, so it travels with them as context.
CONTEXT_BLOCK = re.compile(
    r"^(case study|scenario|stimulus( material)?|background|"
    r"the following information|read the (following|extract))\b[^\n]{0,40}$",
    re.IGNORECASE)
# Anything that ends a question block: the next teaching heading.
BLOCK_END_RATIO = 1.15


@dataclass
class _Block:
    kind: str        # "questions" | "worked-example" | "revision" | "context"
    label: str
    entries: list[_Entry]
    # A shared stimulus printed above the block — the Business Management book's
    # "Case study". Every question in the block needs it to make sense.
    context: str = ""
    context_page: int | None = None


def _blocks(entries: list[_Entry], body_size: float) -> list[_Block]:
    """Slice the stream into question blocks, worked examples and stimuli."""
    blocks: list[_Block] = []
    current: _Block | None = None
    context = ""
    context_page: int | None = None

    def close() -> None:
        """Finish the open block: a stimulus is held back, the rest is kept."""
        nonlocal current, context, context_page
        if current is None:
            return
        if current.kind == "context":
            context = " ".join(
                e.line.text.strip() for e in current.entries).strip()
            context_page = current.entries[0].page_index if current.entries else None
        else:
            blocks.append(current)
        current = None

    for e in entries:
        t = e.line.text.strip()
        is_heading = e.line.size >= body_size * BLOCK_END_RATIO and len(t) < 90

        if WORKED_EXAMPLE.match(t):
            close()
            context, context_page = "", None
            current = _Block("worked-example", t, [])
            continue
        if REVISION_QUESTION.match(t):
            close()
            context, context_page = "", None
            current = _Block("revision", t, [])
            continue
        if RESOURCE_HEADING.match(t):
            # "Resources" / "learnON" heads a list of links, not questions.
            close()
            context, context_page = "", None
            continue
        if CONTEXT_BLOCK.match(t):
            close()
            context, context_page = "", None
            current = _Block("context", t, [])
            continue
        if QUESTION_MARKER.match(t):
            # "Question 1" numbers an item, but QUESTION_BLOCK would read it as
            # a heading and open an empty block on every question in the book.
            # It opens a block only when there is none, for a publisher — or a
            # practice SAC — that prints no heading above the list at all.
            if current is not None and current.kind == "context":
                # A SAC opens with "CASE STUDY" and goes straight to
                # "Question 1". Without this the stimulus block stays open and
                # swallows every question in the paper, and the paper indexes
                # as nothing at all.
                close()
            if current is None:
                current = _Block("questions", "", [], context, context_page)
                context, context_page = "", None
            current.entries.append(e)
            continue
        if QUESTION_BLOCK.match(t):
            close()
            current = _Block("questions", t, [], context, context_page)
            context, context_page = "", None
            continue
        if is_heading and current:
            # A new teaching heading closes the block.
            close()
            continue
        if current is not None:
            current.entries.append(e)

    close()
    return blocks


def _item_number(text: str) -> str | None:
    """The question number opening a line, in either book's notation."""
    m = QUESTION_MARKER.match(text.strip())
    if m:
        return m.group(1)
    m = NUMBERED.match(text)
    return m.group(1) if m else None


def _split_numbered(entries: list[_Entry]) -> list[list[_Entry]]:
    """Split a block into its numbered items, restarting on each number."""
    items: list[list[_Entry]] = []
    current: list[_Entry] = []
    for e in entries:
        if _item_number(e.line.text) is not None and current:
            items.append(current)
            current = [e]
        else:
            current.append(e)
    if current:
        items.append(current)
    return [i for i in items if _item_number(i[0].line.text) is not None]


def _make_question(item: list[_Entry], info: dict[int, _PageInfo],
                   block: _Block, printed_offset: int,
                   number: str | None = None) -> RawQuestion | None:
    from .segment import _bars_inside, _bbox, _looks_mangled

    lines = rejoin_wrapped_marks([e.line.text for e in item])
    declared_marks: int | None = None
    if number is None:
        # "Question 1" stands on its own line and is not part of the question;
        # "1. " opens the first line and is stripped off it.
        marker = QUESTION_MARKER.match(lines[0].strip())
        if marker:
            number = marker.group(1)
            # Keep anything after the number — "(2 MARKS)" often rides on the
            # same line, and dropping the whole line dropped the marks with it.
            rest = lines[0].strip()[marker.end(1):].lstrip(" .):")
            mk = MARKS_LINE.match(rest.strip())
            if mk:
                # Marks stated on the header line are the question's total,
                # full stop. A SAC restates them at the end of a single-part
                # question — "Question 3 (12 marks) ... (12 marks)" — and
                # counting both made it a 24-mark question.
                declared_marks = int(mk.group(1))
                rest = ""
            lines = ([rest] if rest.strip() else []) + lines[1:]
        else:
            m = NUMBERED.match(lines[0])
            number = m.group(1) if m else None
            lines[0] = NUMBERED.sub("", lines[0], count=1)
    if not lines:
        return None

    # Where the callout sits decides what it means. Opening the question, the
    # whole item is a link dressed as a question — including the hybrid kind
    # ("Try out this Interactivity ... and describe what happens"), which a
    # student cannot do on paper. Trailing, it is the block's sign-off swept
    # into the last question, and only the line goes.
    if lines and is_resource_note(lines[0]):
        return None

    provenance = None
    kept: list[str] = []
    for line in lines:
        p = PROVENANCE.match(line.strip())
        if p:
            provenance = (p.group(1) or p.group(2)).strip()
        elif not is_resource_note(line):
            kept.append(line)
    lines = kept

    if not lines:
        return None

    body_lines, options = _split_options(lines)
    # Marks are counted in two places and only one of them is the total.
    #
    # A practice SAC heads the question with its total — "Question 1 (8 marks)"
    # — and then gives each part its own allocation, a. (2), b. (2), c. (4).
    # Adding both gave 16 for an 8-mark question, which then bought twice the
    # answer space it needed and threw the sheet's page budget out. So marks
    # found before the first part are the declared total and win; marks on the
    # parts are only used when nothing was declared.
    header_marks = 0
    part_marks = 0
    stem: list[str] = []
    parts: list[str] = []
    current: list[str] | None = None

    def add(n: int) -> None:
        nonlocal header_marks, part_marks
        if current is None and not parts:
            header_marks += n
        else:
            part_marks += n

    for line in body_lines:
        mk = MARKS_LINE.match(line.strip())
        if mk:
            add(int(mk.group(1)))
            continue
        inline = MARKS_INLINE.search(line)
        if inline:
            is_part = bool(PART.match(line))
            if is_part:
                part_marks += int(inline.group(1))
            else:
                add(int(inline.group(1)))
            line = MARKS_INLINE.sub("", line).strip()
        if PART.match(line):
            if current:
                parts.append(" ".join(current).strip())
            current = [normalise_part(line)]
        elif current is not None:
            current.append(line)
        else:
            stem.append(line)
    if current:
        parts.append(" ".join(current).strip())
    marks = declared_marks or header_marks or part_marks

    text = " ".join(stem).strip()
    if not text and parts:
        text = parts.pop(0)
    if len(text) < 15 or is_resource_note(text):
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
        stimulus=block.context, stimulus_page=block.context_page,
        needs_crop=mangled, crop_reason=reason,
        provenance=provenance or block.label or None,
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
    if len(text) < 15 or is_resource_note(text):
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
        number=m.group(2) if m and m.group(2) else None,
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
        if block.kind == "revision":
            # One question, numbered by its own heading rather than a list.
            if not block.entries:
                continue
            m = REVISION_QUESTION.match(block.label)
            q = _make_question(block.entries, info, block, printed_offset,
                               number=m.group(1) if m else None)
            if q:
                out.append(q)
            continue
        for item in _split_numbered(block.entries):
            q = _make_question(item, info, block, printed_offset)
            if q:
                out.append(q)
    return out
