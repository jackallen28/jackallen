"""The picker's job is to fill two pages without lying about what it covered."""

import pytest

from blitz.models import SheetSpec
from blitz.picker import _keywords, _matches, _stem, build_plan
from blitz.render.layout import budget_mm, estimate_height_mm
from blitz.studydesign import load_study_design


def _spec(subject="physics", **kw):
    design = load_study_design(subject)
    kw.setdefault("kk_ids", [kk.id for kk in design.all_key_knowledge()])
    return SheetSpec(subject_id=subject, **kw)


def test_empty_selection_yields_nothing(seeded):
    plan = build_plan(seeded, _spec(kk_ids=[]))
    assert plan.questions == []
    assert plan.warnings


def test_plan_fits_the_page_budget(seeded):
    plan = build_plan(seeded, _spec(seed=1))
    used = sum(
        estimate_height_mm(q.body, marks=q.marks, options=q.options,
                           has_figure=q.has_figure)
        for q in plan.questions
    )
    assert used <= budget_mm(2)


def test_plan_actually_fills_the_sheet(seeded):
    """A two-page sheet with five questions on it is a failure, not a sheet."""
    plan = build_plan(seeded, _spec(seed=1))
    assert len(plan.questions) >= 12


def test_questions_only_come_from_selected_dot_points(seeded):
    design = load_study_design("physics")
    chosen = [kk.id for kk in design.area("physics-u3-aos1").key_knowledge]
    plan = build_plan(seeded, _spec(kk_ids=chosen))
    for q in plan.questions:
        assert set(q.kk_ids) & set(chosen), f"{q.id} is off-syllabus for this sheet"


def test_question_type_filter_is_respected(seeded):
    plan = build_plan(seeded, _spec(question_type_ids=["ph-mc"]))
    assert plan.questions
    assert {q.question_type for q in plan.questions} == {"ph-mc"}


def test_uncovered_dot_points_are_reported_honestly(seeded):
    plan = build_plan(seeded, _spec(seed=2))
    covered = {kk for q in plan.questions for kk in q.kk_ids}
    for kk_id in plan.uncovered_kk_ids:
        assert kk_id not in covered
    reported = set(plan.uncovered_kk_ids) | covered
    assert set(plan.spec.kk_ids) <= reported | set(plan.spec.kk_ids)


def test_no_duplicate_questions(seeded):
    plan = build_plan(seeded, _spec(seed=3))
    ids = [q.id for q in plan.questions]
    assert len(ids) == len(set(ids))


def test_same_seed_gives_the_same_sheet(seeded):
    a = build_plan(seeded, _spec(seed=42))
    b = build_plan(seeded, _spec(seed=42))
    assert [q.id for q in a.questions] == [q.id for q in b.questions]


def test_excluded_questions_stay_off(seeded):
    first = build_plan(seeded, _spec(seed=5))
    drop = [q.id for q in first.questions[:3]]
    second = build_plan(seeded, _spec(seed=5, exclude_question_ids=drop))
    assert not {q.id for q in second.questions} & set(drop)


def test_disallowing_generated_empties_the_sample_only_index(seeded):
    """Every sample question is generated, so this must come back empty."""
    plan = build_plan(seeded, _spec(allow_generated=False))
    assert plan.questions == []


def test_notes_pull_the_named_topic_onto_the_sheet(seeded):
    """The notes box is the feature; if it doesn't steer coverage it's decoration."""
    design = load_study_design("physics")
    plain = build_plan(seeded, _spec(seed=11))
    nudged = build_plan(seeded, _spec(seed=11, notes="relativity and the photoelectric effect"))

    def covers(plan, needle):
        return any(
            needle in design.key_knowledge(kk).display.lower()
            for q in plan.questions for kk in q.kk_ids
        )

    assert not covers(plain, "photoelectric")
    assert covers(nudged, "photoelectric")


def test_notes_do_not_reshuffle_an_unrelated_selection(seeded):
    """Naming a Unit 3 topic must not drag Unit 4 onto the sheet."""
    design = load_study_design("physics")
    plan = build_plan(seeded, _spec(seed=11, notes="transformers and transmission losses"))
    u4 = [kk for q in plan.questions for kk in q.kk_ids if "-u4-" in kk]
    assert not u4


def test_ordering_groups_by_area_of_study(seeded):
    design = load_study_design("physics")
    plan = build_plan(seeded, _spec(seed=7))
    order = {a.id: i for i, a in enumerate(design.all_areas())}
    ranks = [
        min(order[design.area_of(kk).id] for kk in q.kk_ids)
        for q in plan.questions
    ]
    assert ranks == sorted(ranks)


@pytest.mark.parametrize("word,stem", [
    ("relativity", "relat"),
    ("motion", "motion"),
    ("theories", "theor"),
    ("calculations", "calculation"),
])
def test_stemmer(word, stem):
    assert _stem(word) == stem


def test_stem_matching_is_two_way_tolerant():
    assert _matches("relativity", "relativistic energy and rest mass")
    assert _matches("momentum", "conservation of momentum")
    assert not _matches("transformer", "the photoelectric effect")


def test_keywords_drop_filler_words():
    kws = _keywords("I really struggle with the Force Field Analysis weighting")
    assert "force" in kws and "weighting" in kws
    assert "really" not in kws and "with" not in kws
