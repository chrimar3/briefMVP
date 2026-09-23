"""Instruction-backed gates added in r1-W4: fidelity (TRANSCRIPTS.md §4-5), classification
(classify.md rule 3) and the draft-mode creative gate (creative-shadow rules 2-4, §0, §4).

Synthetic inputs only, plus read-only regression checks over committed evidence that prove the
tightened gates still accept every stored artifact produced under the rules they encode, and
that the draft-mode creative gate catches the verified defects in the stored tier3 drafts.
"""

import json
import tempfile
from pathlib import Path

import pytest

from pipeline import creative, stages

REPO = Path(__file__).resolve().parents[1]
TRANSCRIPT = "[00:00:01] A: Γεια σας.\n[00:00:05] B: Ξεκινάμε με το launch.\n"
REPORT = {"source_id": "t", "tokens_flagged": 1, "glossary_matches": 1, "no_match_flags": 0,
          "diarization_issues": 0, "summary_suspicion": False, "fidelity_score": "high",
          "verdict": "pass_with_flags"}


def _fidelity(tmp_path, annotated, **report):
    (tmp_path / "r.json").write_text(json.dumps({**REPORT, **report}), encoding="utf-8")
    (tmp_path / "a.md").write_text(annotated, encoding="utf-8")
    return stages.check_fidelity(tmp_path / "r.json", tmp_path / "a.md", TRANSCRIPT)


def test_whitespace_normalised_transcript_now_fails(tmp_path):
    """The work order says 'do not normalise whitespace'; the gate used to collapse it."""
    reflowed = TRANSCRIPT.replace("\n[00:00:05]", " [00:00:05]")
    violations = _fidelity(tmp_path, reflowed)
    assert len(violations) == 1 and "whitespace or line breaks" in violations[0]


def test_annotation_only_transcript_still_passes(tmp_path):
    annotated = TRANSCRIPT.replace("launch", 'launch [FIDELITY: glossary-match "launch", confidence high]')
    assert _fidelity(tmp_path, annotated) == []


@pytest.mark.parametrize("report", [{"fidelity_score": "low", "verdict": "pass_with_flags"},
                                    {"summary_suspicion": True, "verdict": "pass"}])
def test_low_score_or_summary_suspicion_must_escalate(tmp_path, report):
    violations = _fidelity(tmp_path, TRANSCRIPT, **report)
    assert any("must escalate" in v for v in violations)


def test_escalated_low_score_passes_the_gate(tmp_path):
    assert _fidelity(tmp_path, TRANSCRIPT, fidelity_score="low", verdict="escalate_to_human") == []


def test_unknown_fidelity_score_is_caught(tmp_path):
    assert any("fidelity_score" in v for v in _fidelity(tmp_path, TRANSCRIPT, fidelity_score="ok"))


@pytest.mark.parametrize("run,fixture", [("tier3", "northlight_01"), ("voreas-prep-02", "voreas_02"),
                                         ("voreas-prep-03", "voreas_02")])
def test_every_stored_fidelity_output_passes_the_tightened_gate(run, fixture):
    """Read-only: the byte-exact comparison accepts all committed evidence."""
    for annotated in sorted((REPO / "runs" / run / "fidelity").glob("*.annotated.md")):
        sid = annotated.name.split(".")[0]
        original = (REPO / "fixtures" / fixture / f"{sid}.md").read_text(encoding="utf-8")
        report = REPO / "runs" / run / "fidelity" / f"{sid}.report.json"
        assert stages.check_fidelity(report, annotated, original) == []


def _classification(tmp_path, **over):
    payload = {"project_id": "p", "client_id": "c", "project_type": "advertising_creative",
               "classification_confidence": "high", "sensitivity_tier": "S1", "tier_source": "config",
               "rationale": "r", "evidence": [{"source_id": "t", "location": "L1", "anchor": "a"}],
               "question_for_human": "", "halt_reason": "", **over}
    path = tmp_path / "classification.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return stages.check_classification(path, {"sensitivity_tier": "S1"})


