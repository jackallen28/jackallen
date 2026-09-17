import pytest

from blitz.studydesign import list_subjects, load_study_design


def test_both_subjects_present():
    ids = {d.subject_id for d in list_subjects()}
    assert {"business-management", "physics"} <= ids


@pytest.mark.parametrize("subject", ["business-management", "physics"])
def test_units_three_and_four_only(subject):
    design = load_study_design(subject)
    assert sorted(u.number for u in design.units) == [3, 4]


@pytest.mark.parametrize("subject", ["business-management", "physics"])
def test_dot_point_ids_are_unique(subject):
    ids = [kk.id for kk in load_study_design(subject).all_key_knowledge()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("subject", ["business-management", "physics"])
def test_every_area_has_key_knowledge(subject):
    for area in load_study_design(subject).all_areas():
        assert area.key_knowledge, f"{area.id} has no key knowledge"


@pytest.mark.parametrize("subject", ["business-management", "physics"])
def test_question_types_are_distinct_and_weighted(subject):
    design = load_study_design(subject)
    ids = [qt.id for qt in design.question_types]
    assert len(ids) == len(set(ids))
    assert all(qt.default_weight > 0 for qt in design.question_types)


@pytest.mark.parametrize("subject", ["business-management", "physics"])
def test_lookups_round_trip(subject):
    design = load_study_design(subject)
    kk = design.all_key_knowledge()[0]
    assert design.key_knowledge(kk.id) is kk
    assert kk in design.area_of(kk.id).key_knowledge


def test_a_design_is_verified_only_if_every_dot_point_is():
    """`fully_verified` is what the UI and the sheet banner key off.

    Physics has been imported from the VCAA PDF; Business Management is still a
    hand-written reconstruction. Both states have to be reported accurately,
    because the banner is the only thing telling a student whether the wording
    they are revising against is real.
    """
    for design in list_subjects():
        flags = {kk.verified for kk in design.all_key_knowledge()}
        assert design.fully_verified == (flags == {True})


def test_imported_designs_record_where_they_came_from():
    for design in list_subjects():
        if design.fully_verified:
            assert "Imported from" in design.source, (
                f"{design.subject_id} claims verified wording but does not say "
                "which PDF it came from")


def test_physics_was_imported_from_the_vcaa_pdf():
    design = load_study_design("physics")
    assert design.fully_verified
    assert design.accreditation
    # Sanity-check the shape against the real document rather than a guess.
    assert len(design.all_key_knowledge()) > 60
    assert [a.id for a in design.all_areas()] == [
        "physics-u3-aos1", "physics-u3-aos2", "physics-u3-aos3",
        "physics-u4-aos1", "physics-u4-aos2",
    ]


def test_no_assessment_boilerplate_leaked_into_key_knowledge():
    """The bullet collector used to run past "Key knowledge" into assessment.

    That produced dot points like "Duration: 2.5 hours", which then appeared in
    the student's selection list and polluted the tagger's vocabulary.
    """
    banned = ("duration:", "date:", "vcaa examination rules",
              "will be marked by assessors", "satisfactory completion")
    for design in list_subjects():
        for kk in design.all_key_knowledge():
            low = kk.text.lower()
            assert not any(b in low for b in banned), \
                f"{kk.id} is assessment boilerplate: {kk.text[:60]}"


class TestSampleBankFingerprint:
    """Dot point ids are positional, so a re-import can change what they mean."""

    def test_shipped_banks_match_their_study_design(self):
        import yaml

        from blitz.corpus.sample import CORPUS_DIR, fingerprint

        for path in sorted(CORPUS_DIR.glob("sample_*.yaml")):
            subject = path.stem.removeprefix("sample_")
            doc = yaml.safe_load(path.read_text(encoding="utf-8"))
            stored = doc.get("study_design_fingerprint")
            assert stored, f"{path.name} records no study design fingerprint"
            assert stored == fingerprint(load_study_design(subject)), (
                f"{path.name} is stale — its questions may now point at the "
                "wrong dot points"
            )

    def test_a_stale_bank_refuses_to_load(self, tmp_path, monkeypatch):
        import sqlite3

        import yaml

        from blitz.corpus import sample as sample_mod
        from blitz.db import connect

        src = sample_mod.CORPUS_DIR / "sample_physics.yaml"
        doc = yaml.safe_load(src.read_text(encoding="utf-8"))
        doc["study_design_fingerprint"] = "deadbeefcafe"

        staged = tmp_path / "sample_physics.yaml"
        staged.write_text(yaml.safe_dump(doc, allow_unicode=True), encoding="utf-8")
        monkeypatch.setattr(sample_mod, "CORPUS_DIR", tmp_path)

        conn: sqlite3.Connection = connect(tmp_path / "t.sqlite3")
        try:
            with pytest.raises(sample_mod.StaleSampleBank, match="different"):
                sample_mod.load_sample(conn, "physics")
        finally:
            conn.close()

    def test_questions_land_on_the_topic_they_test(self):
        """Spot-check the re-mapping after the VCAA import, by topic keyword."""
        import yaml

        from blitz.corpus.sample import CORPUS_DIR

        design = load_study_design("physics")
        doc = yaml.safe_load((CORPUS_DIR / "sample_physics.yaml").read_text())
        expected = {
            "cricket ball": "impulse",
            "transformer": "transformer",
            "de Broglie wavelength of an electron": "de Broglie",
            "Muons created in the upper atmosphere": "muon",
            "peak-to-peak": "root-mean-square",
        }
        for needle, wanted in expected.items():
            q = next((q for q in doc["questions"] if needle in q["body"]), None)
            assert q, f"sample question containing {needle!r} is missing"
            kk_id = q["kk"] if isinstance(q["kk"], str) else q["kk"][0]
            text = design.key_knowledge(kk_id).text.lower()
            assert wanted.lower() in text, (
                f"{needle!r} is filed under {kk_id} ({text[:60]}…), "
                f"which does not mention {wanted!r}"
            )
