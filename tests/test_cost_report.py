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


# --------------------------------------------------------------------------------------
# r1-W3: verify-extract counted, tokens by model as the default unit, repairs not hidden
# --------------------------------------------------------------------------------------


def _usage_sub(session, model, inp, out, cr, cw, cost=0.0, turns=5):
    return {"attempt": 1, "subagent": {
        "agent": "x", "session_id": session, "model_ids": [model], "cost_usd": cost, "num_turns": turns,
        "usage": {"input_tokens": inp, "output_tokens": out,
                  "cache_read_input_tokens": cr, "cache_creation_input_tokens": cw},
    }}


def _routing_validate_shape():
    """The usage recorded in runs/routing-validate-01 (local run store, 2026-07-29): one source,
    an extraction repaired once and a sonnet verify-extract. Numbers copied from its manifest."""
    return ("routing-validate-01", {"started_ts": "2026-07-29T21:42:30", "steps": [
        {"name": "extraction", "kind": "model", "status": "pass", "extracts": [{
            "source_id": "transcript_kickoff",
            "attempts": [_usage_sub("e1", "claude-sonnet-5", 6, 26634, 24710, 40568),
                         _usage_sub("e2", "claude-sonnet-5", 34, 12987, 399611, 49498)],
            "verification": {"model": "sonnet", "risk_classes": ["figures"],
                             "attempts": [_usage_sub("v1", "claude-sonnet-5", 6, 6587, 20413, 17689)]},
        }]},
    ]})


def test_verify_extract_attempts_are_counted_as_their_own_stage():
    ledger = cost.token_ledger([_routing_validate_shape()])
    assert ledger["rows"][("extraction", "sonnet")]["total"] == 554_048
    assert ledger["rows"][("verification", "sonnet")]["total"] == 44_695
    assert ledger["rows"][("verification", "sonnet")]["calls"] == 1


def test_routing_validate_shape_totals_598743_tokens():
    """The figure the stakeholder material had to sum by hand now comes out of the ruler."""
    assert cost.token_ledger([_routing_validate_shape()])["total"]["total"] == 598_743


def test_token_breakdown_has_a_verification_row():
    stages = cost.token_breakdown([_routing_validate_shape()])
    assert stages["verification"]["attempts"] == 1
    assert stages["verification"]["output_tokens"] == 6_587
    assert stages["extraction"]["attempts"] == 2


def test_ledger_keys_tokens_by_resolved_model():
    m = {"steps": [
        {"name": "classification", "kind": "model", "status": "pass",
         "classification": {"attempts": [_usage_sub("c", "claude-haiku-4-5-20251001", 1, 10, 100, 1000)]}},
        {"name": "synthesis", "kind": "model", "status": "pass",
         "synthesis": {"attempts": [_usage_sub("s", "claude-sonnet-5", 2, 20, 200, 2000)]}},
    ]}
    ledger = cost.token_ledger([("r", m)])
    assert ledger["by_model"]["haiku"] == {"calls": 1, "fresh_input": 1, "output": 10, "cache_read": 100,
                                           "cache_write": 1000, "total": 1111}
    assert ledger["by_model"]["sonnet"]["total"] == 2222


def test_attempts_copied_into_a_resumed_run_are_counted_once():
    run_a = ("a", {"steps": [{"name": "synthesis", "kind": "model", "status": "pass",
                              "synthesis": {"attempts": [_usage_sub("same", "claude-sonnet-5", 0, 10, 0, 0)]}}]})
    run_b = ("b", {"steps": [{"name": "synthesis", "kind": "model", "status": "pass", "from_earlier_run": True,
                              "synthesis": {"attempts": [_usage_sub("same", "claude-sonnet-5", 0, 10, 0, 0)]}}]})
    ledger = cost.token_ledger([run_a, run_b])
    assert ledger["total"]["output"] == 10 and ledger["duplicates"] == 1
    assert cost.token_ledger([run_a, run_b], dedupe=False)["total"]["output"] == 20


def test_verification_repair_marks_a_run_not_clean():
    run_id, m = _full_run("r1", 0.70)
    m["steps"][2]["extracts"][0]["verification"] = {"attempts": [_sub(0.05), _sub(0.05)]}
    result = cost.analyse([(run_id, m)])
    assert result["stage1"][0]["clean"] is False
    assert result["stage1"][0]["by_stage"]["verification"]["attempts"] == 2


