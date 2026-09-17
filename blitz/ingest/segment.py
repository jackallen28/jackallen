"""Split a Checkpoints-style book into individual questions.

Written against a real Checkpoints Physics extract, whose structure is:

    Question 12/ 11              <- question number / page in the printed book
    [Adapted VCAA 2018 NHT SA Q8]
    <stem>
    a. <part>          (2 marks)
    b. <part>          (3 marks)
    A <option>  B <option>  C <option>  D <option>
    Solution
    <worked solution>
    Question 13/ 11
    ...

Two things drove the design:

* Questions run across page boundaries, so the whole book is walked as one
  stream of lines rather than page by page.
* Some questions cannot be reconstructed as text at all. A stacked fraction
  extracts as "h²" on one line and "2mλ₂" on the next, with the fraction bar
  being a drawn rule; there is no arrangement of those spans that reads
  correctly. Rather than print a mangled formula on a revision sheet, those
  questions are flagged `needs_crop` and the renderer shows an image of the
  real page instead. Text is still kept for searching and tagging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .textflow import Line, build_lines, fraction_bars, horizontal_rules

# "Question 12/ 11" — question number, then the page in the printed book.
HEADER = re.compile(r"^Question\s+(\d+)\s*/\s*(\d+)\s*$", re.IGNORECASE)
SOLUTION = re.compile(r"^\s*Solutions?\s*:?\s*$", re.IGNORECASE)
# "[VCAA 2019 SA Q14]", "[Adapted VCAA 2018 NHT SA Q8]"
PROVENANCE = re.compile(r"^\[([^\]]*(?:VCAA|Adapted)[^\]]*)\]\s*$", re.IGNORECASE)
MARKS_LINE = re.compile(r"^\((\d+)\s*marks?\)\s*$", re.IGNORECASE)
MARKS_INLINE = re.compile(r"\((\d+)\s*marks?\)", re.IGNORECASE)
PART = re.compile(r"^([a-h])[.)]\s+(?=\S)")
OPTION = re.compile(r"^([A-E])[.)]?\s+(?=\S)")
NOISE = re.compile(
    r"^(chapter\s+\d|unit\s+[1-4]\b|area of study|isbn|©|copyright|"
    r"cambridge university press|uncorrected|sample pages|page\s+\d+|\d{1,4})\s*$",
    re.IGNORECASE,
)

# Glyphs that only show up when the extractor has mangled a formula, plus the
# Mathematical Alphanumeric Symbols block used by equation editors.
MATH_GLYPH = re.compile(r"[\U0001D400-\U0001D7FF]")
# A short line that is nothing but symbols is almost always a stray numerator.
ORPHAN_MATH = re.compile(r"^[^\w\s]{0,3}[A-Za-zα-ω]{0,3}[²³⁰-₟\^]+[^\w\s]{0,3}$")


@dataclass
class RawQuestion:
    """One question, still untagged."""

    number: str | None = None
    printed_page: str | None = None
    text: str = ""
    options: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    marks: int | None = None
    answer: str | None = None
    provenance: str | None = None
    page_index: int = 0
    end_page_index: int = 0
    bbox: tuple[float, float, float, float] | None = None
    answer_bbox: tuple[float, float, float, float] | None = None
    # Text printed above the question header that sets up the question — a
    # shared scenario or a lead-in to a figure. Checkpoints prints these before
    # the rule that fences the question, so they arrive attached to the previous
    # question and have to be moved forward.
    stimulus: str = ""
    stimulus_page: int | None = None
    needs_crop: bool = False
    crop_reason: str = ""
    # A mangled worked solution is worse than a mangled question — it teaches
    # the wrong thing — so the answer is checked and cropped independently.
    answer_needs_crop: bool = False
    answer_crop_reason: str = ""

    @property
    def looks_like_question(self) -> bool:
        if len(self.text) < 20:
            return False
        return bool(self.text or self.options or self.parts)

    @property
    def full_text(self) -> str:
        bits = [self.stimulus, self.text, *self.parts]
        return " ".join(b for b in bits if b).strip()

    @property
    def is_stimulus_only(self) -> bool:
        """A block that sets up the next question rather than asking one.

        Checkpoints heads these with their own "Question N/ P", but they carry
        no options, no parts, no marks and no actual interrogative — just the
        sentence introducing a graph. Indexed on their own they are unanswerable;
        merged forward they are the context the next question needs.
        """
        if self.options or self.parts or self.marks or self.answer:
            return False
        text = self.text.strip()
        if not text or len(text) > 220:
            return False
        if "?" in text:
            return False
        return bool(re.match(
            r"^(the|a|an|this|these|below|shown|use|refer|consider)\b", text,
            re.IGNORECASE))


@dataclass
class _Entry:
    """A line plus where it sits in the book."""

    line: Line
    page_index: int


@dataclass
class _PageInfo:
    """Per-page geometry the segmenter needs after the lines are flattened."""

    bars: list[tuple[float, float, float, float]]
    height: float


def _stream(doc, first: int = 0, last: int | None = None
            ) -> tuple[list[_Entry], dict[int, _PageInfo]]:
    """Every line in the book, in order, tagged with its page."""
    last = doc.page_count if last is None else min(last, doc.page_count)
    out: list[_Entry] = []
    info: dict[int, _PageInfo] = {}
    for index in range(first, last):
        page = doc[index]
        info[index] = _PageInfo(bars=fraction_bars(page), height=page.rect.height)
        for line in build_lines(page):
            if NOISE.match(line.text):
                continue
            out.append(_Entry(line=line, page_index=index))
    return out, info


def _bbox(entries: list[_Entry], page_index: int) -> tuple[float, float, float, float] | None:
    same = [e.line for e in entries if e.page_index == page_index]
    if not same:
        return None
    return (min(l.x0 for l in same), min(l.y0 for l in same),
            max(l.x1 for l in same), max(l.y1 for l in same))


def _looks_mangled(lines: list[str]) -> tuple[bool, str]:
    """Would printing this text misrepresent what's on the page?"""
    joined = " ".join(lines)
    if MATH_GLYPH.search(joined):
        return True, "equation-editor glyphs"
    orphans = [l for l in lines if l.strip() and ORPHAN_MATH.match(l.strip())]
    if orphans:
        return True, f"stacked fraction (orphan run {orphans[0]!r})"
    # A lone numerator often survives as a 1-3 character line between prose.
    for i, line in enumerate(lines):
        stripped = line.strip()
        if 0 < len(stripped) <= 3 and i + 1 < len(lines) and len(lines[i + 1]) > 8:
            if re.fullmatch(r"[A-Za-z]?[²³⁰-₟]", stripped):
                return True, "stacked fraction"
    return False, ""


