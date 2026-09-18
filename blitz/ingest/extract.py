"""Pull text, figures and page crops out of a source PDF with PyMuPDF.

The important trick for this tool is `crop`: when a question depends on a
diagram, we take a real screenshot of the region of the real page rather than
trying to re-draw it. Checkpoints figures in particular are unreproducible —
circuit diagrams, field-line sketches, experimental set-ups — and a crop is both
more faithful and far cheaper than regenerating them.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # PyMuPDF < 1.24.3
    import fitz

from ..config import CROP_ZOOM, CROPS_DIR


@dataclass
class Block:
    """A text block with its position on the page."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    block_no: int

    @property
    def rect(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class PageContent:
    index: int              # 0-based PDF page index
    printed: str | None     # page number as printed on the page, if we found one
    text: str
    blocks: list[Block] = field(default_factory=list)
    drawings: list[tuple[float, float, float, float]] = field(default_factory=list)
    images: list[tuple[float, float, float, float]] = field(default_factory=list)
    width: float = 0.0
    height: float = 0.0

    @property
    def figure_regions(self) -> list[tuple[float, float, float, float]]:
        """Candidate diagram areas: embedded images plus dense vector clusters."""
        return _merge_rects(self.images + _cluster(self.drawings))


class SourceError(Exception):
    """A source file Blitz cannot read, with something the person can do.

    Everything that reaches a teacher goes through here. Raw PyMuPDF errors
    are accurate and useless: "Failed to open file ... as type pdf" is a stack
    trace to a person holding a photocopied SAC.
    """


def open_pdf(path: str | Path) -> fitz.Document:
    """Open a PDF, or explain in plain words why it cannot be opened."""
    path = Path(path)
    if not path.exists():
        raise SourceError(f"There is no file at {path}.")
    if path.stat().st_size == 0:
        raise SourceError(
            f"{path.name} is empty (0 bytes). It may have failed to download "
            "or copy — try saving it again.")
    try:
        doc = fitz.open(str(path))
    except Exception as exc:                     # noqa: BLE001 - reported, not swallowed
        raise SourceError(
            f"{path.name} could not be opened as a PDF. It may be damaged, or "
            f"it may not really be a PDF despite its name.\n"
            f"    Try opening it in Preview and re-saving it as PDF.\n"
            f"    ({type(exc).__name__}: {exc})") from exc
    if doc.needs_pass:
        doc.close()
        raise SourceError(
            f"{path.name} is password-protected, so its text cannot be read.\n"
            "    Open it, enter the password, and save an unprotected copy.")
    if doc.page_count == 0:
        doc.close()
        raise SourceError(f"{path.name} has no pages in it.")
    return doc


# A page with a picture and essentially no text is a photocopy. Schools have a
# lot of them, and they extract to nothing at all with no explanation.
SCAN_CHARS_PER_PAGE = 60


def looks_scanned(doc: fitz.Document, sample: int = 12) -> bool:
    """True when the PDF is images of pages rather than text."""
    pages = min(sample, doc.page_count)
    if not pages:
        return False
    step = max(1, doc.page_count // pages)
    checked = chars = 0
    for i in range(0, doc.page_count, step):
        if checked >= pages:
            break
        checked += 1
        try:
            chars += len(doc[i].get_text("text").strip())
        except Exception:                        # noqa: BLE001 - a bad page is not fatal
            continue
    return checked > 0 and chars / checked < SCAN_CHARS_PER_PAGE


def read_page(doc: fitz.Document, index: int, page_offset: int = 0) -> PageContent:
    return read_page_content(doc[index], index=index, page_offset=page_offset)


def read_page_content(page, index: int | None = None,
                      page_offset: int = 0) -> PageContent:
    index = page.number if index is None else index
    raw = page.get_text("blocks")
    blocks = [
        Block(text=b[4].strip(), x0=b[0], y0=b[1], x1=b[2], y1=b[3], block_no=int(b[5]))
        for b in sorted(raw, key=lambda b: (round(b[1], 1), b[0]))
        if isinstance(b[4], str) and b[4].strip()
    ]

    images: list[tuple[float, float, float, float]] = []
    for info in page.get_images(full=True):
        try:
            for r in page.get_image_rects(info[0]):
                images.append((r.x0, r.y0, r.x1, r.y1))
        except Exception:
            continue

    drawings: list[tuple[float, float, float, float]] = []
    try:
        for d in page.get_drawings():
            r = d.get("rect")
            if r is not None and r.width > 4 and r.height > 4:
                drawings.append((r.x0, r.y0, r.x1, r.y1))
    except Exception:
        pass

    printed = str(index + 1 + page_offset) if page_offset is not None else None
    return PageContent(
        index=index,
        printed=printed,
        text=page.get_text("text"),
        blocks=blocks,
        drawings=drawings,
        images=images,
        width=page.rect.width,
        height=page.rect.height,
    )


def crop(
    doc: fitz.Document,
    page_index: int,
    rect: tuple[float, float, float, float],
    tag: str,
    pad: float = 6.0,
    zoom: float = CROP_ZOOM,
    out_dir: Path | None = None,
) -> str | None:
    """Render a region of a page to PNG and return its path.

    Returns None rather than raising when the region is degenerate — a bad crop
    should cost us one figure, not the whole ingest.
    """
    out_dir = Path(out_dir or CROPS_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    page = doc[page_index]
    x0, y0, x1, y1 = rect
    # Check the region BEFORE padding — otherwise the padding inflates a 1x1
    # sliver past the minimum and we save a crop of nothing.
    if (x1 - x0) < 8 or (y1 - y0) < 8:
        return None
    r = fitz.Rect(x0 - pad, y0 - pad, x1 + pad, y1 + pad) & page.rect
    if r.is_empty or r.width < 8 or r.height < 8:
        return None

    digest = hashlib.sha1(
        f"{tag}:{page_index}:{r.x0:.1f},{r.y0:.1f},{r.x1:.1f},{r.y1:.1f}".encode()
    ).hexdigest()[:16]
    path = out_dir / f"{digest}.png"
    if path.exists():
        return str(path)

    try:
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=r, alpha=False)
        pix.save(str(path))
    except Exception:
        return None
    return str(path)


def _merge_rects(
    rects: list[tuple[float, float, float, float]], gap: float = 12.0
) -> list[tuple[float, float, float, float]]:
    """Merge overlapping or near-touching rectangles into single figure regions."""
    out: list[list[float]] = []
    for r in sorted(rects, key=lambda r: (r[1], r[0])):
        placed = False
        for o in out:
            if (r[0] <= o[2] + gap and o[0] <= r[2] + gap
                    and r[1] <= o[3] + gap and o[1] <= r[3] + gap):
                o[0], o[1] = min(o[0], r[0]), min(o[1], r[1])
                o[2], o[3] = max(o[2], r[2]), max(o[3], r[3])
                placed = True
                break
        if not placed:
            out.append(list(r))
    merged = [tuple(o) for o in out]
    # Drop slivers — rules, underlines and table borders aren't figures.
    return [r for r in merged if (r[2] - r[0]) > 40 and (r[3] - r[1]) > 30]


def _cluster(
    rects: list[tuple[float, float, float, float]], min_parts: int = 4
) -> list[tuple[float, float, float, float]]:
    """A diagram drawn in vector strokes shows up as many small rects together."""
    if len(rects) < min_parts:
        return []
    merged = _merge_rects(rects, gap=14.0)
    return [
        r for r in merged
        if sum(1 for s in rects if _inside(s, r)) >= min_parts
    ]


def _inside(inner, outer) -> bool:
    return (inner[0] >= outer[0] - 1 and inner[1] >= outer[1] - 1
            and inner[2] <= outer[2] + 1 and inner[3] <= outer[3] + 1)
