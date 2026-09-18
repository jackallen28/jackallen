"""The indexing job behind the "Index materials" page.

A browser upload lands files in sources/<subject>/uploads/<stamp>/; the job
then does what the Mac script does from the command line: import the study
design if one came with the upload, import every question pack, index every
PDF and Word file, and write the result out as a folder plus a zip. It runs
in a thread because a book takes a minute and the page polls for progress.
"""

from __future__ import annotations

import json
import re
import shutil
import threading
import traceback
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .. import db
from ..config import EXPORTS_DIR, SOURCES_DIR

_JOBS: dict[str, "IndexJob"] = {}
_LOCK = threading.Lock()

BOOK_SUFFIXES = (".pdf", ".docx")


@dataclass
class IndexJob:
    id: str
    subject_id: str
    folder: Path
    study_design: Path | None = None
    subject_name: str | None = None
    context: list[Path] = field(default_factory=list)
    status: str = "queued"          # queued | running | done | failed
    log: list[str] = field(default_factory=list)
    result: dict = field(default_factory=dict)
    error: str | None = None

    def say(self, line: str) -> None:
        self.log.append(line)

    def snapshot(self) -> dict:
        return {"id": self.id, "subject_id": self.subject_id, "status": self.status,
                "log": list(self.log), "result": dict(self.result),
                "error": self.error}


def get_job(job_id: str) -> IndexJob | None:
    return _JOBS.get(job_id)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s or "material"


def _safe_extract(zip_path: Path, into: Path) -> int:
    """Unzip, refusing paths that would escape the target folder."""
    n = 0
    with zipfile.ZipFile(zip_path) as zf:
        for member in zf.infolist():
            name = member.filename
            if member.is_dir() or name.startswith("__MACOSX") or "/." in f"/{name}":
                continue
            target = (into / name).resolve()
            if not str(target).startswith(str(into.resolve())):
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, target.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            n += 1
    return n


def stage_uploads(subject_id: str, uploads: list[tuple[str, bytes]]) -> Path:
    """Write uploaded files under sources/<subject>/uploads/<stamp>/, unzipping zips."""
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    folder = SOURCES_DIR / subject_id / "uploads" / stamp
    folder.mkdir(parents=True, exist_ok=True)
    for filename, data in uploads:
        name = Path(filename).name or "upload"
        dest = folder / name
        dest.write_bytes(data)
        if dest.suffix.lower() == ".zip":
            into = folder / dest.stem
            into.mkdir(exist_ok=True)
            _safe_extract(dest, into)
            dest.unlink()
    return folder


def is_pack(path: Path) -> bool:
    if path.suffix.lower() != ".json":
        return False
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:4000]
    except OSError:
        return False
    return '"subject_id"' in head and '"questions"' in path.read_text(
        encoding="utf-8", errors="ignore")


def find_materials(folder: Path) -> tuple[list[Path], list[Path]]:
    """(packs, books) anywhere under the folder, in a stable order."""
    packs, books = [], []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.stem == "study-design":
            continue                      # staged beside the materials, not one of them
        if path.suffix.lower() in BOOK_SUFFIXES:
            books.append(path)
        elif is_pack(path):
            packs.append(path)
    return packs, books


def start(subject_id: str, folder: Path, study_design: Path | None = None,
          subject_name: str | None = None,
          context: list[Path] | None = None) -> IndexJob:
    job = IndexJob(id=uuid.uuid4().hex[:10], subject_id=subject_id, folder=folder,
                   study_design=study_design, subject_name=subject_name,
                   context=list(context or []))
    with _LOCK:
        _JOBS[job.id] = job
    threading.Thread(target=_run, args=(job,), daemon=True).start()
    return job


def _run(job: IndexJob) -> None:
    from ..ingest.extract import SourceError
    from ..studydesign.importer import EmptyStudyDesign

    job.status = "running"
    try:
        _index(job)
        job.status = "done"
    except (SourceError, EmptyStudyDesign) as exc:
        # Already written for a person to read. Prefixing "EmptyStudyDesign:"
        # and appending a stack trace makes it look like a crash instead of
        # like the answer, which it is.
        job.error = str(exc)
        job.say(f"STOPPED. {exc}")
        job.status = "failed"
    except Exception as exc:                      # surfaced on the page, not lost
        job.error = f"{type(exc).__name__}: {exc}"
        job.say(f"ERROR {job.error}")
        job.log.append(traceback.format_exc(limit=3))
        job.status = "failed"


