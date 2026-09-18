"""Context documents: what a person knows about a subject, made usable.

Blitz generates a questionnaire for a subject, a model answers it, and the
answer comes back as a context document. The prose is kept with the
subject's material; the concept lexicon inside it is checked against the
study design and installed, which is the part that changes how questions
are filed.
"""

import pytest

from blitz import context
from blitz.studydesign import load_study_design

from tests.test_indexer_ui import client as _client  # noqa: F401  (fixture)


@pytest.fixture
def bm():
    return load_study_design("business-management")


def _answer(design, ids, extra=""):
    """What a model's answer looks like: prose, then a fenced yaml block."""
    entries = "\n".join(
        f"  {kk_id}:\n    triggers: [{', '.join(terms)}]"
        for kk_id, terms in ids.items())
    return f"""# Briefing answers — {design.subject_name}

## 1. How the subject is actually assessed

Case study responses dominate the back half of the paper.
{extra}

```yaml
subject_id: {design.subject_id}
dot_points:
{entries}
```
"""


def test_the_questionnaire_names_every_dot_point_and_the_output_it_wants(bm):
    text = context.briefing_text(bm)
    for area in bm.all_areas():
        for kk in area.key_knowledge:
            assert f"`{kk.id}`" in text, kk.id
    # It asks for the things that make a lexicon work, not just a word list.
    for asked in ("triggers", "requires", "avoid", "weight",
                  "easily confused", "command terms", "skills",
                  "examined together", "wrongly"):
        assert asked in text, asked
    assert f"subject_id: {bm.subject_id}" in text
    assert "```yaml" in text
    for qt in bm.question_types:
        assert f"`{qt.id}`" in text


def test_a_lexicon_is_found_in_a_models_markdown_answer(bm):
    first = bm.all_areas()[0].key_knowledge[0].id
    found = context.find_lexicon(_answer(bm, {first: ["sole trader", "partnership"]}))
    assert found["subject_id"] == "business-management"
    assert found["dot_points"][first]["triggers"] == ["sole trader", "partnership"]

    # A bare YAML file works too, and prose alone does not.
    assert context.find_lexicon(f"subject_id: x\ndot_points:\n  {first}:\n"
                                "    triggers: [a]")["dot_points"]
    assert context.find_lexicon("Just some notes about the subject.") is None


def test_installing_a_lexicon_checks_the_ids_against_the_study_design(tmp_path, bm):
    real = bm.all_areas()[0].key_knowledge[0].id
    result = context.install_lexicon(
        "business-management",
        {"dot_points": {real: {"triggers": ["sole trader"]},
                        "bm-u9-aos9-kk99": {"triggers": ["nonsense"]}}},
        root=tmp_path, design=bm)
    assert result["dot_points"] == 1
    assert result["unknown"] == ["bm-u9-aos9-kk99"]
    written = (tmp_path / "study-designs" / "business-management-lexicon.yaml")
    assert written.exists()
    assert "bm-u9-aos9-kk99" not in written.read_text(encoding="utf-8")

    # A lexicon written against a different study design is refused outright,
    # rather than installed empty.
    with pytest.raises(ValueError, match="different version"):
        context.install_lexicon("business-management",
                                {"dot_points": {"bm-u9-aos9-kk99": {}}},
                                root=tmp_path, design=bm)


