"""The published schema must describe what the importer actually does.

A spec that has drifted from the code is worse than no spec: whoever is building
a pack against it will produce data that silently does not import the way they
expect. These tests tie the JSON Schema, the prose and the importer together.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "docs" / "question-pack.schema.json"
PROSE_PATH = ROOT / "docs" / "question-pack-schema.md"
IMPORTER_PATH = ROOT / "blitz" / "ingest" / "pack.py"


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def importer_source():
    return IMPORTER_PATH.read_text(encoding="utf-8")


def _keys_read(source: str, var: str) -> set[str]:
    """Field names the importer pulls off a given dict."""
    pattern = rf'{re.escape(var)}(?:\.get\(|\[)"([a-z_]+)"'
    return set(re.findall(pattern, source))


def test_the_schema_is_well_formed(schema):
    assert schema["$schema"].endswith("2020-12/schema")
    assert schema["type"] == "object"
    assert set(schema["required"]) == {"subject_id", "source", "questions"}
    for name in ("status", "source", "question", "part", "answer", "figure"):
        assert name in schema["$defs"], f"missing $defs/{name}"


def test_every_documented_question_field_is_read(schema, importer_source):
    """A documented field the importer ignores is a lie in the spec."""
    documented = set(schema["$defs"]["question"]["properties"])
    read = _keys_read(importer_source, "q")
    ignored = documented - read
    assert not ignored, f"documented but never read by the importer: {sorted(ignored)}"


def test_every_question_field_the_importer_reads_is_documented(schema,
                                                               importer_source):
    documented = set(schema["$defs"]["question"]["properties"])
    read = _keys_read(importer_source, "q")
    # Keys the importer reads off other dicts that share the name `q`-adjacent
    # helpers use; these are not pack fields.
    internal = {"path", "pt_width"}
    undocumented = read - documented - internal
    assert not undocumented, f"read but undocumented: {sorted(undocumented)}"


def test_source_fields_match(schema, importer_source):
    documented = set(schema["$defs"]["source"]["properties"])
    read = _keys_read(importer_source, "source")
    assert not documented - read, f"documented, unread: {sorted(documented - read)}"
    assert not read - documented, f"read, undocumented: {sorted(read - documented)}"


def test_figure_fields_match(schema, importer_source):
    documented = set(schema["$defs"]["figure"]["properties"])
    read = _keys_read(importer_source, "fig")
    assert not documented - read, f"documented, unread: {sorted(documented - read)}"
    assert not read - documented, f"read, undocumented: {sorted(read - documented)}"


def test_top_level_fields_match(schema, importer_source):
    documented = set(schema["properties"])
    read = _keys_read(importer_source, "pack")
    assert not documented - read, f"documented, unread: {sorted(documented - read)}"
    assert not read - documented, f"read, undocumented: {sorted(read - documented)}"


def test_the_enums_match_the_importer(schema, importer_source):
    statuses = set(schema["$defs"]["status"]["enum"])
    for value in statuses:
        assert f'"{value}"' in importer_source, \
            f"status {value!r} is in the schema but the importer never mentions it"

    kinds = set(schema["$defs"]["source"]["properties"]["kind"]["enum"])
    from blitz.cli import build_parser

    cli_kinds = set()
    for action in build_parser()._subparsers._group_actions[0].choices[
            "ingest"]._actions:
        if action.dest == "kind" and action.choices:
            cli_kinds = set(action.choices)
    assert kinds == cli_kinds, f"schema kinds {kinds} vs CLI {cli_kinds}"


def test_the_example_pack_exercises_the_documented_fields(schema):
    """The example is what people copy, so it should show the real shape."""
    pack = json.loads((ROOT / "packs" / "example-physics.json").read_text())
    used = {k for q in pack["questions"] for k in q}
    for field in ("id", "kk_ids", "question_type", "stem", "figures"):
        assert field in used, f"the example never shows {field!r}"


def test_the_prose_example_is_valid_json_and_imports(tmp_path, conn):
    """The example record in the prose has to actually work."""
    from blitz.corpus.sample import fingerprint
    from blitz.ingest.pack import validate
    from blitz.studydesign import load_study_design

    text = PROSE_PATH.read_text(encoding="utf-8")
    block = re.search(r"## Example record\n.*?```json\n(.*?)\n```", text, re.S)
    assert block, "the prose has no example record"
    pack = json.loads(block.group(1))

    design = load_study_design("physics")
    assert pack["study_design_fingerprint"] == fingerprint(design), \
        "the example's fingerprint is stale"

    # Drop the figures: they point at a PDF this machine does not have.
    for q in pack["questions"]:
        q.pop("figures", None)
        q.pop("render_mode", None)
        q.pop("answer_mode", None)
    report = validate(pack, design, tmp_path)
    assert report.ok, report.errors


def test_the_prose_documents_every_schema_field(schema):
    text = PROSE_PATH.read_text(encoding="utf-8")
    for field in schema["$defs"]["question"]["properties"]:
        assert f"`{field}`" in text, f"{field!r} is in the schema but not the prose"
