"""The extractor against many publishers' layouts at once.

A pattern tightened for one book silently empties another one's. These hold
every layout the extractor has been taught, so that stays visible.
"""

import pymupdf
import pytest

from blitz.ingest.textbook import segment_textbook

from publisher_pages import BUILDERS, build


def _questions(path):
    doc = pymupdf.open(path)
    try:
        return segment_textbook(doc)
    finally:
        doc.close()


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_the_right_number_of_questions_comes_out(name, tmp_path):
    path, expect = build(name, tmp_path)
    got = _questions(path)
    assert len(got) == expect, (
        f"{name}: expected {expect}, got {len(got)}\n"
        + "\n".join(f"  [{q.number}] {q.text[:70]}" for q in got))


def test_a_bare_number_is_not_a_measurement(tmp_path):
    """"1 Define ..." is a question; "10 m/s is the speed" is not."""
    from blitz.ingest.textbook import NUMBERED

    assert NUMBERED.match("1 Define the term")
    assert NUMBERED.match("2 A ball is dropped")
    for not_a_question in ("10 m/s is the speed", "5.0 kg block", "2 marks",
                           "2019 was the year", "3 of the 5 samples", "1 mark"):
        assert not NUMBERED.match(not_a_question), not_a_question


def test_a_bare_letter_is_not_the_indefinite_article(tmp_path):
    from blitz.ingest.segment import PART

    assert PART.match("a Calculate the net force")
    assert PART.match("b State the direction")
    for stem in ("a ball is dropped", "a the object moves"):
        assert not PART.match(stem), stem


def test_parts_are_printed_the_same_way_whatever_the_book_did(tmp_path):
    path, _ = build("subparts-without-dots", tmp_path)
    q = _questions(path)[0]
    assert q.parts == ["a. Calculate the net force if it accelerates at 1.5 m/s2.",
                       "b. State the direction of the net force."]


def test_marks_are_counted_without_brackets(tmp_path):
    path, _ = build("marks-without-brackets", tmp_path)
    qs = _questions(path)
    assert [q.marks for q in qs] == [2, 3]
    assert all("mark" not in q.text.lower() for q in qs)


def test_a_running_header_never_joins_a_question(tmp_path):
    path, _ = build("running-headers", tmp_path)
    for q in _questions(path):
        assert "VCE PHYSICS" not in q.full_text
        assert q.full_text.strip().endswith(".")


def test_the_answers_section_is_not_mined_for_questions(tmp_path):
    path, _ = build("answers-at-the-back", tmp_path)
    blob = " ".join(q.full_text for q in _questions(path))
    assert "p = mv" not in blob
    assert "Impulse is the change" not in blob


def test_a_case_study_reaches_every_question_under_it(tmp_path):
    path, _ = build("case-study-shared", tmp_path)
    qs = _questions(path)
    assert all("Harrow Retail employs 340 staff" in q.stimulus for q in qs)


def test_options_survive_a_block_that_mixes_types(tmp_path):
    path, _ = build("mixed-mc-and-short", tmp_path)
    qs = _questions(path)
    assert qs[0].options == ["joule", "watt", "newton", "pascal"]
    assert not qs[1].options and qs[1].marks == 2