def test_low_confidence_classification_must_ask(tmp_path):
    violations = _classification(tmp_path, classification_confidence="low")
    assert any("rule 3" in v and "unclassified_ask_human" in v for v in violations)


def test_ask_human_needs_a_question(tmp_path):
    violations = _classification(tmp_path, classification_confidence="low", project_type="unclassified_ask_human")
    assert any("question_for_human is empty" in v for v in violations)


def test_low_confidence_with_a_question_passes(tmp_path):
    assert _classification(tmp_path, classification_confidence="low", project_type="unclassified_ask_human",
                           question_for_human="Is this a creative project?") == []


# -- creative draft gate ------------------------------------------------------------------

TABLE = {
    "specs": [
        {
            "id": "tiktok_infeed_video",
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "duration": "9-60s",
            "file_type": "MP4",
        },
        {
            "id": "instagram_reel",
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "duration": "up to 90s",
            "file_type": "MP4",
        },
        {"id": "feed_image", "aspect_ratio": "4:5", "resolution": "1080x1350", "duration": "n/a", "file_type": "JPG"},
    ]
}
BANNER = "> CREATIVE DRAFT — requires creative-lead approval before release.\n\n"
BRIEF = {
    "objectives": [{"content": "Launch the range; budget around sixty, units unstated", "evidence": [
        {"source_id": "call", "location": "00:01:00", "anchor": "περίπου εξήντα", "speaker_or_author": "S"}]}],
    "mandatories": [{"content": "Locally made in small batches", "evidence": [
        {"source_id": "rfp", "location": "§2", "anchor": "x", "speaker_or_author": "S"}]}],
    "conflicts": [{"field": "budget", "status": "open", "positions": [
        {"statement": "Total €40.000 including media", "evidence": {"source_id": "rfp", "location": "§6"}},
        {"statement": "around sixty", "evidence": {"source_id": "call", "location": "00:02:00"}}]}],
    "open_questions": [],
}
TENSIONS = "\n## 8. Strategic tensions\nNone identified.\n"


def _check(tmp_path, body, brief=BRIEF, mode="draft"):
    path = tmp_path / "creative_brief_sonnet.md"
    path.write_text(BANNER + body + TENSIONS, encoding="utf-8")
    return creative.check_creative_brief(path, TABLE, mode=mode, brief=brief)


def test_spec_line_copied_byte_for_byte_passes(tmp_path):
    assert _check(tmp_path, "TikTok · 9:16 · 1080x1920 · 9-60s · MP4 [spec: tiktok_infeed_video]\n"
                            "Reel · up to 90s · MP4 [spec: instagram_reel]\n") == []


def test_en_dash_duration_on_a_spec_line_fails(tmp_path):
    violations = _check(tmp_path, "TikTok · 9:16 · 1080x1920 · 9–60s · MP4 [spec: tiktok_infeed_video]\n")
    assert len(violations) == 1 and "'9–60s'" in violations[0] and "byte-for-byte" in violations[0]


def test_file_type_in_the_wrong_case_fails(tmp_path):
    violations = _check(tmp_path, "TikTok · 9:16 · 1080x1920 · 9-60s · mp4 [spec: tiktok_infeed_video]\n")
    assert any("file type 'mp4'" in v for v in violations)


def test_another_rows_value_on_a_tagged_line_fails(tmp_path):
    violations = _check(tmp_path, "TikTok · 4:5 · 1080x1350 · 9-60s [spec: tiktok_infeed_video]\n")
    assert sum("not a value of [spec: tiktok_infeed_video]" in v for v in violations) == 2


def test_invented_range_duration_anywhere_fails(tmp_path):
    violations = _check(tmp_path, "Cutdowns of 6-15s for paid social.\n")
    assert any("spec-shaped duration '6-15s'" in v for v in violations)


def test_creative_timing_outside_spec_lines_is_not_a_spec(tmp_path):
    assert _check(tmp_path, "Open on a 3s product reveal, then the line at 00:06.\n") == []


