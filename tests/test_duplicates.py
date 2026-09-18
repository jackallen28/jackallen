"""The same question arriving twice from two files.

A folder of practice SACs usually holds both the .docx a teacher wrote and a
PDF of it. The question id is derived from the file it came from, so both got
indexed and every question landed on the sheet twice, with nothing said.
"""

import pytest

from blitz import db
from blitz.db import content_fingerprint, duplicate_of


class TestFingerprint:
    def test_typesetting_does_not_change_it(self):
        a = content_fingerprint(
            "Explain why a geostationary satellite must orbit above the equator.")
        b = content_fingerprint(
            "Explain  why a geostationary satellite must orbit  above the equator!")
        assert a == b and a

    def test_a_different_question_is_a_different_fingerprint(self):
        a = content_fingerprint("Explain why a geostationary satellite orbits above the equator.")
        b = content_fingerprint("Explain why a polar satellite passes over both poles today.")
        assert a != b

    def test_something_too_short_is_not_fingerprinted(self):
        """Or every one-word question collapses into the same bucket."""
        assert content_fingerprint("Define force.") == ""
        assert content_fingerprint("") == ""


def _add(conn, qid, source_id, body, subject="physics"):
    db.upsert_source(conn, id=source_id, subject_id=subject, kind="exam",
                     title=source_id)
    db.insert_question(conn, {
        "id": qid, "subject_id": subject, "source_id": source_id,
        "question_type": "ph-explanation", "body": body,
        "fingerprint": content_fingerprint(body), "citation": "test",
    }, [])
    conn.commit()


BODY = "Explain why a geostationary satellite must orbit above the equator."


class TestDuplicateDetection:
    def test_the_same_words_from_another_file_are_found(self, conn):
        _add(conn, "q1", "sac-pdf", BODY)
        hit = duplicate_of(conn, content_fingerprint(BODY), "physics", "sac-word")
        assert hit is not None
        assert hit["source_id"] == "sac-pdf"
        assert hit["serial"]

    def test_the_same_file_is_not_its_own_duplicate(self, conn):
        """Re-indexing one file must stay idempotent, not skip everything."""
        _add(conn, "q1", "sac-pdf", BODY)
        assert duplicate_of(conn, content_fingerprint(BODY), "physics", "sac-pdf") is None

    def test_another_subject_is_not_a_duplicate(self, conn):
        _add(conn, "q1", "sac-pdf", BODY)
        assert duplicate_of(conn, content_fingerprint(BODY),
                            "business-management", "other") is None

    def test_an_unfingerprintable_question_never_matches(self, conn):
        _add(conn, "q1", "sac-pdf", "Define force.")
        assert duplicate_of(conn, "", "physics", "other") is None


def test_indexing_a_sac_twice_skips_the_second_copy(conn, tmp_path):
    """End to end: the PDF, then the Word original of the same paper."""
    import sys

    sys.path.insert(0, "tests")
    from publisher_pages import build, sac_docx

    from blitz.ingest.index import index_book

    pdf, _ = build("practice-sac", tmp_path)
    first = index_book(conn, pdf, subject_id="business-management",
                       source_id="sac-pdf", progress=lambda s: None)
    assert first.questions_indexed == 3
    assert first.duplicates == 0

    docx = sac_docx(tmp_path / "same-paper.docx")
    second = index_book(conn, docx, subject_id="business-management",
                        source_id="sac-word", progress=lambda s: None)
    assert second.questions_indexed == 0
    assert second.duplicates == 3
    assert second.duplicate_sources == {"sac-pdf"}
    assert "already indexed as" in " ".join(second.review)


def test_reindexing_one_file_is_still_idempotent(conn, tmp_path):
    import sys

    sys.path.insert(0, "tests")
    from publisher_pages import build

    from blitz.ingest.index import index_book

    pdf, _ = build("practice-sac", tmp_path)
    for _ in range(2):
        report = index_book(conn, pdf, subject_id="business-management",
                            source_id="sac-pdf", progress=lambda s: None)
        assert report.questions_indexed == 3, "a re-index must replace, not skip"
        assert report.duplicates == 0
    total = conn.execute("SELECT COUNT(*) n FROM question").fetchone()["n"]
    assert total == 3
