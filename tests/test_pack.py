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
