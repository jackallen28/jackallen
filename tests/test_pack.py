"""Question pack import — the preferred way questions get into Blitz.

A pack is curated, so it is trusted further than the heuristic extractor: its
rows land verified, its dot point tags are taken as given, and it decides
per question whether the text can be shown at all. That trust is why the
validator is strict and the import is all-or-nothing.
"""

import json

import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

from blitz.corpus.sample import fingerprint
from blitz.ingest.pack import import_pack, validate
from blitz.studydesign import load_study_design

PAGE_W, PAGE_H = A4


@pytest.fixture
def design():
    return load_study_design("physics")


@pytest.fixture
def source_pdf(tmp_path):
    path = tmp_path / "book.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    for page in range(3):
        c.setFont("Helvetica", 12)
        c.drawString(20 * mm, PAGE_H - 30 * mm, f"page {page}")
        c.setLineWidth(1)
        for i in range(6):
            c.rect(30 * mm + i * 8 * mm, PAGE_H - 90 * mm, 7 * mm, 30 * mm)
        c.showPage()
    c.save()
    return path


def _pack(design, tmp_path, **overrides):
    pack = {
        "pack_version": "1.0",
        "subject_id": "physics",
        "study_design_fingerprint": fingerprint(design),
        "source": {"id": "bk", "kind": "checkpoints", "title": "Book",
                   "pdf": "book.pdf"},
        "questions": [{
            "id": "Q1",
            "title": "Impulse in a collision",
            "provenance": "VCAA 2019 SA Q3",
            "printed_page": "42",
            "source_number": "7",
            "kk_ids": ["physics-u3-aos1-kk07"],
            "question_type": "ph-calculation",
            "stem": "A ball of mass 0.16 kg is struck by a bat.",
            "parts": [{"label": "a", "text": "Find the impulse.", "marks": 3},
                      {"label": "b", "text": "Find the average force.", "marks": 2}],
            "answer": {"text": "Impulse is the change in momentum."},
            "figures": [{"role": "question", "page": 0,
                         "bbox": [80, 80, 300, 200], "caption": "The collision"}],
        }],
    }
    pack.update(overrides)
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path


def _write(path, pack):
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path


