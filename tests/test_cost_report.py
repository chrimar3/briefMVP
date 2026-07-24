"""Tests for the cost re-derivation. The aggregation is what the deck's number rests on, so
it is checked against synthetic manifests with known costs."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import cost_report as cost  # noqa: E402


def _sub(cost_usd, model="claude-haiku-4-5-20251001"):
    return {"attempt": 1, "subagent": {"cost_usd": cost_usd, "model_ids": [model]}}


def _full_run(run_id, render_cost):
    """A complete one-attempt Stage-1 run with fixed per-stage costs."""
    return (run_id, {"steps": [
        {"name": "classification", "kind": "model", "status": "pass",
         "classification": {"attempts": [_sub(0.03)]}},
        {"name": "fidelity_check", "kind": "model", "status": "pass",
         "fidelity": [{"attempts": [_sub(0.04)]}]},
        {"name": "extraction", "kind": "model", "status": "pass",
         "extracts": [{"attempts": [_sub(0.10)]}, {"attempts": [_sub(0.10)]},
                      {"attempts": [_sub(0.10)]}, {"attempts": [_sub(0.10)]}]},
        {"name": "synthesis", "kind": "model", "status": "pass",
         "synthesis": {"attempts": [_sub(0.80, "claude-sonnet-5")]}},
        {"name": "render", "kind": "model", "status": "pass",
         "render": {"attempts": [_sub(render_cost, "claude-sonnet-5")]}},
    ]})


def test_stage1_total_sums_every_stage():
    result = cost.analyse([_full_run("r1", 0.70)])
    assert len(result["stage1"]) == 1
    # 0.03 + 0.04 + 4×0.10 + 0.80 + 0.70 = 1.97
    assert round(result["stage1"][0]["total"], 2) == 1.97


def test_extraction_sums_all_four_source_attempts():
    result = cost.analyse([_full_run("r1", 0.70)])
    ex = result["stage1"][0]["by_stage"]["extraction"]
    assert round(ex["cost"], 2) == 0.40 and ex["attempts"] == 4


def test_a_repair_round_marks_a_run_not_clean():
    run_id, m = _full_run("r1", 0.70)
    m["steps"][3]["synthesis"]["attempts"].append(_sub(0.80, "claude-sonnet-5"))  # 2nd synthesis attempt
    result = cost.analyse([(run_id, m)])
    assert result["stage1"][0]["clean"] is False


def test_incomplete_run_is_not_counted_as_stage1():
    """A run that failed before render is not a per-brief cost sample."""
    run_id, m = _full_run("r1", 0.70)
    m["steps"] = m["steps"][:3]  # no synthesis / render
    assert cost.analyse([(run_id, m)])["stage1"] == []


def test_creative_ab_is_reported_separately():
    m = {"steps": [{"name": "creative_shadow", "kind": "model", "status": "pass",
                    "creative": [{"attempts": [_sub(0.27, "claude-sonnet-5")]},
                                 {"attempts": [_sub(0.47, "claude-opus-4-8")]}]}]}
    result = cost.analyse([("r1", m)])
    assert round(result["creative"][0]["cost"], 2) == 0.74


def test_model_names_are_shortened_to_aliases():
    assert cost._short_model("claude-haiku-4-5-20251001") == "haiku"
    assert cost._short_model("claude-sonnet-5") == "sonnet"
    assert cost._short_model("claude-opus-4-8") == "opus"


def test_shipped_cost_model_doc_quotes_the_ratio_not_the_estimate(repo_root):
    text = (repo_root / "docs" / "COST_MODEL.md").read_text(encoding="utf-8")
    assert "17:1" in text
    assert "smallest line" in text
