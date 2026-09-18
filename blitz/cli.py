"""Command line entry points.

    blitz init                      create the index and load the sample bank
    blitz subjects                  list subjects and how verified they are
    blitz index <pdf> ...           study design + book in, index out (start here)
    blitz extract-pack <pdf>        build a draft pack from a PDF, no model
    blitz import-pack <json>        load a curated question pack (preferred)
    blitz dot-points <subject>      the dot point ids a pack should tag against
    blitz ingest <pdf> ...          index a PDF heuristically (no pack available)
    blitz coverage <subject>        show questions held per dot point
    blitz generate <subject> ...    build a sheet from the command line
    blitz serve                     run the local web UI
"""

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

from . import db
from .config import OUT_DIR, ensure_dirs
from .corpus.sample import load_all_samples
from .models import SheetSpec
from .picker import build_plan
from .render import render_sheet
from .studydesign import list_subjects, load_study_design


def cmd_init(args) -> int:
    ensure_dirs()
    with db.session() as conn:
        counts = load_all_samples(conn)
    print(f"index ready at {db.DB_PATH}")
    for subject, n in counts.items():
        print(f"  {subject}: {n} sample questions loaded")
    print("\nIngest your own sources next, e.g.:")
    print("  blitz ingest sources/physics-checkpoints.pdf \\")
    print("      --subject physics --source-id physics-checkpoints \\")
    print("      --kind checkpoints --page-offset -2")
    return 0


def cmd_subjects(args) -> int:
    designs = list_subjects()
    if not designs:
        print("no study designs installed")
        return 1
    with db.session() as conn:
        for d in designs:
            held = db.coverage(conn, d.subject_id)
            total_kk = len(d.all_key_knowledge())
            covered = sum(1 for kk in d.all_key_knowledge() if held.get(kk.id))
            flag = "" if d.fully_verified else "  [study design NOT yet imported from VCAA]"
            print(f"{d.subject_id:22} {d.subject_name}{flag}")
            print(f"{'':22} {len(d.units)} units, {total_kk} dot points, "
                  f"{covered} with at least one question")
    return 0


def cmd_ingest(args) -> int:
    ensure_dirs()
    source_id = args.source_id or Path(args.pdf).stem.lower().replace(" ", "-")
    from .ingest import ingest_pdf

    with db.session() as conn:
        report = ingest_pdf(
            conn, args.pdf,
            source_id=source_id,
            subject_id=args.subject,
            kind=args.kind,
            title=args.title,
            edition=args.edition,
            page_offset=args.page_offset,
            pages=(args.first_page, args.last_page) if args.last_page else None,
            use_model=not args.no_model,
        )
    if report.untagged_samples:
        print("\n  examples of text that matched no dot point:")
        for s in report.untagged_samples:
            print(f"    · {s}…")
    return 0


def cmd_coverage(args) -> int:
    from .ingest.pipeline import coverage_report

    design = load_study_design(args.subject)
    with db.session() as conn:
        rows = coverage_report(conn, design)
        content = db.passage_coverage(conn, args.subject)
        by_source = db.coverage_by_source(conn, args.subject) if args.by_source else {}
    sources = sorted({src for _, src in by_source})
    current = None
    thin = 0
    if sources:
        # One column per source, so two indexes of the same book (a model's
        # pack and blitz index on the PDF, say) can be read side by side.
        heads = "".join(f"{s[-14:]:>15}" for s in sources)
        print(f"{'Qs':>4} {'text':>5}{heads}   dot point")
    else:
        print(f"{'Qs':>4} {'text':>5}   {'':24}  dot point")
    for row in rows:
        if row["aos"] != current:
            current = row["aos"]
            print(f"\n{current}")
        n_text = content.get(row["kk_id"], 0)
        star = "" if row["verified"] else " *"
        if row["count"] < args.thin:
            thin += 1
        if sources:
            cols = "".join(f"{by_source.get((row['kk_id'], s), 0):>15}" for s in sources)
            print(f"  {row['count']:4} {n_text:5}{cols}   {row['label']}{star}")
        else:
            bar = "█" * min(row["count"], 20) + "░" * min(n_text, 4)
            print(f"  {row['count']:4} {n_text:5}   {bar:<24}  {row['label']}{star}")
    print(f"\n{thin} dot point(s) hold fewer than {args.thin} questions.  "
          f"(█ questions, ░ teaching sections)")
    if not design.fully_verified:
        print("* wording not yet imported from the official VCAA study design.")
    return 0