class TestValidation:
    def _validate(self, design, tmp_path, mutate):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        mutate(pack)
        return validate(pack, design, tmp_path)

    def test_a_good_pack_passes(self, design, tmp_path, source_pdf):
        path = _pack(design, tmp_path)
        report = validate(json.loads(path.read_text()), design, tmp_path)
        assert report.ok, report.errors

    def test_unknown_dot_point_is_rejected(self, design, tmp_path, source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p["questions"][0].update(
                               kk_ids=["physics-u9-aos9-kk99"]))
        assert not r.ok
        assert any("unknown dot point" in e for e in r.errors)

    def test_unknown_question_type_is_rejected(self, design, tmp_path, source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p["questions"][0].update(
                               question_type="ph-interpretive-dance"))
        assert any("unknown question_type" in e for e in r.errors)

    def test_duplicate_ids_are_rejected(self, design, tmp_path, source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p["questions"].append(dict(p["questions"][0])))
        assert any("duplicate id" in e for e in r.errors)

    def test_a_question_with_no_text_is_rejected(self, design, tmp_path, source_pdf):
        def strip(p):
            p["questions"][0].pop("stem")
            p["questions"][0].pop("parts")
        assert any("neither stem nor parts" in e
                   for e in self._validate(design, tmp_path, strip).errors)

    def test_a_stale_fingerprint_is_rejected(self, design, tmp_path, source_pdf):
        """Dot point ids are positional; a stale pack may tag the wrong ones."""
        r = self._validate(design, tmp_path,
                           lambda p: p.update(study_design_fingerprint="deadbeef"))
        assert not r.ok
        assert any("different" in e and "study" in e for e in r.errors)

    def test_a_missing_fingerprint_only_warns(self, design, tmp_path, source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p.pop("study_design_fingerprint"))
        assert r.ok
        assert any("fingerprint" in w for w in r.warnings)

    def test_a_bbox_off_the_end_of_the_pdf_is_rejected(self, design, tmp_path,
                                                       source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p["questions"][0]["figures"][0].update(page=99))
        assert any("outside the PDF" in e for e in r.errors)

    def test_an_inverted_bbox_is_rejected(self, design, tmp_path, source_pdf):
        r = self._validate(
            design, tmp_path,
            lambda p: p["questions"][0]["figures"][0].update(bbox=[300, 200, 80, 80]))
        assert any("inverted" in e for e in r.errors)

    def test_a_missing_figure_file_is_rejected(self, design, tmp_path, source_pdf):
        def use_file(p):
            fig = p["questions"][0]["figures"][0]
            fig.pop("page"), fig.pop("bbox")
            fig["file"] = "figures/nope.png"
        assert any("file not found" in e
                   for e in self._validate(design, tmp_path, use_file).errors)

    def test_a_figure_needs_exactly_one_of_file_or_bbox(self, design, tmp_path,
                                                        source_pdf):
        r = self._validate(design, tmp_path,
                           lambda p: p["questions"][0]["figures"][0].update(
                               file="x.png"))
        assert any("not both or neither" in e for e in r.errors)

    def test_crop_mode_without_a_figure_is_rejected(self, design, tmp_path,
                                                    source_pdf):
        def crop_no_fig(p):
            p["questions"][0]["render_mode"] = "crop"
            p["questions"][0]["figures"] = []
        assert any("no question figure" in e
                   for e in self._validate(design, tmp_path, crop_no_fig).errors)

    def test_errors_are_reported_together(self, design, tmp_path, source_pdf):
        """A 1000-page pack is unusable if it surfaces one error per run."""
        def break_lots(p):
            p["questions"][0].update(kk_ids=["nope"], question_type="nope")
            p["questions"].append({"id": "Q1", "stem": "dup"})
        r = self._validate(design, tmp_path, break_lots)
        assert len(r.errors) >= 3


class TestImport:
    def test_a_clean_pack_loads(self, design, tmp_path, source_pdf, conn):
        report = import_pack(conn, _pack(design, tmp_path),
                             design=design, progress=lambda *_: None)
        assert report.ok and report.imported == 1
        row = conn.execute("SELECT * FROM question").fetchone()
        assert row["body"].startswith("A ball of mass")
        assert row["verified"] == 1, "a curated pack is trusted"

    def test_marks_are_summed_from_the_parts(self, design, tmp_path, source_pdf,
                                             conn):
        import_pack(conn, _pack(design, tmp_path), design=design,
                    progress=lambda *_: None)
        assert conn.execute("SELECT marks FROM question").fetchone()["marks"] == 5

    def test_a_bbox_figure_is_cropped_from_the_pdf(self, design, tmp_path,
                                                   source_pdf, conn):
        import_pack(conn, _pack(design, tmp_path), design=design,
                    progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        assert row["figure_path"], "the bbox figure was not cropped"
        from pathlib import Path
        assert Path(row["figure_path"]).exists()
        assert row["figure_caption"] == "The collision"

    def test_provenance_reaches_the_citation(self, design, tmp_path, source_pdf,
                                             conn):
        import_pack(conn, _pack(design, tmp_path), design=design,
                    progress=lambda *_: None)
        citation = conn.execute("SELECT citation FROM question").fetchone()["citation"]
        assert "Book" in citation and "p. 42" in citation and "Q7" in citation
        assert "VCAA 2019 SA Q3" in citation

    def test_a_bad_pack_writes_nothing(self, design, tmp_path, source_pdf, conn):
        """All-or-nothing: a half-loaded pack has invisible gaps."""
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0]["kk_ids"] = ["physics-u9-aos9-kk99"]
        _write(path, pack)

        report = import_pack(conn, path, design=design, progress=lambda *_: None)
        assert not report.ok
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == 0

    def test_dry_run_writes_nothing(self, design, tmp_path, source_pdf, conn):
        report = import_pack(conn, _pack(design, tmp_path), design=design,
                             dry_run=True, progress=lambda *_: None)
        assert report.ok
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == 0

    def test_reimporting_updates_in_place(self, design, tmp_path, source_pdf, conn):
        path = _pack(design, tmp_path)
        import_pack(conn, path, design=design, progress=lambda *_: None)
        import_pack(conn, path, design=design, progress=lambda *_: None)
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == 1

    def test_a_missing_answer_stays_missing(self, design, tmp_path, source_pdf,
                                            conn):
        """Packs must not invent solutions, and import must not paper over it."""
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0].pop("answer")
        pack["questions"][0]["notes"] = "Source answer not supplied."
        _write(path, pack)

        import_pack(conn, path, design=design, progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        assert row["answer"] is None
        assert "not supplied" in json.loads(row["extra"])["notes"]

    def test_crop_mode_survives_into_the_database(self, design, tmp_path,
                                                  source_pdf, conn):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0]["render_mode"] = "crop"
        _write(path, pack)

        import_pack(conn, path, design=design, progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        assert row["render_mode"] == "crop"
        assert row["figure_path"]

    def test_untagged_questions_are_counted_not_dropped(self, design, tmp_path,
                                                        source_pdf, conn):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0].pop("kk_ids")
        _write(path, pack)

        report = import_pack(conn, path, design=design, progress=lambda *_: None)
        assert report.ok and report.untagged == 1
        assert conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"] == 1


