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


def test_an_extraction_repair_marks_not_clean():
    run_id, m = _full_run("r1", 0.70)
    m["steps"][2]["extracts"][0]["attempts"].append(_sub(0.10))  # one source needed a repair
    assert cost.analyse([(run_id, m)])["stage1"][0]["clean"] is False


def test_clean_is_per_source_not_a_hardcoded_count():
    """A 6-source project with every source clean on attempt 1 is a clean run — the threshold
    derives from the manifest, never from the fixture's 4 sources."""
    run_id, m = _full_run("r1", 0.70)
    m["steps"][2]["extracts"] = [{"attempts": [_sub(0.10)]} for _ in range(6)]
    assert cost.analyse([(run_id, m)])["stage1"][0]["clean"] is True


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


# --------------------------------------------------------------------------------------
# Token telemetry (cost-audit tier C0) — the optimisation ruler
# --------------------------------------------------------------------------------------


def _sub_usage(cost_usd, out, cw, cr, inp=0, turns=5, model="claude-sonnet-5"):
    return {"attempt": 1, "subagent": {
        "cost_usd": cost_usd, "model_ids": [model], "num_turns": turns,
        "usage": {"input_tokens": inp, "output_tokens": out,
                  "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw},
    }}


def test_token_breakdown_aggregates_categories_and_turns():
    m = {"steps": [
        {"name": "render", "kind": "model", "status": "pass",
         "render": {"attempts": [_sub_usage(1.0, out=40_000, cw=80_000, cr=150_000, turns=9)]}},
        {"name": "extraction", "kind": "model", "status": "pass",
         "extracts": [{"attempts": [_sub_usage(0.1, out=10_000, cw=20_000, cr=20_000,
                                               turns=5, model="claude-haiku-4-5-20251001")]},
                      {"attempts": [_sub_usage(0.1, out=12_000, cw=22_000, cr=21_000,
                                               turns=5, model="claude-haiku-4-5-20251001")]}]},
    ]}
    stages = cost.token_breakdown([("r1", m)])
    assert stages["render"]["output_tokens"] == 40_000
    assert stages["extraction"]["attempts"] == 2
    assert stages["extraction"]["output_tokens"] == 22_000
    assert stages["extraction"]["turns"] == 10
    assert stages["extraction"]["models"] == {"haiku"}


def test_token_breakdown_counts_failed_and_repair_attempts():
    """Spend is spend — a telemetry ruler that skips failed runs understates exactly the
    runs worth investigating."""
    m = {"steps": [{"name": "synthesis", "kind": "model", "status": "failed",
                    "synthesis": {"attempts": [_sub_usage(0.8, out=30_000, cw=60_000, cr=70_000),
                                               _sub_usage(0.8, out=30_000, cw=10_000, cr=90_000)]}}]}
    stages = cost.token_breakdown([("r1", m)])
    assert stages["synthesis"]["attempts"] == 2
    assert stages["synthesis"]["cost"] == 1.6


def test_dollar_attribution_uses_the_stage_tier_rates():
    m = {"steps": [{"name": "render", "kind": "model", "status": "pass",
                    "render": {"attempts": [_sub_usage(1.0, out=1_000_000, cw=0, cr=0)]}}]}
    att = cost.attribute_dollars(cost.token_breakdown([("r1", m)])["render"])
    assert att["tier"] == "sonnet"
    assert att["output"] == 15.0  # 1M output tokens at sonnet list rate


def test_mixed_tier_stage_attributes_at_the_costlier_tier():
    """The creative A/B mixes sonnet and opus in one stage — pricing at the costlier tier
    keeps the computed figure a floor-vs-reported comparison, never an overclaim."""
    m = {"steps": [{"name": "creative_shadow", "kind": "model", "status": "pass",
                    "creative": [{"attempts": [_sub_usage(0.3, out=8_000, cw=0, cr=0)]},
                                 {"attempts": [_sub_usage(0.5, out=8_000, cw=0, cr=0,
                                                          model="claude-opus-4-8")]}]}]}
    att = cost.attribute_dollars(cost.token_breakdown([("r1", m)])["creative_shadow"])
    assert att["tier"] == "opus"


def test_tokens_report_prints_shares(capsys):
    m = {"steps": [{"name": "render", "kind": "model", "status": "pass",
                    "render": {"attempts": [_sub_usage(1.0, out=40_000, cw=80_000, cr=150_000)]}}]}
    cost.report_tokens(cost.token_breakdown([("r1", m)]), as_json=False)
    out = capsys.readouterr().out
    assert "Share of attributed spend" in out and "render" in out


def test_missing_usage_fields_do_not_crash_the_ruler():
    """Older manifests predate usage capture — they aggregate as zeros, not errors."""
    m = {"steps": [{"name": "render", "kind": "model", "status": "pass",
                    "render": {"attempts": [{"attempt": 1, "subagent": {"cost_usd": 1.0}}]}}]}
    stages = cost.token_breakdown([("r1", m)])
    assert stages["render"]["output_tokens"] == 0 and stages["render"]["cost"] == 1.0