def cmd_generate(args) -> int:
    ensure_dirs()
    design = load_study_design(args.subject)

    kk_ids = args.kk or []
    if args.aos:
        for aos_id in args.aos:
            kk_ids.extend(kk.id for kk in design.area(aos_id).key_knowledge)
    if not kk_ids:
        print("Nothing selected. Pass --aos <id> or --kk <id> (see `blitz coverage`).")
        return 2

    spec = SheetSpec(
        subject_id=args.subject,
        kk_ids=list(dict.fromkeys(kk_ids)),
        question_type_ids=args.type or [],
        notes=args.notes or "",
        title=args.title or "",
        difficulty=args.difficulty,
        include_solutions=not args.no_solutions,
        allow_generated=not args.no_generated,
        seed=args.seed,
    )

    with db.session() as conn:
        plan = build_plan(conn, spec, design)
        if not plan.questions:
            for w in plan.warnings:
                print(f"  ! {w}")
            return 1
        out = Path(args.out or OUT_DIR / f"blitz-{args.subject}-{uuid.uuid4().hex[:6]}.pdf")
        result = render_sheet(plan, out, design)

    print(f"wrote {result['path']}")
    print(f"  {result['questions']} questions, {result['total_marks']} marks, "
          f"{result['total_pages']} pages total "
          f"({result['question_pages']} of questions)")
    for w in plan.warnings:
        print(f"  ! {w}")
    if result["dropped"]:
        print(f"  {len(result['dropped'])} question(s) dropped to hold two pages.")
    return 0


def cmd_import_pack(args) -> int:
    """Load a curated question pack (docs/question-pack-schema.md)."""
    ensure_dirs()
    from .ingest.pack import import_pack

    with db.session() as conn:
        report = import_pack(conn, args.pack, dry_run=args.dry_run,
                             refine=not args.keep_pack_tags)
    if report.ok and not args.dry_run:
        print("\nNext: blitz coverage " + (report.subject_id or "<subject>"))
    return 0 if report.ok else 1


def cmd_index(args) -> int:
    """A study design and a book in, an index out. No model, no network."""
    ensure_dirs()
    from .ingest.index import index_book

    source_id = args.source_id or Path(args.pdf).stem.lower().replace(" ", "-").replace("_", "-")
    with db.session() as conn:
        report = index_book(
            conn, args.pdf,
            subject_id=args.subject, source_id=source_id,
            title=args.title, kind=args.kind, edition=args.edition,
            page_offset=args.page_offset,
            pages=(args.first_page, args.last_page) if args.last_page else None,
            study_design_pdf=args.study_design,
            include_content=not args.no_content,
        )
    print(f"\nNext: blitz coverage {args.subject}")
    return 0 if report.questions_indexed or report.passages_indexed else 1


