"""Tests for eval/pass_rates.py: per-check pass rates across stored harness reports, grouped by
fixture and routing era, with resumed legs counted once."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import pass_rates  # noqa: E402


def _sub(session, model):
    return {"attempt": 1, "subagent": {"session_id": session, "model_ids": [model], "usage": {}}}


def _manifest(extract_session, synth_session, render_session, model="claude-haiku-4-5-20251001",
              verified=False):
    extract = {"source_id": "s", "attempts": [_sub(extract_session, model)]}
    if verified:
        extract["verification"] = {"attempts": [_sub(extract_session + "-v", "claude-sonnet-5")]}
    return {"started_ts": "2026-07-24T10:00:00", "steps": [
        {"name": "extraction", "kind": "model", "status": "pass", "extracts": [extract]},
        {"name": "synthesis", "kind": "model", "status": "pass",
         "synthesis": {"attempts": [_sub(synth_session, "claude-sonnet-5")]}},
        {"name": "render", "kind": "model", "status": "pass",
         "render": {"attempts": [_sub(render_session, "claude-sonnet-5")]}},
    ]}


def _report(fixture, statuses):
    checks = [{"check_id": cid, "status": st} for cid, st in statuses.items()]
    return {"fixture": fixture, "checks": checks,
            "summary": {"passed": sum(1 for s in statuses.values() if s == "pass"),
                        "failed": sum(1 for s in statuses.values() if s == "fail"), "skipped": 0}}


def _write_run(root, name, report, manifest=None):
    run = root / name
    run.mkdir(parents=True)
    (run / "harness_report.json").write_text(json.dumps(report), encoding="utf-8")
    if manifest is not None:
        (run / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run


def _groups(root):
    records = [pass_rates.load_record(p) for p in pass_rates.find_reports([root])]
    return pass_rates.aggregate(records)


def test_rates_are_grouped_by_fixture_and_era(tmp_path):
    _write_run(tmp_path, "a", _report("northlight_01", {"T1.1": "pass", "X2": "pass"}), _manifest("e1", "s1", "r1"))
    _write_run(tmp_path, "b", _report("northlight_01", {"T1.1": "pass", "X2": "fail"}), _manifest("e2", "s2", "r2"))
    _write_run(tmp_path, "c", _report("northlight_01", {"T1.1": "fail", "X2": "pass"}),
               _manifest("e3", "s3", "r3", model="claude-sonnet-5", verified=True))
    _write_run(tmp_path, "d", _report("voreas_02", {"T1.1": "pass"}), _manifest("e4", "s4", "r4"))
    groups = _groups(tmp_path)
    assert set(groups) == {("northlight_01", "haiku-era"), ("northlight_01", "current"), ("voreas_02", "haiku-era")}
    haiku = groups[("northlight_01", "haiku-era")]
    assert haiku["reports"] == 2
    assert (haiku["checks"]["X2"]["pass"], haiku["checks"]["X2"]["n"]) == (1, 2)
    assert groups[("northlight_01", "current")]["checks"]["T1.1"]["pass"] == 0


def test_a_resumed_leg_graded_twice_counts_once(tmp_path):
    """Two reports on the same extracts (resumed synthesis re-roll): T1.x has one distinct leg,
    synthesis checks have two."""
    _write_run(
        tmp_path, "roll1", _report("northlight_01", {"T1.3": "pass", "T3.1": "fail"}), _manifest("e1", "s1", "r1")
    )
    _write_run(
        tmp_path, "roll2", _report("northlight_01", {"T1.3": "pass", "T3.1": "pass"}), _manifest("e1", "s2", "r2")
    )
    checks = _groups(tmp_path)[("northlight_01", "haiku-era")]["checks"]
    assert (checks["T1.3"]["n"], checks["T1.3"]["legs_n"], checks["T1.3"]["legs_pass"]) == (2, 1, 1)
    assert (checks["T3.1"]["legs_n"], checks["T3.1"]["legs_pass"]) == (2, 1)


def test_render_checks_are_legs_of_synthesis_plus_render(tmp_path):
    _write_run(tmp_path, "r1", _report("f", {"T2.5": "pass", "T2.1": "pass"}), _manifest("e", "s", "r1"))
    _write_run(tmp_path, "r2", _report("f", {"T2.5": "pass", "T2.1": "pass"}), _manifest("e", "s", "r2"))
    checks = _groups(tmp_path)[("f", "haiku-era")]["checks"]
    assert checks["T2.5"]["legs_n"] == 2  # render re-rolled
    assert checks["T2.1"]["legs_n"] == 1  # same brief


def test_a_report_without_a_manifest_is_its_own_unknown_leg(tmp_path):
    _write_run(tmp_path, "orphan", _report("f", {"T1.1": "pass"}))
    group = _groups(tmp_path)[("f", "unknown")]
    assert group["checks"]["T1.1"]["legs_n"] == 1 and group["checks"]["T1.1"]["unknown_legs"] == 1


def test_symlinked_run_dirs_are_not_counted_twice(tmp_path):
    run = _write_run(tmp_path, "real", _report("f", {"T1.1": "pass"}), _manifest("e", "s", "r"))
    (tmp_path / "latest").symlink_to(run, target_is_directory=True)
    assert len(pass_rates.find_reports([tmp_path])) == 1


def test_skipped_checks_do_not_count_as_samples(tmp_path):
    _write_run(tmp_path, "a", _report("f", {"T1.1": "skip"}), _manifest("e", "s", "r"))
    assert _groups(tmp_path)[("f", "haiku-era")]["checks"]["T1.1"]["n"] == 0


def test_wilson_interval_bounds():
    assert pass_rates.wilson(0, 0) == (0.0, 0.0)
    lo, hi = pass_rates.wilson(10, 10)
    assert hi == pytest.approx(1.0) and 0.70 < lo < 0.75
    lo, hi = pass_rates.wilson(1, 2)
    assert lo < 0.5 < hi


def test_markdown_table_names_the_era_and_n(tmp_path, capsys):
    _write_run(tmp_path, "a", _report("northlight_01", {"T1.1": "pass"}), _manifest("e", "s", "r"))
    assert pass_rates.main([str(tmp_path), "--markdown"]) == 0
    out = capsys.readouterr().out
    assert "Haiku-era" in out and "| T1.1 | 1/1 | 1/1 |" in out


def _committed_reports(repo_root):
    """Harness reports git tracks under runs/ — never gitignored local runs in a working checkout,
    so the numbers are the same in a clean clone and in a developer's tree."""
    import subprocess
    try:
        listed = subprocess.run(["git", "-C", str(repo_root), "ls-files", "-z", "--", "runs"],
                                capture_output=True, check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout: committed evidence cannot be told apart from local runs")
    tracked = {(repo_root / rel).resolve() for rel in listed.split("\0") if rel}
    return [p for p in pass_rates.find_reports([repo_root / "runs"]) if p.resolve() in tracked]


def test_committed_evidence_aggregates(repo_root):
    """The committed evidence (runs/tier3, voreas-prep-02/03) is readable by the tool; the
    numbers recorded in docs/EVAL_RECORD.md come from this run of it."""
    groups = pass_rates.aggregate([pass_rates.load_record(p) for p in _committed_reports(repo_root)])
    northlight = groups[("northlight_01", "haiku-era")]
    voreas = groups[("voreas_02", "haiku-era")]
    assert northlight["full_passes"] == 1 and northlight["reports"] == 1
    assert voreas["reports"] == 2 and voreas["checks"]["T3.3"]["pass"] == 0
    assert voreas["checks"]["T1.1"]["legs_n"] == 1  # prep-03 re-used prep-02's extracts