def _index(job: IndexJob) -> None:
    from ..export import export_subject
    from ..ingest.extract import SourceError
    from ..ingest.index import index_book
    from ..ingest.pack import import_pack
    from ..studydesign.loader import load_study_design

    say = job.say
    if job.study_design is not None:
        from ..studydesign.importer import import_study_design

        say(f"Study design: {job.study_design.name}")
        out = import_study_design(job.study_design, job.subject_id,
                                  subject_name=job.subject_name)
        load_study_design.cache_clear()
        say(f"  imported → {out.name}")
        from ..guide import write_subject_guide

        guide = write_subject_guide(job.subject_id)[0]
        say(f"  dot points and indexing notes → {guide}")
        from ..setup import adopt_shipped_lexicon

        adopted = adopt_shipped_lexicon(job.subject_id)
        if adopted:
            say(f"  concept lexicon for {adopted} dot points came with it")
    design = load_study_design(job.subject_id)
    say(f"Subject: {design.subject_name} "
        f"({'verified' if design.fully_verified else 'draft wording'})")

    # Context documents go in before anything is indexed, so a concept
    # lexicon they carry is what this run's tagging uses.
    if job.context:
        from ..context import add_context
        from ..ingest.lexicon import load_lexicon

        say(f"\nContext documents: {len(job.context)}")
        try:
            result = add_context(
                job.subject_id,
                [(p.name, p.read_bytes()) for p in job.context],
                design=design)
            say(f"  kept {', '.join(result['stored'])} in {result['folder']}")
            if result["lexicon"]:
                lex = result["lexicon"]
                say(f"  installed a concept lexicon covering {lex['dot_points']} "
                    f"dot points ({lex['coverage']:.0%}) from {lex['from']}")
                if lex["unknown"]:
                    say(f"  ! ignored {len(lex['unknown'])} dot point id(s) this "
                        f"study design does not have: {', '.join(lex['unknown'][:5])}")
            for note in result["notes"]:
                say(f"  ! {note}")
        except ValueError as exc:
            say(f"  ! context not stored: {exc}")
        load_lexicon.cache_clear()

    packs, books = find_materials(job.folder)
    if not packs and not books:
        if job.study_design is None:
            raise ValueError("nothing to index: no PDF, Word or question-pack "
                             "files in the upload")
        say("\nNo books or packs in this upload, so only the study design was "
            "imported. Upload materials for it next.")

    with db.session() as conn:
        for pack in packs:
            say(f"\nPack: {pack.name}")
            report = import_pack(conn, pack, design=design,
                                 progress=lambda s: say(s.rstrip()))
            if not report.ok:
                say(f"  not imported ({len(report.errors)} error(s))")
        skipped: list[str] = []
        for book in books:
            say(f"\nBook: {book.name}")
            source_id = f"{job.subject_id}-{slug(book.stem)}"
            try:
                report = index_book(conn, book, subject_id=job.subject_id,
                                    source_id=source_id, design=design,
                                    progress=lambda s: say(s.rstrip()))
            except SourceError as exc:
                # One unreadable file — a photocopy, a locked PDF — must not
                # throw away the other nine the teacher dropped in with it.
                say(f"  SKIPPED. {exc}")
                skipped.append(book.name)
                continue
            say(report.summary())
        if skipped:
            say(f"\n{len(skipped)} file(s) skipped: {', '.join(skipped)}")
        conn.commit()

        say("\nWriting the export folder…")
        export = export_subject(conn, job.subject_id, design=design)
    say(f"  {export.summary()}")
    say(f"  folder: {export.folder}")
    job.result = {
        "folder": str(export.folder),
        "zip": export.zip_path.name if export.zip_path else None,
        "questions": export.questions,
        "passages": export.passages,
        "figures": export.figures,
        "sources": export.sources,
        "coverage": (export.folder / "coverage.txt").read_text(encoding="utf-8"),
    }


def export_path(name: str) -> Path | None:
    """A zip under out/ by name, or None if the name is not one of ours."""
    if not re.fullmatch(r"index-[a-z0-9-]+-\d{4}-\d{2}-\d{2}-\d{4}\.zip", name):
        return None
    path = EXPORTS_DIR / name
    return path if path.exists() else None
