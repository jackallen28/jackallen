"""Measure how often the tagger files a question under the right area of study.

Tagging quality is the difference between a revision sheet that matches what you
asked for and one that quietly hands you relativity when you asked for
projectiles. It is not something to judge by reading a few rows, so this scores
it.

Ground truth comes from the book itself. Checkpoints prints the page each
question sits on ("Question 12/ 11"), and pages cluster by chapter, so a page
number maps cleanly onto an area of study. That gives a labelled set for free,
with no hand-annotation to drift out of date.

Usage:
    python evals/tagging_eval.py sources/physics-checkpoints-sample.pdf
    python evals/tagging_eval.py <pdf> --model      # score the Claude tagger
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pymupdf  # noqa: E402

from blitz.ingest.segment import segment_document  # noqa: E402
from blitz.ingest.tag import ClaudeTagger, KeywordTagger  # noqa: E402
from blitz.studydesign import load_study_design  # noqa: E402

# Printed page in the book -> the area of study those questions assess.
# Taken from the chapter each page falls in, not from the tagger's output.
PAGE_TO_AOS = {
    "11": "physics-u3-aos1",   # motion basics: kinematics, projectiles
    "22": "physics-u3-aos1",   # motion graphs, friction, acceleration
    "14": "physics-u4-aos1",   # matter waves, de Broglie, electron diffraction
    "21": "physics-u4-aos1",   # photons, momentum of light, photoelectric
    "35": "physics-u4-aos1",   # X-ray and electron diffraction
    "49": "physics-u4-aos1",   # photoelectric effect experiments
}


def labelled(pdf: Path):
    doc = pymupdf.open(pdf)
    try:
        for q in segment_document(doc):
            gold = PAGE_TO_AOS.get(q.printed_page or "")
            if gold:
                yield q, gold
    finally:
        doc.close()


def area_of(design, kk_id: str) -> str | None:
    try:
        return design.area_of(kk_id).id
    except KeyError:
        return None


def score(pdf: Path, use_model: bool = False) -> dict:
    design = load_study_design("physics")
    items = list(labelled(pdf))
    if not items:
        raise SystemExit(f"No labelled questions found in {pdf}. "
                         "Is this the Checkpoints sample?")

    if use_model:
        tagger = ClaudeTagger(design)
        payload = [{"text": q.full_text, "options": q.options, "marks": q.marks}
                   for q, _ in items]
        results = tagger.tag_all(payload)
    else:
        tagger = KeywordTagger(design)
        results = [tagger.tag(q.full_text, q.options, q.marks) for q, _ in items]

    stats = {"total": len(items), "tagged": 0, "correct": 0, "wrong": 0,
             "rejected": 0}
    by_area: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    mistakes = []

    for (q, gold), result in zip(items, results):
        if result.rejected or not result.kk_ids:
            stats["rejected"] += 1
            continue
        stats["tagged"] += 1
        predicted = area_of(design, result.kk_ids[0])
        by_area[gold][1] += 1
        if predicted == gold:
            stats["correct"] += 1
            by_area[gold][0] += 1
        else:
            stats["wrong"] += 1
            if len(mistakes) < 8:
                mistakes.append((q.full_text[:70], gold, predicted, result.kk_ids[0]))

    stats["precision"] = stats["correct"] / stats["tagged"] if stats["tagged"] else 0.0
    stats["coverage"] = stats["tagged"] / stats["total"]
    stats["by_area"] = {k: (v[0], v[1]) for k, v in by_area.items()}
    stats["mistakes"] = mistakes
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--model", action="store_true",
                    help="score the Claude tagger instead of the keyword fallback")
    args = ap.parse_args()

    stats = score(args.pdf, use_model=args.model)
    name = "Claude tagger" if args.model else "keyword tagger"
    print(f"\n{name} on {args.pdf.name}")
    print(f"  labelled questions : {stats['total']}")
    print(f"  tagged             : {stats['tagged']}  "
          f"({stats['coverage']:.0%} coverage)")
    print(f"  left untagged      : {stats['rejected']}")
    print(f"  correct area       : {stats['correct']}")
    print(f"  wrong area         : {stats['wrong']}")
    print(f"  PRECISION          : {stats['precision']:.0%}")

    if stats["by_area"]:
        print("\n  per area of study (correct/tagged):")
        for area, (ok, n) in sorted(stats["by_area"].items()):
            print(f"    {area}: {ok}/{n}")

    if stats["mistakes"]:
        print("\n  examples of misfiled questions:")
        for text, gold, predicted, kk in stats["mistakes"]:
            print(f"    · {text}…")
            print(f"        gold={gold}  predicted={predicted} ({kk})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
