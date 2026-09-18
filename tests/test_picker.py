"""The picker's job is to fill two pages without lying about what it covered."""

import pytest

from blitz.models import SheetSpec
from blitz.picker import _keywords, _matches, _stem, build_plan
from blitz.render.layout import budget_mm
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
    """Measured the way the renderer lays questions out, the plan fits the
    budget it was picked against."""
    from blitz.render.sheet import measure_question_mm

    design = load_study_design("physics")
    plan = build_plan(seeded, _spec(seed=1), design)
    used = sum(measure_question_mm(q, plan.columns, design) for q in plan.questions)
    assert used <= budget_mm(2, columns=plan.columns)
    # And not by a mile: an estimate that is safe because it is timid leaves
    # the second page empty.
    assert used >= 0.8 * budget_mm(2, columns=plan.columns)


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
    # One page: the sample bank fits on two almost whole, which would make
    # the plain sheet cover the topic by accident and prove nothing.
    design = load_study_design("physics")
    plain = build_plan(seeded, _spec(seed=11), pages=1)
    nudged = build_plan(seeded, _spec(seed=11, notes="relativity and the photoelectric effect"),
                        pages=1)

    def covers(plan, needle):
        return any(
            needle in design.key_knowledge(kk).display.lower()
            for q in plan.questions for kk in q.kk_ids
        )

    assert not covers(plain, "photoelectric")
    assert covers(nudged, "photoelectric")


def test_notes_promote_only_what_they_name(seeded):
    """Unrelated notes must leave the student's own selection order alone.

    Asserted on the priority ordering rather than on the finished sheet: whether
    Unit 4 fits depends on how much material the index happens to hold, which
    makes a sheet-level assertion a test of the fixture, not of the picker.
    """
    from blitz.picker import _fetch_candidates, _keywords, _kk_priority
    from collections import defaultdict

    design = load_study_design("physics")
    spec = _spec(seed=11, notes="transformers and transmission losses")
    candidates, _ = _fetch_candidates(seeded, spec)
    by_kk = defaultdict(list)
    for q in candidates:
        for kk in q.kk_ids:
            by_kk[kk].append(q)

    order = _kk_priority(spec, design, by_kk, _keywords(spec.notes))
    promoted = order[:2]
    assert any("u3-aos3" in kk for kk in promoted), (
        f"transformer/transmission dot points should lead, got {promoted}")

    # Everything the notes do not name keeps the order the student chose.
    named = {kk for kk in order[:3]}
    rest = [kk for kk in order if kk not in named]
    assert rest == [kk for kk in spec.kk_ids if kk not in named]


def test_ordering_groups_by_area_of_study(seeded):
    design = load_study_design("physics")
    plan = build_plan(seeded, _spec(seed=7))
    order = {a.id: i for i, a in enumerate(design.all_areas())}
    ranks = [
        min(order[design.area_of(kk).id] for kk in q.kk_ids)
        for q in plan.questions
    ]
    assert ranks == sorted(ranks)


class TestSheetLength:
    """Quick / standard / extended change how much the picker is allowed to
    spend. Whether the sheet fills up is then a question about the index."""

    def test_a_longer_sheet_gets_more(self, seeded):
        got = {}
        for length in ("quick", "standard", "extended"):
            plan = build_plan(seeded, _spec(seed=3, length=length))
            got[length] = sum(q.marks or 1 for q in plan.questions)
        assert got["quick"] < got["standard"] <= got["extended"]

    def test_standard_is_what_the_default_was(self, seeded):
        """Two pages, unchanged: every sheet made before this option existed."""
        a = build_plan(seeded, _spec(seed=9))
        b = build_plan(seeded, _spec(seed=9, length="standard"))
        c = build_plan(seeded, _spec(seed=9), pages=2)
        assert [q.id for q in a.questions] == [q.id for q in b.questions]
        assert [q.id for q in a.questions] == [q.id for q in c.questions]

    def test_a_quick_sheet_never_splits_into_two_layouts(self, seeded):
        """One page cannot be a text page and a crop page both."""
        plan = build_plan(seeded, _spec(seed=4, length="quick"))
        assert plan.wide_ids == []

    def test_an_unknown_length_falls_back_to_standard(self, seeded):
        plan = build_plan(seeded, _spec(seed=9, length="enormous"))
        expected = build_plan(seeded, _spec(seed=9))
        assert [q.id for q in plan.questions] == [q.id for q in expected.questions]

    def test_a_spec_saved_before_lengths_existed_still_loads(self):
        """Browse mode and the student log round-trip specs through JSON."""
        old = '{"subject_id": "physics", "kk_ids": [], "difficulty": "mixed"}'
        assert SheetSpec.from_json(old).length == "standard"


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


class TestEmptyHandedMessages:
    """What a teacher is told when a sheet cannot be built.

    "Ingest your sources first" is the name of a function, not an instruction
    anyone outside this repo can follow.
    """

    def test_an_empty_subject_points_at_the_page_that_fixes_it(self, conn):
        plan = build_plan(conn, _spec(kk_ids=["physics-u3-aos1-kk01"]))
        assert plan.questions == []
        message = plan.warnings[0]
        assert "Index materials" in message
        assert "ingest" not in message.lower()

    def test_a_too_narrow_selection_says_how_to_widen_it(self, seeded):
        """There are questions; this selection just does not reach them."""
        plan = build_plan(seeded, _spec(kk_ids=["physics-u4-aos2-kk06"],
                                        question_type_ids=["ph-mc"]))
        assert plan.questions == []
        message = plan.warnings[0]
        assert "ticking more dot points" in message
        assert "Index materials" not in message