def test_an_installed_lexicon_changes_how_a_question_is_tagged(tmp_path, monkeypatch, bm):
    import blitz.studydesign.loader as loader
    from blitz.ingest.lexicon import load_lexicon
    from blitz.ingest.tag import KeywordTagger

    designs = tmp_path / "study-designs"
    designs.mkdir()
    from blitz.config import STUDY_DESIGN_DIR

    (designs / "business-management.yaml").write_text(
        (STUDY_DESIGN_DIR / "business-management.yaml").read_text(encoding="utf-8"),
        encoding="utf-8")
    monkeypatch.setattr(loader, "USER_DESIGN_DIR", designs)
    monkeypatch.setattr(loader, "STUDY_DESIGN_DIR", designs)
    load_lexicon.cache_clear()
    loader.load_study_design.cache_clear()

    question = ("Sanjeev is deciding whether to register as a sole trader or a "
                "partnership for his new landscaping venture.")
    target = next(kk.id for kk in bm.all_key_knowledge()
                  if kk.text.startswith("types of businesses"))

    before = KeywordTagger(bm).tag(question)
    context.install_lexicon(
        "business-management",
        {"dot_points": {target: {"triggers": ["sole trader", "partnership",
                                              "register as a"]}}},
        root=tmp_path, design=bm)
    after = KeywordTagger(bm).tag(question)

    assert after.kk_ids[:1] == [target]
    assert before.kk_ids[:1] != [target] or before.rejected
    load_lexicon.cache_clear()


def test_documents_are_kept_even_when_they_carry_no_lexicon(tmp_path, bm):
    result = context.add_context(
        "business-management",
        [("teaching-notes.md", b"# Notes\n\nThe cohort struggles with KPIs.")],
        root=tmp_path, design=bm)
    assert result["stored"] == ["teaching-notes.md"]
    assert result["lexicon"] is None
    assert any("No concept lexicon found" in n for n in result["notes"])
    kept = tmp_path / "sources" / "business-management" / "context" / "teaching-notes.md"
    assert "struggles with KPIs" in kept.read_text(encoding="utf-8")

    listed = context.list_context("business-management", root=tmp_path)
    assert [c["name"] for c in listed] == ["teaching-notes.md"]
    assert context.remove_context("business-management", "teaching-notes.md", root=tmp_path)
    assert context.list_context("business-management", root=tmp_path) == []
    # A name that tries to climb out of the folder is not a document.
    assert not context.remove_context("business-management", "../../secret", root=tmp_path)


def test_a_file_that_is_not_text_is_refused_by_name(tmp_path, bm):
    with pytest.raises(ValueError, match="not a text document"):
        context.add_context("business-management", [("book.pdf", b"%PDF")],
                            root=tmp_path, design=bm)


# --------------------------------------------------------------------------
# Through the pages
# --------------------------------------------------------------------------

def test_the_briefing_downloads_and_context_uploads(_client, bm):
    res = _client.get("/api/subjects/business-management/briefing")
    assert res.status_code == 200
    assert ("business-management-briefing-questions.md"
            in res.headers["content-disposition"])
    assert "Briefing questions" in res.text

    first = bm.all_areas()[0].key_knowledge[0].id
    answer = _answer(bm, {first: ["sole trader", "partnership"]}).encode()
    res = _client.post("/api/subjects/business-management/context",
                       files=[("files", ("answers.md", answer, "text/markdown"))])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["stored"] == ["answers.md"]
    assert body["lexicon"]["dot_points"] == 1
    assert body["lexicon"]["from"] == "answers.md"

    settings = _client.get("/api/settings").json()
    subject = next(s for s in settings["subjects"] if s["id"] == "business-management")
    assert subject["lexicon"] == 1
    assert [c["name"] for c in subject["context"]] == ["answers.md"]

    cleared = _client.post("/api/subjects/business-management/lexicon/clear")
    assert cleared.json() == {"cleared": True}
    dropped = _client.delete("/api/subjects/business-management/context/answers.md")
    assert dropped.status_code == 200
    settings = _client.get("/api/settings").json()
    subject = next(s for s in settings["subjects"] if s["id"] == "business-management")
    assert subject["lexicon"] == 0 and subject["context"] == []


def test_the_settings_page_and_an_unknown_subject(_client):
    assert _client.get("/settings").status_code == 200
    assert _client.get("/settings.js").status_code == 200
    assert _client.get("/api/subjects/nope/briefing").status_code == 404
    assert _client.post("/api/subjects/business-management/context",
                        files=[]).status_code == 400
