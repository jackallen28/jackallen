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
# Checkpoints fences its attribution in brackets, "[VCAA 2018 SB Q2]". The
# Edrolo Business Management book prints it bare under the question, "Adapted
# from VCAA 2020 exam Section A Q1a". Both are the same thing.
PROVENANCE = re.compile(
    r"^(?:\[([^\]]*(?:VCAA|Adapted)[^\]]*)\]"
    r"|((?:adapted\s+from\s+)?VCAA\s+\d{4}[^\n]{0,60}))\s*$",
    re.IGNORECASE)
# A line that is nothing but the mark allocation. The brackets are optional:
# plenty of books print a bare "2 marks" right-aligned under the question, and
# requiring the brackets left it sitting in the question text with the marks
# uncounted. MARKS_INLINE below still insists on them — stripping an
# unbracketed "2 marks" from mid-sentence would mangle real prose.
MARKS_LINE = re.compile(r"^[(\[]?\s*(\d+)\s*marks?\s*[)\]]?\s*$", re.IGNORECASE)
MARKS_INLINE = re.compile(r"\((\d+)\s*marks?\)", re.IGNORECASE)
# "a. <part>" and the unpunctuated "a <part>". The bare form insists on a
# capital letter, because "a" is also the indefinite article: "a ball is
# dropped" is a stem, "a Calculate the net force" is a part.
PART = re.compile(r"^([a-h])(?:[.)]\s+(?=\S)|\s+(?=[A-Z]))")

OPTION = re.compile(r"^([A-E])[.)]?\s+(?=\S)")
NOISE = re.compile(
    r"^(chapter\s+\d|unit\s+[1-4]\b|area of study|isbn|©|copyright|"
    r"cambridge university press|uncorrected|sample pages|page\s+\d+|\d{1,4})\s*$",
    re.IGNORECASE,
)

# A mark allocation broken over a line break: "... longer term. (4" then
# "marks)". Word documents converted to PDF wrap wherever the column ends, so
# this is normal rather than exotic, and neither fragment matches MARKS_INLINE.
_MARKS_HEAD = re.compile(r"\(\s*\d+\s*$")
_MARKS_TAIL = re.compile(r"^\s*marks?\s*\)", re.IGNORECASE)


def rejoin_wrapped_marks(lines: list[str]) -> list[str]:
    """Put a mark allocation back together when the line break split it.

    Left alone, "(4" stays in the question text and the 4 marks go uncounted —
    which then sizes the answer space wrongly as well as printing a stray
    bracket on the sheet.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        tail = _MARKS_TAIL.match(nxt) if nxt is not None else None
        if tail and _MARKS_HEAD.search(line):
            out.append(f"{line.rstrip()} {nxt[:tail.end()].strip()}")
            rest = nxt[tail.end():].strip()
            if rest:
                out.append(rest)
            i += 2
            continue
        out.append(line)
        i += 1
    return out


def normalise_part(line: str) -> str:
    """Print every part the same way, whatever the book did.

    One publisher writes "a. Calculate ...", another "a Calculate ...". On a
    sheet that mixes questions from both books the second form reads as a typo,
    so the label is rewritten to "a." and the text follows it.
    """
    m = PART.match(line)
    if not m:
        return line
    return f"{m.group(1)}. {line[m.end():].strip()}"

# Online-resource callouts, which are not questions however they are laid out.
#
# Jacaranda's learnON titles print these between the real questions and in the
# same style — "Try out this Interactivity: Projectile motion (int-6799)" sits
# where question 4 should be — so the segmenter happily filed them as
# questions and students got a sheet telling them to go and watch a video.
# Edrolo and Cambridge do the same with QR codes and companion websites.
#
# Matched anywhere in the question, not just at the start: the callout often
# begins with a real-looking verb ("Complete this digital document ...").
ONLINE_RESOURCE = re.compile(
    r"learn\s?on|elesson|eworkbook|emodelling|ebookplus|"
    r"int-\d|ele-\d|doc-\d|ewbk-\d|"
    r"interactivit(y|ies)|digital document|digital doc|weblink|web link|"
    r"try out this|watch this (video|elesson)|explore more with|"
    r"scan the qr|qr code|companion website|online only|"
    r"in your learnon title|access (this|these) .{0,30}online",
    re.IGNORECASE)
# A bare section heading that introduces a block of them.
RESOURCE_HEADING = re.compile(
    r"^(resources|online resources|digital resources|learn\s?on)\s*:?\s*$",
    re.IGNORECASE)


def is_resource_note(text: str) -> bool:
    """True when this is a pointer to online material rather than a question.

    Deliberately not applied to a question that merely mentions a video or a
    website in its own scenario, which is why the markers are product names
    and asset codes ("int-6799") rather than words like "online".
    """
    return bool(text) and bool(ONLINE_RESOURCE.search(text))


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
        if is_resource_note(self.full_text):
            # A pointer to a video or an interactivity, laid out like a
            # question. Answering it is impossible and printing it wastes
            # half a sheet.
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


# How far into a page a running header or footer can sit, as a fraction of
# page height, and how many pages must share a line before it counts as
# furniture rather than content. Two is enough: the same words, in the margin,
# on two different pages is a masthead. Body text does not repeat verbatim.
MARGIN_BAND = 0.08
FURNITURE_PAGES = 2
FURNITURE_SHARE = 0.25


def _furniture(pages: dict[int, list], heights: dict[int, float]) -> set[str]:
    """Text repeated in the margins of many pages: mastheads and footers.

    "VCE PHYSICS UNITS 3 & 4" at the top of every page is not matchable by
    pattern — every publisher writes a different one — but it is trivially
    detectable by repetition. Without this the masthead of the following page
    is swept into the last question of the previous one, and the question
    prints with the book's title glued to the end of it.

    Only the top and bottom of the page are considered, so a phrase that
    genuinely recurs in the body ("Calculate the acceleration") is safe.
    """
    if len(pages) < 2:
        return set()
    seen: dict[str, set[int]] = {}
    for index, lines in pages.items():
        height = heights.get(index) or 0
        if not height:
            continue
        band = height * MARGIN_BAND
        for line in lines:
            if line.y0 > band and line.y1 < height - band:
                continue
            text = line.text.strip()
            if text:
                seen.setdefault(text, set()).add(index)
    threshold = max(FURNITURE_PAGES, int(len(pages) * FURNITURE_SHARE))
    return {text for text, on in seen.items() if len(on) >= threshold}


def _stream(doc, first: int = 0, last: int | None = None
            ) -> tuple[list[_Entry], dict[int, _PageInfo]]:
    """Every line in the book, in order, tagged with its page."""
    last = doc.page_count if last is None else min(last, doc.page_count)
    info: dict[int, _PageInfo] = {}
    lines_by_page: dict[int, list] = {}
    heights: dict[int, float] = {}
    for index in range(first, last):
        page = doc[index]
        info[index] = _PageInfo(bars=fraction_bars(page), height=page.rect.height)
        heights[index] = page.rect.height
        lines_by_page[index] = build_lines(page)

    furniture = _furniture(lines_by_page, heights)
    out: list[_Entry] = []
    for index in range(first, last):
        for line in lines_by_page[index]:
            if NOISE.match(line.text) or line.text.strip() in furniture:
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

    q_lines = rejoin_wrapped_marks([e.line.text for e in q_entries])
    provenance = None
    kept: list[str] = []
    for line in q_lines:
        p = PROVENANCE.match(line)
        if p:
            provenance = (p.group(1) or p.group(2)).strip()
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
            current = [normalise_part(line)]
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
