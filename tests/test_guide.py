"""A subject with no books yet is not empty-handed.

Adding a study design gives Blitz the dot points and nothing else. It also
writes the briefing that turns that into a starting point: every dot point
id with VCAA's wording, the fingerprint that pins them, and the rules for
whoever prepares the material.
"""

import json

import pytest

from blitz import guide
from blitz.corpus.sample import fingerprint
from blitz.studydesign import load_study_design


@pytest.fixture
def physics():
    return load_study_design("physics")


def test_the_guide_lists_every_dot_point_with_its_id(physics):
    text = guide.guide_text(physics)
    for area in physics.all_areas():
        for kk in area.key_knowledge:
            assert f"`{kk.id}`" in text, kk.id
            # VCAA's own wording, not the shortened label used on sheets.
            assert kk.text.replace("|", "\\|")[:60] in text
    assert f"`{fingerprint(physics)}`" in text
    for qt in physics.question_types:
        assert f"`{qt.id}`" in text


def test_the_guide_says_what_to_do_next(physics):
    text = guide.guide_text(physics)
    assert "blitz index <file> --subject physics" in text
    assert "blitz coverage physics" in text
    assert "blitz import-pack <file> --dry-run" in text
    assert "docs/question-pack-schema.md" in text
    assert "figure_zoom" in text
    assert "dot-points.json" in text
    # The number of dot points it claims is the number it lists.
    n = sum(len(a.key_knowledge) for a in physics.all_areas())
    assert f"**{n} dot points, no" in text


def test_an_unverified_design_is_called_out(tmp_path):
    import yaml

    from blitz.config import STUDY_DESIGN_DIR
    from blitz.studydesign.loader import load_study_design_file

    data = yaml.safe_load((STUDY_DESIGN_DIR / "physics.yaml").read_text(encoding="utf-8"))
    data["units"][0]["areas_of_study"][0]["key_knowledge"][0]["verified"] = False
    path = tmp_path / "physics.yaml"
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    text = guide.guide_text(load_study_design_file(path))
    assert "not all VCAA's own" in text
    assert "wording not from VCAA" in text

    assert "not all VCAA's own" not in guide.guide_text(load_study_design("physics"))


def test_the_payload_is_the_contract(physics):
    payload = guide.dot_points_payload(physics)
    assert payload["subject_id"] == "physics"
    assert payload["study_design_fingerprint"] == fingerprint(physics)
    assert payload["verified"] is True
    ids = [d["id"] for d in payload["dot_points"]]
    assert ids == [kk.id for a in physics.all_areas() for kk in a.key_knowledge]
    first = payload["dot_points"][0]
    assert set(first) == {"id", "unit", "area_of_study", "area_title", "text", "short"}
    assert first["unit"] == 3


def test_writing_it_creates_the_subject_folder(tmp_path, physics):
    written = guide.write_subject_guide("physics", root=tmp_path, design=physics)
    folder = tmp_path / "sources" / "physics"
    assert [p.parent for p in written] == [folder, folder]
    assert (folder / "INDEXING-GUIDE.md").exists()
    payload = json.loads((folder / "dot-points.json").read_text(encoding="utf-8"))
    assert payload["subject_id"] == "physics"

    # Rewriting replaces rather than appends.
    before = (folder / "INDEXING-GUIDE.md").read_text(encoding="utf-8")
    guide.write_subject_guide("physics", root=tmp_path, design=physics)
    assert (folder / "INDEXING-GUIDE.md").read_text(encoding="utf-8") == before


def test_the_dot_points_command_prints_the_same_payload(physics, capsys):
    from blitz.cli import main

    assert main(["dot-points", "physics", "--json"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed == guide.dot_points_payload(physics)
