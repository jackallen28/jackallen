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


def test_drafts_are_flagged_unverified():
    """The shipped files are reconstructions, so nothing may claim to be VCAA's.

    This test is expected to start failing the moment a real study design is
    imported — at which point delete it.
    """
    for design in list_subjects():
        assert not design.fully_verified, (
            f"{design.subject_id} now claims verified wording; if it really was "
            "imported from the VCAA PDF, remove this test."
        )