def cmd_extract_pack(args) -> int:
    """Build a draft pack from a PDF, deterministically. No model, no network."""
    import json as _json

    from .ingest.draft import build_draft, review_queue, write_draft

    pack, report = build_draft(
        args.pdf, subject_id=args.subject, source_id=args.source_id,
        title=args.title, kind=args.kind, edition=args.edition,
        pages=(args.first_page, args.last_page) if args.last_page else None,
    )
    out = write_draft(pack, args.out)
    print(f"\nwrote {out}")
    print(report.summary())

    queue = review_queue(pack)
    if queue and args.review_out:
        Path(args.review_out).write_text(
            _json.dumps(queue, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"\nwrote {args.review_out} — {len(queue)} entries needing review")
        print("Hand that file to a person or a model; leave the rest alone.")
    print("\nThen: blitz import-pack " + str(out) + " --dry-run")
    return 0


def cmd_dot_points(args) -> int:
    """The authoritative dot point ids, for whatever is building a pack."""
    import json as _json

    from .corpus.sample import fingerprint

    design = load_study_design(args.subject)
    if args.json:
        payload = {
            "subject_id": design.subject_id,
            "subject_name": design.subject_name,
            "accreditation": design.accreditation,
            "study_design_fingerprint": fingerprint(design),
            "verified": design.fully_verified,
            "question_types": [
                {"id": qt.id, "label": qt.label, "description": qt.description}
                for qt in design.question_types
            ],
            "dot_points": [
                {
                    "id": kk.id,
                    "unit": unit.number,
                    "area_of_study": area.id,
                    "area_title": area.title,
                    "text": kk.text,
                    "short": kk.display,
                }
                for unit in design.units
                for area in unit.areas_of_study
                for kk in area.key_knowledge
            ],
        }
        print(_json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    for unit in design.units:
        print(f"\nUnit {unit.number}: {unit.title}")
        for area in unit.areas_of_study:
            print(f"  {area.id} — {area.title}")
            for kk in area.key_knowledge:
                print(f"    {kk.id}  {kk.text[:90]}")
    print(f"\nfingerprint: {fingerprint(design)}")
    return 0


def cmd_serve(args) -> int:
    import os

    import uvicorn

    from .server.auth import MissingPassword, check_startup, password

    ensure_dirs()
    # A platform (Render, Fly, a container) hands the port in the environment
    # and expects the app on 0.0.0.0. Locally, neither is true.
    port = int(os.environ.get("PORT") or args.port)
    host = args.host
    if os.environ.get("PORT") and host == "127.0.0.1":
        host = "0.0.0.0"

    try:
        check_startup(host)
    except MissingPassword as exc:
        print(f"\n{exc}\n")
        return 2

    where = "http://127.0.0.1" if host in ("127.0.0.1", "localhost") else f"http://{host}"
    lock = " (password required)" if password() else ""
    print(f"Blitz is running at {where}:{port}{lock}")
    print(f"  make a sheet     {where}:{port}/")
    print(f"  index materials  {where}:{port}/index")
    if args.open:
        import threading
        import webbrowser

        url = f"{where}:{port}/{args.open if isinstance(args.open, str) else ''}"
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run("blitz.server.app:app", host=host, port=port,
                reload=args.reload, log_level="warning")
    return 0


def cmd_import_study_design(args) -> int:
    from .studydesign.importer import import_study_design

    path = import_study_design(args.pdf, args.subject, dry_run=args.dry_run)
    print(f"{'would write' if args.dry_run else 'wrote'} {path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="blitz", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="create the index and load the sample bank"
                   ).set_defaults(func=cmd_init)
    sub.add_parser("subjects", help="list subjects").set_defaults(func=cmd_subjects)

    ing = sub.add_parser("ingest", help="index one of your own PDFs")
    ing.add_argument("pdf")
    ing.add_argument("--subject", required=True)
    ing.add_argument("--source-id")
    ing.add_argument("--kind", default="checkpoints",
                     choices=["checkpoints", "textbook", "vcaa-exam", "other"])
    ing.add_argument("--title")
    ing.add_argument("--edition")
    ing.add_argument("--page-offset", type=int, default=0,
                     help="printed page number minus PDF page index")
    ing.add_argument("--first-page", type=int, default=0)
    ing.add_argument("--last-page", type=int)
    ing.add_argument("--no-model", action="store_true",
                     help="tag with keywords only, never call the API")
    ing.set_defaults(func=cmd_ingest)

    cov = sub.add_parser("coverage", help="questions held per dot point")
    cov.add_argument("subject")
    cov.add_argument("--thin", type=int, default=3)
    cov.add_argument("--by-source", action="store_true",
                     help="one column per source, to compare two indexes of "
                          "the same book side by side")
    cov.set_defaults(func=cmd_coverage)

    gen = sub.add_parser("generate", help="build a sheet")
    gen.add_argument("subject")
    gen.add_argument("--aos", action="append", help="include a whole area of study")
    gen.add_argument("--kk", action="append", help="include one dot point")
    gen.add_argument("--type", action="append", help="restrict to a question type")
    gen.add_argument("--notes", help="free-text nudge, same as the notes box")
    gen.add_argument("--title")
    gen.add_argument("--difficulty", default="mixed",
                     choices=["easy", "mixed", "hard"])
    gen.add_argument("--no-solutions", action="store_true")
    gen.add_argument("--no-generated", action="store_true",
                     help="only use questions from real sources")
    gen.add_argument("--seed", type=int)
    gen.add_argument("--out")
    gen.set_defaults(func=cmd_generate)

    imp = sub.add_parser("import-study-design",
                         help="rebuild a subject's YAML from the VCAA PDF or Word file")
    imp.add_argument("pdf", help="the study design as .pdf or .docx")
    imp.add_argument("--subject", required=True)
    imp.add_argument("--dry-run", action="store_true")
    imp.set_defaults(func=cmd_import_study_design)

    pack = sub.add_parser("import-pack",
                          help="load a curated question pack (JSON)")
    pack.add_argument("pack")
    pack.add_argument("--dry-run", action="store_true",
                      help="validate only; write nothing")
    pack.add_argument("--keep-pack-tags", action="store_true",
                      help="file questions under the pack's dot points exactly "
                           "as given, without narrowing chapter-level tags to "
                           "the dot point each question's text names")
    pack.set_defaults(func=cmd_import_pack)

    ix = sub.add_parser(
        "index",
        help="study design + book in, index out (questions AND content)")
    ix.add_argument("pdf", help="a Checkpoints book, textbook, exam paper or "
                                "worksheet, as .pdf or .docx")
    ix.add_argument("--subject", required=True)
    ix.add_argument("--study-design", metavar="PDF",
                    help="import the VCAA study design first, from this PDF")
    ix.add_argument("--source-id", help="stable id; defaults to the filename")
    ix.add_argument("--title", help="printed in citations; defaults to the filename")
    ix.add_argument("--kind", default="auto",
                    choices=["auto", "checkpoints", "textbook", "exam"],
                    help="what kind of book; auto-detected by default")
    ix.add_argument("--edition")
    ix.add_argument("--page-offset", type=int, default=0,
                    help="printed page number minus PDF page index")
    ix.add_argument("--first-page", type=int, default=0)
    ix.add_argument("--last-page", type=int)
    ix.add_argument("--no-content", action="store_true",
                    help="questions only; skip indexing the teaching sections")
    ix.set_defaults(func=cmd_index)

    xp = sub.add_parser("extract-pack",
                        help="build a draft pack from a PDF (no model)")
    xp.add_argument("pdf")
    xp.add_argument("--subject", required=True)
    xp.add_argument("--source-id", required=True)
    xp.add_argument("--title")
    xp.add_argument("--kind", default="checkpoints",
                    choices=["checkpoints", "textbook", "vcaa-exam", "other"])
    xp.add_argument("--edition")
    xp.add_argument("--first-page", type=int, default=0)
    xp.add_argument("--last-page", type=int)
    xp.add_argument("-o", "--out", required=True, help="where to write the pack")
    xp.add_argument("--review-out",
                    help="also write just the entries needing review")
    xp.set_defaults(func=cmd_extract_pack)

    dots = sub.add_parser("dot-points",
                          help="list dot point ids, for building a pack")
    dots.add_argument("subject")
    dots.add_argument("--json", action="store_true",
                      help="machine-readable, including the design fingerprint")
    dots.set_defaults(func=cmd_dot_points)

    srv = sub.add_parser("serve", help="run the local web UI")
    srv.add_argument("--host", default="127.0.0.1")
    srv.add_argument("--port", type=int, default=8712)
    srv.add_argument("--reload", action="store_true")
    srv.add_argument("--open", nargs="?", const="", metavar="PAGE",
                     help="open the browser once running; --open index goes "
                          "straight to the indexing page")
    srv.set_defaults(func=cmd_serve)

    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
