"""Tier-0 DoD: both schemas parse as valid JSON Schema.

Plus the two scope guarantees the schemas are supposed to enforce structurally — if
either regresses, the PRD's "governance via topology, not policy documents" claim fails.
"""

import json

import pytest
from jsonschema import Draft7Validator

SCHEMAS = ("brief_schema", "extract_schema")


@pytest.fixture(params=SCHEMAS)
def schema(request, repo_root):
    path = repo_root / "schema" / f"{request.param}.json"
    assert path.is_file(), f"missing schema file: {path}"
    return json.loads(path.read_text(encoding="utf-8"))


def test_schema_is_valid_json_schema(schema):
    """DoD 1 — parses as JSON and is itself a legal Draft-07 schema."""
    Draft7Validator.check_schema(schema)


def test_schema_declares_draft07(schema):
    assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"


def test_brief_schema_excludes_regulated_tiers(repo_root):
    """PRD DR-11: S2/S3 are unrepresentable in v1, not merely discouraged."""
    schema = json.loads((repo_root / "schema" / "brief_schema.json").read_text(encoding="utf-8"))
    tiers = schema["properties"]["meta"]["properties"]["sensitivity_tier"]["enum"]
    assert tiers == ["S0", "S1"]


def test_extract_schema_requires_citations(repo_root):
    """SOURCES.md rule 2: no location + anchor -> the value does not exist."""
    schema = json.loads((repo_root / "schema" / "extract_schema.json").read_text(encoding="utf-8"))
    item = schema["definitions"]["item"]
    assert {"location", "anchor"} <= set(item["required"])
    assert item["properties"]["location"]["minLength"] == 1
    assert item["properties"]["anchor"]["minLength"] == 1


def test_brief_entry_requires_evidence(repo_root):
    """Every canonical claim carries at least one evidence ref."""
    schema = json.loads((repo_root / "schema" / "brief_schema.json").read_text(encoding="utf-8"))
    entry = schema["definitions"]["brief_entry"]
    assert "evidence" in entry["required"]
    assert entry["properties"]["evidence"]["minItems"] == 1
