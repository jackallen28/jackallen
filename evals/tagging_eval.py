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


def sample_bank_items(subject_id: str = "physics"):
    """A held-out, dot-point-level labelled set.

    The sample bank's questions were written for this repo and hand-mapped to
    dot points before the lexicon existed, so they are independent of the
    tuning done against the Checkpoints set — and they are labelled at dot
    point level, which is a much harder target than area of study.
    """
    import yaml

    from blitz.corpus.sample import CORPUS_DIR

    doc = yaml.safe_load((CORPUS_DIR / f"sample_{subject_id}.yaml").read_text(
        encoding="utf-8"))
    for q in doc.get("questions", []):
        kk = q["kk"] if isinstance(q["kk"], str) else q["kk"][0]
        yield q, kk


def score_sample_bank(subject_id: str = "physics", use_model: bool = False) -> dict:
    """Precision at dot point AND area level on the held-out sample bank."""
    design = load_study_design(subject_id)
    items = list(sample_bank_items(subject_id))
    if use_model:
        tagger = ClaudeTagger(design)
        results = tagger.tag_all(
            [{"text": q["body"], "options": q.get("options"),
              "marks": q.get("marks")} for q, _ in items])
    else:
        tagger = KeywordTagger(design)
        results = [tagger.tag(q["body"], q.get("options"), q.get("marks"))
                   for q, _ in items]

    stats = {"total": len(items), "tagged": 0, "exact": 0, "same_area": 0,
             "rejected": 0, "mistakes": []}
    for (q, gold), result in zip(items, results):
        if result.rejected or not result.kk_ids:
            stats["rejected"] += 1
            continue
        stats["tagged"] += 1
        predicted = result.kk_ids[0]
        if predicted == gold:
            stats["exact"] += 1
            stats["same_area"] += 1
        elif area_of(design, predicted) == area_of(design, gold):
            stats["same_area"] += 1
            if len(stats["mistakes"]) < 6:
                stats["mistakes"].append((q["body"][:64], gold, predicted, "area ok"))
        elif len(stats["mistakes"]) < 6:
            stats["mistakes"].append((q["body"][:64], gold, predicted, "WRONG AREA"))

    tagged = stats["tagged"] or 1
    stats["exact_precision"] = stats["exact"] / tagged
    stats["area_precision"] = stats["same_area"] / tagged
    stats["coverage"] = stats["tagged"] / stats["total"]
    return stats


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


def score_pack(pack_path: Path, use_model: bool = False) -> dict:
    """Score the tagger on a question pack, at area-of-study level.

    A pack built by a model tags each question by chapter, and a chapter sits
    inside one area of study, so the pack's tags give area-level ground truth
    for free on a book the lexicon was never tuned against. This is the
    number to quote for the raw `blitz index` path on new material.
    """
    import json

    design = load_study_design("physics")
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    items = []
    for q in pack["questions"]:
        kk_ids = q.get("kk_ids") or []
        areas = {area_of(design, k) for k in kk_ids} - {None}
        if len(areas) != 1:
            continue                    # no single-area ground truth
        bits = [q.get("context") or "", q.get("stem") or ""]
        bits += [f"{p.get('label', '')}. {p.get('text', '')}" for p in q.get("parts") or []]
        items.append((" ".join(b for b in bits if b), q.get("options") or [],
                      q.get("marks"), next(iter(areas))))
    if not items:
        raise SystemExit(f"No single-area questions in {pack_path}")

    if use_model:
        tagger = ClaudeTagger(design)
        results = tagger.tag_all([{"text": t, "options": o, "marks": m}
                                  for t, o, m, _ in items])
    else:
        tagger = KeywordTagger(design)
        results = [tagger.tag(t, o, m) for t, o, m, _ in items]

    stats = {"total": len(items), "tagged": 0, "correct": 0, "wrong": 0,
             "rejected": 0}
    by_area: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    confusions: dict[tuple[str, str], int] = defaultdict(int)
    for (text, _, _, gold), result in zip(items, results):
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
            confusions[(gold, predicted)] += 1
    stats["precision"] = stats["correct"] / stats["tagged"] if stats["tagged"] else 0.0
    stats["coverage"] = stats["tagged"] / stats["total"]
    stats["by_area"] = {k: (v[0], v[1]) for k, v in by_area.items()}
    stats["confusions"] = sorted(confusions.items(), key=lambda kv: -kv[1])[:6]
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf", type=Path, nargs="?",
                    help="a Checkpoints PDF to score (area-of-study level)")
    ap.add_argument("--samples", action="store_true",
                    help="score the held-out sample bank at dot point level")
    ap.add_argument("--pack", type=Path,
                    help="score against a question pack's chapter-level tags "
                         "(area-of-study level; the honest number for a book "
                         "the lexicon was not tuned on)")
    ap.add_argument("--model", action="store_true",
                    help="score the Claude tagger instead of the keyword fallback")
    args = ap.parse_args()

    if args.pack:
        s = score_pack(args.pack, use_model=args.model)
        name = "Claude tagger" if args.model else "keyword tagger"
        print(f"\n{name} on {args.pack.name} (area of study level, pack tags as truth)")
        print(f"  questions with one area : {s['total']}")
        print(f"  tagged                  : {s['tagged']}  ({s['coverage']:.0%} coverage)")
        print(f"  left untagged           : {s['rejected']}")
        print(f"  right area of study     : {s['correct']}/{s['tagged']} "
              f"({s['precision']:.0%})")
        print("  by area:")
        for area, (ok, n) in sorted(s["by_area"].items()):
            print(f"    {area:18} {ok:4}/{n:<4} {ok / n:.0%}")
        if s["confusions"]:
            print("  most common confusions (truth -> predicted):")
            for (gold, pred), n in s["confusions"]:
                print(f"    {gold} -> {pred}: {n}")
        return 0

    if args.samples or args.pdf is None:
        s = score_sample_bank(use_model=args.model)
        name = "Claude tagger" if args.model else "keyword tagger"
        print(f"\n{name} on the held-out sample bank (dot point level)")
        print(f"  labelled questions   : {s['total']}")
        print(f"  tagged               : {s['tagged']}  ({s['coverage']:.0%})")
        print(f"  left untagged        : {s['rejected']}")
        print(f"  EXACT dot point      : {s['exact']}/{s['tagged']} "
              f"({s['exact_precision']:.0%})")
        print(f"  right area of study  : {s['same_area']}/{s['tagged']} "
              f"({s['area_precision']:.0%})")
        if s["mistakes"]:
            print("\n  misses:")
            for text, gold, predicted, kind in s["mistakes"]:
                print(f"    [{kind}] {text}…")
                print(f"        gold={gold}  predicted={predicted}")
        if args.pdf is None:
            return 0

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