def _split_options(lines: list[str]) -> tuple[list[str], list[str]]:
    """Pull a trailing run of A/B/C/D option lines off the body.

    The scan runs backwards from the end, but a stem beginning "A dark region in
    a two-slit pattern..." matches the option pattern too, so the collected
    letters come out [A, A, B, C, D] and the run looks malformed. Discarding the
    lot lost every option on such questions. Instead, take the longest suffix
    whose letters really are A, B, C, ... in order.
    """
    candidates: list[tuple[int, str, str]] = []
    for i in range(len(lines) - 1, -1, -1):
        m = OPTION.match(lines[i].strip())
        if not m or len(candidates) >= 6:
            break
        candidates.append(
            (i, m.group(1).upper(), OPTION.sub("", lines[i].strip(), count=1).strip())
        )
    candidates.reverse()

    for size in range(len(candidates), 2, -1):
        run = candidates[-size:]
        if [c[1] for c in run] == list("ABCDEF"[:size]):
            cut = run[0][0]
            return lines[:cut], [c[2] for c in run]
    return lines, []


def _bars_inside(entries: list[_Entry], info: dict[int, _PageInfo]) -> int:
    """Count fraction bars falling within the vertical span of these lines."""
    count = 0
    by_page: dict[int, list[Line]] = {}
    for e in entries:
        by_page.setdefault(e.page_index, []).append(e.line)
    for page_index, lines in by_page.items():
        page = info.get(page_index)
        if not page:
            continue
        top = min(l.y0 for l in lines) - 4
        bottom = max(l.y1 for l in lines) + 4
        count += sum(1 for _, y0, _, y1 in page.bars if top <= y0 <= bottom)
    return count


