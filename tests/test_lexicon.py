"""The concept lexicon — the bridge between study design wording and questions."""

import pytest
import yaml

from blitz.config import STUDY_DESIGN_DIR
from blitz.ingest.lexicon import Concept, Lexicon, load_lexicon, validate
from blitz.ingest.tag import KeywordTagger
from blitz.studydesign import load_study_design


def test_physics_lexicon_covers_every_dot_point():
    design = load_study_design("physics")
    lex = load_lexicon("physics")
    missing = {kk.id for kk in design.all_key_knowledge()} - set(lex.concepts)
    assert not missing, f"no lexicon entry for {sorted(missing)}"


def test_lexicon_ids_all_exist_in_the_study_design():
    """Dot point ids are positional; a study design import can invalidate these."""
    design = load_study_design("physics")
    stale = validate(load_lexicon("physics"),
                     {kk.id for kk in design.all_key_knowledge()})
    assert not stale, f"lexicon references dot points that no longer exist: {stale}"


def test_a_subject_without_a_lexicon_gets_an_empty_one():
    """Both shipped subjects now have one, so this uses a subject that cannot."""
    lex = load_lexicon("no-such-subject")
    assert isinstance(lex, Lexicon)
    assert not lex.concepts


def test_business_management_has_a_lexicon_covering_every_dot_point():
    design = load_study_design("business-management")
    lex = load_lexicon("business-management")
    missing = {kk.id for kk in design.all_key_knowledge()} - set(lex.concepts)
    assert not missing, f"dot points with no trigger vocabulary: {sorted(missing)}"


@pytest.mark.parametrize("subject", ["physics", "business-management"])
def test_no_lexicon_term_is_a_truncated_stem(subject):
    """A bare stem matches nothing, and in `requires` it silently kills the
    dot point. `motivat*` is the way to write a word family."""
    from blitz.ingest.lexicon import truncated_terms

    bad = truncated_terms(load_lexicon(subject))
    assert not bad, f"write these with a trailing '*': {bad}"


@pytest.mark.parametrize("term,text,expected", [
    ("motivat*", "a motivation strategy", True),
    ("motivat*", "they motivate staff", True),
    ("motivat", "a motivation strategy", False),   # the trap the star exists for
    ("train*", "training options", True),
    ("train", "training options", False),
    ("train", "the train accelerates", True),
    ("restructur*", "after its restructure", True),
])
def test_star_matches_a_word_family(term, text, expected):
    from blitz.ingest.lexicon import _present

    assert _present(term, text) is expected


def test_one_hit_counts_once():
    """Listing both singular and plural must not double the score."""
    from blitz.ingest.lexicon import Concept

    both = Concept("x", triggers=("key performance indicator",
                                  "key performance indicators"))
    one = Concept("x", triggers=("key performance indicator",))
    text = "review the key performance indicators"
    assert both.matches(text) == one.matches(text)


def test_tagger_refuses_a_stale_lexicon():
    design = load_study_design("physics")
    bogus = Lexicon(subject_id="physics",
                    concepts={"physics-u9-aos9-kk99": Concept("physics-u9-aos9-kk99")})
    with pytest.raises(ValueError, match="no longer has"):
        KeywordTagger(design, lexicon=bogus)


class TestConceptScoring:
    def test_a_phrase_beats_a_bare_word(self):
        word = Concept("a", triggers=("work",))
        phrase = Concept("b", triggers=("work function",))
        text = "determine the work function of the metal"
        assert phrase.matches(text) > word.matches(text)

    def test_short_words_need_a_token_boundary(self):
        """'work' must not match inside 'homework' or 'network'."""
        c = Concept("a", triggers=("work",))
        assert c.matches("the work done by the force") > 0
        assert c.matches("the network of wires") == 0

    def test_avoid_rules_a_concept_out(self):
        c = Concept("a", triggers=("motion",), avoid=("car", "cyclist"))
        assert c.matches("describe the motion of the object") > 0
        assert c.matches("describe the motion of the car") == 0

    def test_requires_demands_supporting_evidence(self):
        c = Concept("a", triggers=("motion",), requires=("speed of light",))
        assert c.matches("motion of the trolley") == 0
        assert c.matches("motion approaching the speed of light") > 0

    def test_weight_breaks_ties_between_concepts(self):
        plain = Concept("a", triggers=("electron gun",))
        named = Concept("b", triggers=("de broglie",), weight=1.6)
        text = "electrons from an electron gun; find the de broglie wavelength"
        assert named.matches(text) > plain.matches(text)

    def test_vetoed_is_independent_of_triggers(self):
        """The veto binds the word-overlap fallback too, which has no triggers."""
        c = Concept("a", triggers=(), avoid=("car",))
        assert c.vetoed("the car accelerates")
        assert not c.vetoed("the trolley accelerates")


