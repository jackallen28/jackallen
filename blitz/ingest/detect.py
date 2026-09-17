"""Work out what kind of book a PDF is, so the right extractor runs.

A Checkpoints book heads every question "Question 12/ 11". A textbook has
chapters, section headings, worked examples and review questions numbered
"1.", "2.". A VCAA exam paper has "SECTION A", "Question 3 (4 marks)" and an
official header. They need different segmentation, and guessing wrong produces
confident garbage — so the kind is detected from a sample of pages and reported,
and can be overridden.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .textflow import build_lines

CHECKPOINTS_HEADER = re.compile(r"^Question\s+\d+\s*/\s*\d+\s*$", re.IGNORECASE)
EXAM_SECTION = re.compile(r"^SECTION\s+[A-C]\b", re.IGNORECASE)
EXAM_QUESTION = re.compile(r"^Question\s+\d+\s*\(\d+\s*marks?\)", re.IGNORECASE)
VCAA_HEADER = re.compile(r"\bVCAA\b|Victorian Certificate of Education|written examination",
                         re.IGNORECASE)
TEXTBOOK_CUES = re.compile(
    r"^(chapter\s+\d+|\d+\.\d+\s+[A-Z]|worked example|review questions?|"
    r"chapter review|key (terms|concepts|ideas)|summary|learning (objectives|outcomes))",
    re.IGNORECASE)
NUMBERED = re.compile(r"^\s*\d{1,3}\s*[.)]\s+\S")


@dataclass
class Detection:
    kind: str                     # checkpoints | textbook | exam | unknown
    confidence: float             # 0..1
    evidence: dict[str, int]
    pages_sampled: int

    def summary(self) -> str:
        ev = ", ".join(f"{k}={v}" for k, v in sorted(self.evidence.items()) if v)
        return f"{self.kind} ({self.confidence:.0%}; {ev})"


def detect_kind(doc, sample: int = 40) -> Detection:
    """Sample pages spread through the book and count the structural cues."""
    n = doc.page_count
    if n == 0:
        return Detection("unknown", 0.0, {}, 0)
    step = max(1, n // sample)
    indices = list(range(0, n, step))[:sample]

    counts: Counter[str] = Counter()
    for i in indices:
        lines = build_lines(doc[i])
        for line in lines:
            t = line.text.strip()
            if CHECKPOINTS_HEADER.match(t):
                counts["checkpoints_headers"] += 1
            if EXAM_SECTION.match(t):
                counts["exam_sections"] += 1
            if EXAM_QUESTION.match(t):
                counts["exam_questions"] += 1
            if VCAA_HEADER.search(t):
                counts["vcaa_headers"] += 1
            if TEXTBOOK_CUES.match(t):
                counts["textbook_cues"] += 1
            if NUMBERED.match(t):
                counts["numbered_items"] += 1

    pages = len(indices)
    per_page = {k: v / pages for k, v in counts.items()}

    # Order matters: Checkpoints and exams also contain numbered items and the
    # odd heading, so the more specific signals are tested first.
    if per_page.get("checkpoints_headers", 0) >= 0.5:
        conf = min(1.0, per_page["checkpoints_headers"] / 1.5)
        return Detection("checkpoints", conf, dict(counts), pages)
    if counts["exam_sections"] or (counts["vcaa_headers"] and counts["exam_questions"]):
        conf = min(1.0, (counts["exam_sections"] + counts["exam_questions"]) / 6)
        return Detection("exam", max(conf, 0.5), dict(counts), pages)
    if per_page.get("textbook_cues", 0) >= 0.15 or (
            counts["textbook_cues"] >= 3 and per_page.get("numbered_items", 0) >= 0.3):
        conf = min(1.0, per_page.get("textbook_cues", 0) / 0.6 + 0.3)
        return Detection("textbook", conf, dict(counts), pages)
    if per_page.get("numbered_items", 0) >= 1.0:
        return Detection("textbook", 0.4, dict(counts), pages)
    return Detection("unknown", 0.0, dict(counts), pages)