def _parse_unit(entries: list[_Entry],
                info: dict[int, _PageInfo] | None = None) -> RawQuestion | None:
    """Turn one Question..Solution..next-Question block into a RawQuestion."""
    if not entries:
        return None

    header = HEADER.match(entries[0].line.text)
    number = header.group(1) if header else None
    printed = header.group(2) if header else None
    body_entries = entries[1:] if header else entries

    # Split the question from its worked solution.
    split_at = next(
        (i for i, e in enumerate(body_entries) if SOLUTION.match(e.line.text)), None
    )
    if split_at is None:
        q_entries, a_entries = body_entries, []
    else:
        q_entries, a_entries = body_entries[:split_at], body_entries[split_at + 1:]

    q_lines = [e.line.text for e in q_entries]
    provenance = None
    kept: list[str] = []
    for line in q_lines:
        p = PROVENANCE.match(line)
        if p:
            provenance = p.group(1).strip()
        else:
            kept.append(line)

    mangled, reason = _looks_mangled(kept)
    if not mangled and info:
        bars = _bars_inside(q_entries or entries, info)
        if bars:
            mangled = True
            reason = f"{bars} fraction bar(s) — stacked maths can't be reflowed"

    body_lines, options = _split_options(kept)

    marks = 0
    stem: list[str] = []
    parts: list[str] = []
    current: list[str] | None = None
    for line in body_lines:
        m = MARKS_LINE.match(line.strip())
        if m:
            marks += int(m.group(1))
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

    answer = " ".join(e.line.text for e in a_entries).strip() or None
    if answer:
        answer = re.sub(r"\s{2,}", " ", answer)

    a_mangled, a_reason = _looks_mangled([e.line.text for e in a_entries])
    if not a_mangled and info and a_entries:
        bars = _bars_inside(a_entries, info)
        if bars:
            a_mangled = True
            a_reason = f"{bars} fraction bar(s) — stacked maths can't be reflowed"

    q = RawQuestion(
        number=number,
        printed_page=printed,
        text=" ".join(stem).strip(),
        options=options,
        parts=parts,
        marks=marks or None,
        answer=answer,
        provenance=provenance,
        page_index=entries[0].page_index,
        end_page_index=entries[-1].page_index,
        bbox=_bbox(q_entries or entries, entries[0].page_index),
        answer_bbox=_bbox(a_entries, a_entries[0].page_index) if a_entries else None,
        needs_crop=mangled,
        crop_reason=reason,
        answer_needs_crop=a_mangled,
        answer_crop_reason=a_reason,
    )
    if not q.text and q.parts:
        # A question that is all parts and no stem still needs something to read.
        q.text = q.parts.pop(0)
    return q if q.looks_like_question else None


def segment_document(doc, first: int = 0, last: int | None = None) -> list[RawQuestion]:
    """Every question in the book, assembled across page boundaries."""
    entries, info = _stream(doc, first, last)
    starts = [i for i, e in enumerate(entries) if HEADER.match(e.line.text)]
    if not starts:
        return _segment_without_headers(entries, info)

    out: list[RawQuestion] = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(entries)
        q = _parse_unit(entries[start:end], info)
        if q:
            out.append(q)
    return _merge_stimuli(out)


def _merge_stimuli(questions: list[RawQuestion]) -> list[RawQuestion]:
    """Fold each stimulus-only block into the question it introduces."""
    out: list[RawQuestion] = []
    pending: RawQuestion | None = None
    for q in questions:
        if q.is_stimulus_only:
            # Two in a row: keep the later one, it is the nearer context.
            pending = q
            continue
        if pending is not None:
            q.stimulus = pending.text
            q.stimulus_page = pending.page_index
            # The stimulus block owns the figure, and its span is where to look.
            if pending.bbox and q.bbox is None:
                q.bbox = pending.bbox
            q.page_index = min(q.page_index, pending.page_index)
            pending = None
        out.append(q)
    if pending is not None:
        out.append(pending)          # trailing stimulus with nothing after it
    return out


def _segment_without_headers(entries: list[_Entry],
                             info: dict[int, _PageInfo] | None = None) -> list[RawQuestion]:
    """Fallback for books that number questions as plain "1." rather than headers."""
    numbered = re.compile(r"^\s*(\d{1,3})\s*[.)]\s+(?=\S)")
    out: list[RawQuestion] = []
    current: list[_Entry] = []
    for entry in entries:
        if numbered.match(entry.line.text) and current:
            q = _parse_unit(current, info)
            if q:
                out.append(q)
            current = [entry]
        else:
            current.append(entry)
    if current:
        q = _parse_unit(current, info)
        if q:
            out.append(q)
    return out


def segment_page(page, page_index: int = 0) -> list[RawQuestion]:
    """Single-page segmentation, kept for tests and for spot-checking one page."""
    entries = [_Entry(line=l, page_index=page_index)
               for l in build_lines(page) if not NOISE.match(l.text)]
    info = {page_index: _PageInfo(bars=fraction_bars(page), height=page.rect.height)}
    starts = [i for i, e in enumerate(entries) if HEADER.match(e.line.text)]
    if not starts:
        return _segment_without_headers(entries, info)
    out = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(entries)
        q = _parse_unit(entries[start:end], info)
        if q:
            out.append(q)
    return out


def question_regions(page, question: RawQuestion) -> list[tuple[float, float, float, float]]:
    """Figure regions on a page, bounded by the rules that fence the question."""
    rules = horizontal_rules(page)
    if not question.bbox:
        return []
    _, y0, _, y1 = question.bbox
    above = max([y for y in rules if y < y0 + 2], default=0.0)
    below = min([y for y in rules if y > y1 - 2], default=page.rect.height)
    return [(above, below)]