def test_the_shipped_example_pack_is_valid():
    """The example doubles as documentation, so it must actually work."""
    from pathlib import Path

    path = Path(__file__).resolve().parent.parent / "packs" / "example-physics.json"
    pack = json.loads(path.read_text(encoding="utf-8"))
    report = validate(pack, load_study_design("physics"), path.parent)
    assert report.ok, report.errors


class TestFriendlyErrors:
    """The failures you hit before a pack is even read deserve a sentence."""

    def test_a_missing_file_says_so(self, conn, tmp_path):
        report = import_pack(conn, tmp_path / "nope.json",
                             progress=lambda *_: None)
        assert not report.ok
        assert "no such pack file" in report.errors[0]

    def test_a_directory_says_so(self, conn, tmp_path):
        report = import_pack(conn, tmp_path, progress=lambda *_: None)
        assert "is a directory" in report.errors[0]

    def test_malformed_json_points_at_the_line(self, conn, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text('{"subject_id": "physics",\n  "questions": [\n',
                        encoding="utf-8")
        report = import_pack(conn, path, progress=lambda *_: None)
        assert "not valid JSON" in report.errors[0]
        assert "line" in report.errors[0]

    def test_a_json_array_is_rejected_clearly(self, conn, tmp_path):
        path = tmp_path / "arr.json"
        path.write_text("[]", encoding="utf-8")
        report = import_pack(conn, path, progress=lambda *_: None)
        assert "JSON object" in report.errors[0]

    def test_a_missing_subject_id_says_where_to_look(self, conn, tmp_path):
        path = tmp_path / "p.json"
        path.write_text('{"questions": []}', encoding="utf-8")
        report = import_pack(conn, path, progress=lambda *_: None)
        assert "subject_id is required" in report.errors[0]

    def test_an_unknown_subject_lists_the_known_ones(self, conn, tmp_path):
        path = tmp_path / "p.json"
        path.write_text('{"subject_id": "chemistry", "questions": []}',
                        encoding="utf-8")
        report = import_pack(conn, path, progress=lambda *_: None)
        assert "physics" in report.errors[0]

    def test_a_tilde_path_is_expanded(self, conn, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        report = import_pack(conn, "~/nope.json", progress=lambda *_: None)
        assert "~" not in report.errors[0], "the path should be expanded"


def test_the_lexicon_is_not_mistaken_for_a_study_design():
    """physics-lexicon.yaml sits beside the study designs but is not one."""
    from blitz.studydesign import list_subjects

    ids = [d.subject_id for d in list_subjects()]
    assert "physics-lexicon" not in ids
    assert ids == sorted(set(ids))


class TestMultipleFigures:
    """A question routinely needs more than one image.

    A page continuation, a shared scenario printed above it, or an earlier
    question it depends on. Importing only the first truncated 60% of the
    content in the first real pack this was tried on, and the loss was silent.
    """

    def _multi(self, design, tmp_path, source_pdf):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0]["render_mode"] = "crop"
        pack["questions"][0]["answer_mode"] = "crop"
        pack["questions"][0]["figures"] = [
            {"role": "question", "page": 0, "bbox": [40, 40, 560, 200],
             "caption": "Shared context"},
            {"role": "question", "page": 1, "bbox": [40, 40, 560, 300],
             "caption": "Source question (continued)"},
            {"role": "answer", "page": 2, "bbox": [40, 40, 560, 150],
             "caption": "Source answer"},
            {"role": "answer", "page": 2, "bbox": [40, 160, 560, 260],
             "caption": "Source answer (continued)"},
        ]
        return _write(path, pack)

    def test_every_figure_is_imported(self, design, tmp_path, source_pdf, conn):
        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        row = conn.execute("SELECT figures FROM question").fetchone()
        figs = json.loads(row["figures"])
        assert len(figs) == 4, f"expected 4 figures, imported {len(figs)}"
        assert [f["role"] for f in figs] == ["question", "question",
                                             "answer", "answer"]

    def test_figure_order_is_preserved(self, design, tmp_path, source_pdf, conn):
        """A shared scenario has to come before the question that uses it."""
        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        figs = json.loads(conn.execute("SELECT figures FROM question").fetchone()["figures"])
        captions = [f["caption"] for f in figs if f["role"] == "question"]
        assert captions == ["Shared context", "Source question (continued)"]

    def test_each_figure_gets_its_own_file(self, design, tmp_path, source_pdf,
                                           conn):
        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        figs = json.loads(conn.execute("SELECT figures FROM question").fetchone()["figures"])
        paths = [f["path"] for f in figs]
        assert len(set(paths)) == 4, "figures overwrote each other"

    def test_the_first_question_figure_stays_in_the_legacy_columns(
            self, design, tmp_path, source_pdf, conn):
        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        figs = json.loads(row["figures"])
        assert row["figure_path"] == figs[0]["path"]
        assert row["figure_caption"] == "Shared context"

    def test_all_of_them_reach_the_sheet(self, design, tmp_path, source_pdf,
                                         conn):
        import pymupdf

        from blitz.models import SheetSpec
        from blitz.picker import build_plan
        from blitz.render import render_sheet

        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        kk = json.loads(_pack(design, tmp_path).read_text())["questions"][0]["kk_ids"]
        plan = build_plan(conn, SheetSpec(subject_id="physics", kk_ids=kk), design)
        out = tmp_path / "sheet.pdf"
        render_sheet(plan, out, design)

        doc = pymupdf.open(out)
        images = sum(len(doc[i].get_images(full=True))
                     for i in range(doc.page_count))
        doc.close()
        assert images >= 4, (
            f"only {images} of 4 figures reached the sheet — a question whose "
            "context is dropped is unanswerable")

    def test_the_picker_budgets_for_the_whole_stack(self, design, tmp_path,
                                                    source_pdf, conn):
        """Costing only the first image would overfill the sheet."""
        from blitz.models import Question
        from blitz.picker import build_plan
        from blitz.models import SheetSpec

        import_pack(conn, self._multi(design, tmp_path, source_pdf),
                    design=design, progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        q = Question.from_row(row, ["physics-u3-aos1-kk07"])

        from blitz.render.layout import image_height_mm

        stack = sum(image_height_mm(f["path"], columns=1,
                                    pt_width=f.get("pt_width"))
                    for f in q.figures_for("question"))
        first = image_height_mm(q.figures_for("question")[0]["path"], columns=1,
                                pt_width=q.figures_for("question")[0].get("pt_width"))
        assert stack > first * 1.3, "the stack should cost more than its first image"


class TestContextAndDependencies:
    """A question that loses its scenario or its prerequisite is unanswerable."""

    def _with(self, design, tmp_path, **extra):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0].update(extra)
        return _write(path, pack)

    def test_context_is_stored_and_printed(self, design, tmp_path, source_pdf,
                                           conn):
        import pymupdf

        from blitz.models import SheetSpec
        from blitz.picker import build_plan
        from blitz.render import render_sheet

        path = self._with(design, tmp_path,
                          context="A cricket ball is struck by a bat.")
        import_pack(conn, path, design=design, progress=lambda *_: None)
        row = conn.execute("SELECT context FROM question").fetchone()
        assert row["context"] == "A cricket ball is struck by a bat."

        plan = build_plan(conn, SheetSpec(subject_id="physics",
                                          kk_ids=["physics-u3-aos1-kk07"]), design)
        out = tmp_path / "s.pdf"
        render_sheet(plan, out, design)
        doc = pymupdf.open(out)
        text = " ".join(" ".join(p.get_text("text").split()) for p in doc)
        doc.close()
        assert "A cricket ball is struck by a bat" in text

    def test_a_dependency_outside_the_pack_is_rejected(self, design, tmp_path,
                                                       source_pdf):
        path = self._with(design, tmp_path, depends_on=["NOT-IN-PACK"])
        report = validate(json.loads(path.read_text()), design, tmp_path)
        assert not report.ok
        assert any("not in this pack" in e for e in report.errors)

    def test_a_prerequisite_is_pulled_onto_the_sheet(self, design, tmp_path,
                                                     source_pdf, conn):
        from blitz.models import SheetSpec
        from blitz.picker import build_plan

        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        first = pack["questions"][0]
        second = dict(first)
        second["id"] = "Q2"
        second["stem"] = "Using your answer from the previous question, find the force."
        second["depends_on"] = ["Q1"]
        second["figures"] = []
        second["kk_ids"] = ["physics-u3-aos1-kk06"]
        pack["questions"].append(second)
        _write(path, pack)

        import_pack(conn, path, design=design, progress=lambda *_: None)
        # Select only the dependent question's dot point.
        plan = build_plan(conn, SheetSpec(subject_id="physics",
                                          kk_ids=["physics-u3-aos1-kk06"]), design)
        ids = [q.id for q in plan.questions]
        assert any(i.endswith("Q2") for i in ids), "the chosen question is missing"
        assert any(i.endswith("Q1") for i in ids), (
            "its prerequisite was not pulled in — the question is unanswerable")
        assert ids.index(next(i for i in ids if i.endswith("Q1"))) < \
            ids.index(next(i for i in ids if i.endswith("Q2"))), \
            "the prerequisite must come first"


class TestDraftStatus:
    """Curated is not the same as checked."""

    def test_a_draft_pack_does_not_land_verified(self, design, tmp_path,
                                                 source_pdf, conn):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["status"] = "draft"
        _write(path, pack)
        import_pack(conn, path, design=design, progress=lambda *_: None)
        assert conn.execute("SELECT verified FROM question").fetchone()["verified"] == 0

    def test_a_flagged_question_does_not_land_verified(self, design, tmp_path,
                                                       source_pdf, conn):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0]["review"] = ["curriculum tag needs subject review"]
        _write(path, pack)
        import_pack(conn, path, design=design, progress=lambda *_: None)
        row = conn.execute("SELECT * FROM question").fetchone()
        assert row["verified"] == 0
        assert "subject review" in row["review"]

    def test_an_approved_pack_still_lands_verified(self, design, tmp_path,
                                                   source_pdf, conn):
        import_pack(conn, _pack(design, tmp_path), design=design,
                    progress=lambda *_: None)
        assert conn.execute("SELECT verified FROM question").fetchone()["verified"] == 1

    def test_an_unknown_status_is_rejected(self, design, tmp_path, source_pdf):
        path = _pack(design, tmp_path)
        pack = json.loads(path.read_text())
        pack["questions"][0]["status"] = "probably fine"
        _write(path, pack)
        report = validate(json.loads(path.read_text()), design, tmp_path)
        assert any("status must be" in e for e in report.errors)
