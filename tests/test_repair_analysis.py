"""Tests for the repair-loop analyser.

The classifier is the part that can silently be wrong — if it mis-buckets violations, the
recurrence counts lie and someone "teaches the skeleton" the wrong lesson. So every violation
message the pipeline actually emits is asserted to land on its intended rule, using strings
taken from the real gate code rather than paraphrases.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import repair_analysis as ra  # noqa: E402

# Verbatim samples of what each gate emits (pipeline/gates.py, pipeline/stages.py).
SAMPLES = {
    "citation-unresolvable": "objectives[0]: location '[00:07]' does not occur in the source — citations are copied from the document, never constructed",
    "glossary-term-repaired": "objectives[0]: value contains glossary term 'brand awareness', which never appears in Latin script in the source. If the source renders it collapsed...",
    "citation-empty": "budget[0]: empty anchor — value='around eighty'",
    "readiness-populated": "brief contains a `readiness` block — that field is computed by the runner, not by the model (SYNTHESIS.md rule 8). Remove it.",
    "agent-signed-off": "signoff.status must be 'draft' — sign-off is a human act (PRD DR-8)",
    "conflict-resolved": "conflicts[0]: status 'resolved_by_human' — synthesis emits 'open'; resolution is human-only (PRD DR-10)",
    "anchor-altered": "budget[0].evidence[0]: anchor 'around eighty thousand' does not match any extract anchor — refs are copied verbatim (SYNTHESIS.md rule 1)",
    "entry-without-evidence": "budget[0]: no evidence — every claim traces to an extract item",
    "render-uncited-line": "en: claim line with no citation tag — 'We recommend a larger budget.'",
    "render-unknown-source": "en: citation tag names no known source — 'Grow. [made_up 00:01]'",
    "render-glossary-lost": "el: glossary term 'media spend' is in the brief but missing from the render",
    "render-missing-section": "el: brief has open questions but the render has no '⚠' section heading — open questions and conflicts are the product",
    "tier-inferred": "sensitivity_tier 'S0' does not match the client config ('S1') — the tier is read from onboarding, never inferred (PRD DR-11)",
    "classification-uncited": "no evidence for the project_type decision — a routing call with no citation is a vibe",
    "fidelity-repaired": "annotated transcript differs from the original by more than [FIDELITY: ...] insertions — this stage annotates, it never repairs (TRANSCRIPTS.md §3)",
    "malformed-json": "not valid JSON: Expecting value: line 1 column 1",
    "no-output-file": "no file written at /run/extracts/talk.json",
    "schema-missing-required": "objectives/0: 'anchor' is a required property",
    "schema-additional-properties": "meta: Additional properties are not allowed ('foo' was unexpected)",
    "schema-invalid-enum": "meta/sensitivity_tier: 'S3' is not one of ['S0', 'S1']",
    "schema-wrong-type": "budget/0/confidence: 5 is not of type 'string'",
}


@pytest.mark.parametrize("expected_rule, message", list(SAMPLES.items()))
def test_each_violation_lands_on_its_rule(expected_rule, message):
    rule_id, _title = ra.classify_violation(message)
    assert rule_id == expected_rule, f"{message!r} classified as {rule_id}, expected {expected_rule}"


def test_classification_uncited_beats_the_generic_no_evidence_rule():
    """Order matters: 'no evidence for the project_type decision' must not fall into
    entry-without-evidence, which also contains 'no evidence'."""
    rule_id, _ = ra.classify_violation("no evidence for the project_type decision — a routing call with no citation is a vibe")
    assert rule_id == "classification-uncited"


def test_unknown_violation_is_bucketed_as_other_without_indices():
    rule_id, title = ra.classify_violation("deliverables[3]: some brand new failure mode we never wrote")
    assert rule_id == "other"
    assert "[3]" not in title and "[]" in title


def _manifest(*attempt_lists, stage="extraction", as_extracts=True):
    """Build a manifest whose extraction step carries the given per-source attempt lists."""
    if as_extracts:
        extracts = [
            {"source_id": f"s{i}", "attempts": [
                {"attempt": n + 1, "violations": v} for n, v in enumerate(attempts)
            ]}
            for i, attempts in enumerate(attempt_lists)
        ]
        return {"steps": [{"name": stage, "status": "pass", "extracts": extracts}]}
    return {"steps": [{"name": stage, "status": "pass", "attempts": [
        {"attempt": n + 1, "violations": v} for n, v in enumerate(attempt_lists[0])
    ]}]}


def test_recurring_first_attempt_rule_is_surfaced():
    """The case the tool exists for: the same rule fails first-attempt on every source."""
    cite = ["objectives[0]: location '[00:07]' does not occur in the source — never constructed"]
    m = _manifest([cite, []], [cite, []], [cite, []])  # 3 sources, each fixed on retry
    result = ra.analyse([("run1", m)])

    top = result["rules"][0]
    assert top["rule_id"] == "citation-unresolvable"
    assert top["first_attempt_hits"] == 3
    assert top["distinct_sites"] == 3
    assert result["totals"]["repair_rounds"] == 3


def test_clean_first_attempts_are_counted():
    m = _manifest([[]], [[]])
    totals = ra.analyse([("run1", m)])["totals"]
    assert totals["clean_first_attempts"] == 2
    assert totals["repair_rounds"] == 0


def test_single_artifact_stage_attempts_are_read():
    """Synthesis/render/classify record attempts on the step, not under extracts[]."""
    bad = ["brief contains a `readiness` block — computed by the runner"]
    m = _manifest([bad, []], stage="synthesis", as_extracts=False)
    result = ra.analyse([("run1", m)])
    assert result["rules"][0]["rule_id"] == "readiness-populated"


def test_load_manifests_reads_a_runs_parent(tmp_path):
    run = tmp_path / "20260101-000000"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps(_manifest([[]])), encoding="utf-8")
    loaded = ra.load_manifests(tmp_path)
    assert len(loaded) == 1 and loaded[0][0] == "20260101-000000"