def test_verification_cost_is_in_the_stage1_total():
    run_id, m = _full_run("r1", 0.70)
    m["steps"][2]["extracts"][0]["verification"] = {"attempts": [_sub(0.05)]}
    assert round(cost.analyse([(run_id, m)])["stage1"][0]["total"], 2) == 2.02


def test_per_brief_view_lists_repaired_runs_next_to_clean_ones(capsys):
    clean = _full_run("clean-run", 0.70)
    rid, repaired = _full_run("repaired-run", 0.70)
    repaired["steps"][3]["synthesis"]["attempts"].append(_sub(0.80, "claude-sonnet-5"))
    runs = [clean, (rid, repaired)]
    briefs = cost.complete_briefs(runs)
    assert {b["run"]: b["clean"] for b in briefs} == {"clean-run": True, "repaired-run": False}
    means = cost.brief_means(briefs)
    assert means["all"]["n"] == 2 and means["clean"]["n"] == 1
    cost.report_ledger(cost.token_ledger(runs), briefs, as_json=False)
    out = capsys.readouterr().out
    assert "repaired-run" in out and "clean-run" in out
    assert "all complete runs" in out and "clean runs only" in out


def test_default_view_is_tokens_and_prints_no_dollars(capsys):
    cost.report_ledger(cost.token_ledger([_routing_validate_shape()]), [], as_json=False)
    out = capsys.readouterr().out
    assert "TOKENS BY MODEL" in out and "598,743" in out
    assert "$" not in out


def test_usd_view_is_labelled_a_footnote(capsys):
    cost.report(cost.analyse([_full_run("r1", 0.70)]), 38.0, as_json=False)
    out = capsys.readouterr().out
    assert out.lstrip().startswith("USD FOOTNOTE") and "not the stakeholder unit" in out.lower()


def test_main_defaults_to_the_token_ledger(tmp_path, capsys):
    run = tmp_path / "routing-validate-01"
    run.mkdir()
    (run / "run_manifest.json").write_text(json.dumps(_routing_validate_shape()[1]), encoding="utf-8")
    assert cost.main([str(run)]) == 0
    assert "598,743" in capsys.readouterr().out


def test_routing_era_reads_the_extraction_models():
    assert cost.routing_era(_routing_validate_shape()[1]) == ("current", "extraction models")
    assert cost.routing_era(_full_run("r1", 0.70)[1])[0] == "haiku-era"
    assert cost.routing_era({"started_ts": "2026-07-24T10:00:00", "steps": []}) == ("haiku-era", "run date")


def test_risk_replay_counts_the_base_branch_and_skips_copies(tmp_path):
    run_a = tmp_path / "a" / "extracts"
    run_b = tmp_path / "b" / "extracts"
    run_a.mkdir(parents=True)
    run_b.mkdir(parents=True)
    quiet = {"source_id": "s1", "objectives": [{"value": "grow awareness", "confidence": "high"}]}
    risky = {"source_id": "s2", "budget": [{"value": "€90.000", "confidence": "high"}]}
    (run_a / "s1.json").write_text(json.dumps(quiet), encoding="utf-8")
    (run_a / "s2.json").write_text(json.dumps(risky), encoding="utf-8")
    (run_b / "s2.json").write_text(json.dumps(risky), encoding="utf-8")  # byte-identical copy
    result = cost.risk_replay([tmp_path])
    assert result["unique_extracts"] == 2 and result["duplicate_copies_skipped"] == 1
    assert result["base_branch"] == 1 and result["per_class"]["figures"] == 1
    assert result["sole_trigger"]["figures"] == 1


# ---- round 2 (W-D): symlinks, the round-2 era, verifier effectiveness ---------------------


