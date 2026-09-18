"""What happens when the file is the problem.

A school will feed this photocopied SACs, locked PDFs, half-downloaded files
and things named .docx that are not. Every one of these used to end in a
Python traceback, which tells a teacher nothing and looks like the program
is broken rather than the file.
"""

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

from blitz.ingest.extract import SourceError, looks_scanned, open_pdf


@pytest.fixture
def broken(tmp_path):
    def make(name, data=b""):
        path = tmp_path / name
        path.write_bytes(data)
        return path
    return make


def test_a_missing_file_says_so(tmp_path):
    with pytest.raises(SourceError, match="no file at"):
        open_pdf(tmp_path / "nope.pdf")


def test_an_empty_file_says_so(broken):
    with pytest.raises(SourceError, match="empty"):
        open_pdf(broken("empty.pdf"))


def test_a_corrupt_pdf_suggests_re_saving(broken):
    with pytest.raises(SourceError, match="could not be opened as a PDF"):
        open_pdf(broken("corrupt.pdf", b"%PDF-1.4\nnot really a pdf\n"))


def test_a_locked_pdf_says_to_unlock_it(tmp_path):
    path = tmp_path / "locked.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4, encrypt="secret")
    c.drawString(72, 700, "Question 1 (2 marks)")
    c.save()
    with pytest.raises(SourceError, match="password-protected"):
        open_pdf(path)


def _scan(path, pages=3):
    doc = pymupdf.open()
    for _ in range(pages):
        page = doc.new_page()
        pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 400, 560))
        pix.set_rect(pix.irect, (235, 235, 235))
        page.insert_image(page.rect, pixmap=pix)
    doc.save(str(path))
    doc.close()
    return path


def test_a_photocopy_is_recognised_as_one(tmp_path):
    doc = open_pdf(_scan(tmp_path / "scan.pdf"))
    try:
        assert looks_scanned(doc)
    finally:
        doc.close()


def test_a_real_book_is_not_mistaken_for_a_scan(tmp_path):
    import sys

    sys.path.insert(0, "tests")
    from publisher_pages import build

    path, _ = build("oxford-check-your-learning", tmp_path)
    doc = open_pdf(path)
    try:
        assert not looks_scanned(doc)
    finally:
        doc.close()


class TestIndexing:
    """The message has to reach the person, not just be raised."""

    def _index(self, conn, path):
        from blitz.ingest.index import index_book

        return index_book(conn, path, subject_id="physics",
                          source_id="x", progress=lambda s: None)

    def test_indexing_a_scan_explains_why_nothing_came_out(self, conn, tmp_path):
        with pytest.raises(SourceError, match="looks like a scan"):
            self._index(conn, _scan(tmp_path / "scan.pdf"))

    def test_indexing_a_fake_docx_points_at_word(self, conn, tmp_path):
        path = tmp_path / "fake.docx"
        path.write_bytes(b"not a zip")
        with pytest.raises(SourceError, match="Word document"):
            self._index(conn, path)

    def test_the_cli_prints_the_message_and_fails(self, tmp_path, capsys, monkeypatch):
        import argparse

        from blitz.cli import cmd_index

        path = tmp_path / "corrupt.pdf"
        path.write_bytes(b"%PDF-1.4\nbroken\n")
        args = argparse.Namespace(
            pdf=str(path), subject="physics", source_id=None, title=None,
            kind="auto", edition=None, page_offset=0, first_page=0,
            last_page=None, study_design=None, no_content=True)
        assert cmd_index(args) == 1
        out = capsys.readouterr().out
        assert "could not be opened as a PDF" in out
        assert "Traceback" not in out