class TestTaggingWithTheLexicon:
    """Regressions for the specific misfilings found on the real book."""

    @pytest.fixture
    def tagger(self):
        return KeywordTagger(load_study_design("physics"))

    @pytest.fixture
    def design(self):
        return load_study_design("physics")

    def _area(self, design, result):
        assert result.kk_ids, "expected a tag"
        return design.area_of(result.kk_ids[0]).id

    @pytest.mark.parametrize("question,area", [
        # These all used to land in Unit 4 because of "motion", "travel", "speed".
        ("A speeding motorbike travels past a stationary police car at 35 m s⁻¹.",
         "physics-u3-aos1"),
        ("Two trains travel along the same track at 40 m s⁻¹ towards each "
         "other. At a separation of 1 km they brake, each with a constant "
         "deceleration of 1.7 m s⁻².", "physics-u3-aos1"),
        ("The speed-time graph below describes the motion of an object.",
         "physics-u3-aos1"),
        ("A cyclist accelerates constantly from rest for 10 s at 2.5 m s⁻².",
         "physics-u3-aos1"),
        # And these must still reach Unit 4.
        ("Determine the work function of the metal from the photoelectric graph.",
         "physics-u4-aos1"),
        ("Muons created in the upper atmosphere travel towards Earth at 0.99c.",
         "physics-u4-aos1"),
        ("Calculate the de Broglie wavelength of an electron.", "physics-u4-aos1"),
    ])
    def test_questions_land_in_the_right_area(self, tagger, design, question, area):
        assert self._area(design, tagger.tag(question)) == area

    def test_work_function_is_not_work_done(self, tagger, design):
        """'work' collided: the photoelectric work function vs mechanical work."""
        photo = tagger.tag("Determine the work function of the metal surface.")
        mech = tagger.tag("Calculate the work done by the 20 N force over 3.0 m.")
        assert design.area_of(photo.kk_ids[0]).id == "physics-u4-aos1"
        assert design.area_of(mech.kk_ids[0]).id == "physics-u3-aos1"

    def test_circular_motion_beats_generic_newton(self, tagger):
        r = tagger.tag("A car travels at constant speed around a flat, unbanked "
                       "circular bend. Draw a free-body diagram.")
        assert r.kk_ids[0] == "physics-u3-aos1-kk02"

    def test_emf_induced_matches_despite_word_order(self, tagger):
        """"the EMF induced in the coil" did not match the trigger "induced emf"."""
        r = tagger.tag("Calculate the magnitude of the EMF induced in the coil.")
        assert r.kk_ids[0] == "physics-u3-aos3-kk02"

    def test_investigation_skills_lose_to_content(self, tagger, design):
        """A photoelectric question that plots a graph is still photoelectric."""
        r = tagger.tag("Students set up apparatus to study the photoelectric "
                       "effect and plot the data to find the line of best fit.")
        assert design.area_of(r.kk_ids[0]).id == "physics-u4-aos1"

    def test_investigation_skills_win_when_nothing_else_fires(self, tagger, design):
        r = tagger.tag("Distinguish between a systematic error and a random "
                       "error, and state one way of reducing each.")
        assert design.area_of(r.kk_ids[0]).id == "physics-u4-aos2"


def test_lexicon_file_is_well_formed():
    raw = yaml.safe_load((STUDY_DESIGN_DIR / "physics-lexicon.yaml").read_text())
    assert raw["subject_id"] == "physics"
    for kk_id, entry in raw["dot_points"].items():
        assert entry and entry.get("triggers"), f"{kk_id} has no triggers"
        assert all(isinstance(t, str) and t.strip() for t in entry["triggers"])
        if "weight" in entry:
            assert 0 < float(entry["weight"]) <= 3