def _write_run(root, name, manifest):
    run = root / name
    run.mkdir(parents=True)
    (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run


def test_load_runs_skips_a_symlinked_latest_dir(tmp_path):
    """runs/r2-live/latest -> vo-r3 used to list vo-r3 twice (once as `latest`)."""
    _write_run(tmp_path, "vo-r3", _routing_validate_shape()[1])
    (tmp_path / "latest").symlink_to("vo-r3", target_is_directory=True)
    assert [run_id for run_id, _m in cost.load_runs(tmp_path)] == ["vo-r3"]


def test_symlinked_latest_is_not_a_second_brief(tmp_path):
    rid, m = _full_run("vo-r3", 0.70)
    _write_run(tmp_path, rid, m)
    (tmp_path / "latest").symlink_to(rid, target_is_directory=True)
    briefs = cost.complete_briefs(cost.load_runs(tmp_path))
    assert [b["run"] for b in briefs] == ["vo-r3"]


def test_a_single_run_path_through_a_symlink_still_loads(tmp_path):
    """Pointing the ruler AT a symlinked run (runs/latest) is an explicit choice and still works."""
    _write_run(tmp_path, "real", _routing_validate_shape()[1])
    (tmp_path / "latest").symlink_to("real", target_is_directory=True)
    assert len(cost.load_runs(tmp_path / "latest")) == 1


def _round2(manifest):
    return {**manifest, "cli": {"version": "2.1.280 (Claude Code)", "min_version": "2.1.280", "live": True}}


def test_round2_manifests_form_their_own_era_with_the_owner_decision_label():
    assert cost.routing_era(_round2(_routing_validate_shape()[1])) == ("r2", "extraction models + round-2 seam")
    assert cost.routing_era(_routing_validate_shape()[1])[0] == "current"
    label = cost.ERA_LABELS["r2"]
    assert "sonnet extraction + sonnet verify-extract (owner decision 2026-09-23 #5)" in label
    assert "risk-routed" not in label


def test_round2_date_fallback_needs_the_seam_record():
    assert cost.routing_era(_round2({"started_ts": "2026-09-23T21:00:00", "steps": []}))[0] == "r2"
    assert cost.routing_era({"started_ts": "2026-09-23T21:00:00", "steps": []})[0] == "current"


def _verified_extract(source_id, issues, forwarded, dropped=0, applied=0, rejected=0):
    adjudication = None
    if forwarded:
        adjudication = {"file": "x", "applied": applied,
                        "rejected": [{"finding": f"F{i + 1}", "where": "budget[0]", "problem": "p"}
                                     for i in range(rejected)]}
    return {"source_id": source_id, "attempts": [_usage_sub(f"e-{source_id}", "claude-sonnet-5", 1, 1, 1, 1)],
            "verification": {"model": "sonnet", "issue_count": issues, "forwarded_count": forwarded,
                             "dropped": [{"index": i} for i in range(dropped)], "adjudication": adjudication,
                             "attempts": [_usage_sub(f"v-{source_id}", "claude-sonnet-5", 1, 1, 1, 1)]}}


def test_verifier_effectiveness_counts_every_outcome():
    m = {"project_dir": "fixtures/northlight_01", "steps": [{"name": "extraction", "kind": "model", "extracts": [
        _verified_extract("a", 0, 0),
        _verified_extract("b", 3, 2, dropped=1, applied=1, rejected=1),
        _verified_extract("c", 1, 1, applied=1),
        {"source_id": "d", "attempts": []},  # no verifier (Haiku-era shape): not a check
    ]}]}
    result = cost.verifier_effectiveness([("nl-r9", m)])
    row = result["runs"][0]
    assert (row["checks"], row["issues"], row["forwarded"], row["dropped"]) == (3, 4, 3, 1)
    assert (row["applied"], row["rejected"], row["unadjudicated"]) == (2, 1, 0)
    assert row["rejections"][0]["source_id"] == "b"
    assert result["total"]["applied"] == 2


def test_verifier_effectiveness_never_guesses_a_missing_adjudication():
    ext = _verified_extract("a", 2, 2)
    ext["verification"]["adjudication"] = None
    m = {"steps": [{"name": "extraction", "kind": "model", "extracts": [ext]}]}
    row = cost.verifier_effectiveness([("r", m)])["runs"][0]
    assert row["unadjudicated"] == 2 and row["applied"] == 0 and row["rejected"] == 0


def test_verifier_view_prints_totals_and_rejections(tmp_path, capsys):
    m = {"steps": [{"name": "extraction", "kind": "model", "extracts": [
        _verified_extract("t", 1, 1, rejected=1)]}]}
    _write_run(tmp_path, "nl-r3", m)
    assert cost.main([str(tmp_path), "--verifier"]) == 0
    out = capsys.readouterr().out
    assert "TOTAL" in out and "Rejected findings" in out and "nl-r3" in out
    assert cost.main([str(tmp_path), "--verifier", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["total"]["rejected"] == 1