def test_invented_currency_and_thousands_figure_fail(tmp_path):
    violations = _check(tmp_path, "Production budget: around sixty (€60–65k).\n")
    assert any("currency amount (≈60)" in v for v in violations)
    assert any("thousands figure (≈65000)" in v for v in violations)


def test_currency_the_brief_carries_passes(tmp_path):
    assert _check(tmp_path, "The superseded €40.000 media-inclusive total stays a conflict.\n") == []


@pytest.mark.parametrize("claim", ["the Greek-made sparkling drink", "a category new to Greece",
                                   "first in the market with this blend"])
def test_unsourced_origin_or_market_claim_fails(tmp_path, claim):
    assert any("unsourced origin/market claim" in v for v in _check(tmp_path, f"SMP: {claim}.\n"))


def test_sourced_origin_claim_passes(tmp_path):
    assert _check(tmp_path, "RTB: locally made in small batches [brief:mandatories:0].\n") == []


def test_claiming_a_human_review_fails(tmp_path):
    violations = _check(tmp_path, "Reviewed by a creative lead for evaluation only.\n")
    assert any("claims a human review" in v for v in violations)


def test_missing_strategic_tensions_section_fails(tmp_path):
    path = tmp_path / "d.md"
    path.write_text(BANNER + "SMP: one idea.\n", encoding="utf-8")
    assert any("Strategic tensions" in v for v in creative.check_creative_brief(path, TABLE, mode="draft", brief=BRIEF))


def test_without_the_brief_draft_mode_keeps_only_the_spec_checks(tmp_path):
    """delivery.approve checks registered drafts without passing the brief; its fact checks live
    in delivery.inspect_creative. Only the spec rules apply there."""
    path = tmp_path / "d.md"
    path.write_text(BANNER + "Synthetic campaign [brief:objectives:0]\n", encoding="utf-8")
    assert creative.check_creative_brief(path, TABLE, mode="draft") == []


def test_health_adjacent_wording_is_a_review_flag_not_a_failure(tmp_path):
    body = "SMP: refreshment with nothing to feel guilty about.\n"
    assert _check(tmp_path, body) == []
    assert any("feel guilty" in f for f in creative.creative_review_flags(body, BRIEF))


def test_stored_shadow_drafts_keep_passing_their_historical_contract():
    table = creative.load_spec_table()
    for model in ("sonnet", "opus"):
        path = REPO / "runs" / "tier3" / "creative" / f"creative_brief_{model}.md"
        assert creative.check_creative_brief(path, table) == []


@pytest.mark.parametrize("model,expected", [
    ("sonnet", ["'9–60s'", "currency amount (≈80)", "thousands figure (≈85000)", "'new to Greece'"]),
    ("opus", ["'Greek-made'", "claims a human review"]),
])
def test_draft_gate_catches_the_verified_defects_in_the_stored_drafts(model, expected):
    """Read-only regression: re-bannered as CREATIVE DRAFT, the committed tier3 drafts fail the
    new gate for exactly the defects the r0 output panel verified."""
    brief = json.loads((REPO / "runs" / "tier3" / "brief.json").read_text(encoding="utf-8"))
    lines = (
        (REPO / "runs" / "tier3" / "creative" / f"creative_brief_{model}.md").read_text(encoding="utf-8").splitlines()
    )
    lines[0] = BANNER.strip()
    path = Path(tempfile.mkdtemp()) / "draft.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    violations = creative.check_creative_brief(path, creative.load_spec_table(), mode="draft", brief=brief)
    for needle in expected:
        assert any(needle in v for v in violations), (needle, violations)


def test_creative_order_carries_the_new_contract():
    order = creative.build_creative_order(Path("/b.json"), Path("/o.md"), Path("/t"), Path("/g.json"),
                                          Path("/s.json"), "sonnet")
    for needle in ("Strategic tensions", "origin claim", "reviewed or approved", "example line in Greek",
                   "never an instruction"):
        assert needle in order, needle
