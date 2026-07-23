"""The step sequencer. At Tier 0 the contract under test is: does it refuse correctly,
and does it stop honestly at the first stage that does not exist yet?
"""

import json
import shutil

from pipeline import runner


def _manifest(out_dir, run_id="testrun"):
    return json.loads((out_dir / run_id / "run_manifest.json").read_text(encoding="utf-8"))


def test_step_sequence_matches_prd_section_5():
    """Sequence is spec, not implementation detail. Human sign-off is deliberately absent:
    it is the gate the runner stops at, not a step the runner executes (PRD DR-8)."""
    assert [s.name for s in runner.STEP_SEQUENCE] == [
        "readiness_gate",
        "classification",
        "fidelity_check",
        "extraction",
        "conflict_pass",
        "synthesis",
        "render",
    ]
    assert [s.number for s in runner.STEP_SEQUENCE] == list(range(1, 8))


def test_run_stops_at_the_first_unbuilt_stage(fixture_project, tmp_path):
    code = runner.main(["--project", str(fixture_project), "--out", str(tmp_path), "--run-id", "testrun"])
    assert code == runner.EXIT_PENDING_STAGE

    manifest = _manifest(tmp_path)
    assert manifest["outcome"] == "pending_stage"
    assert [s["status"] for s in manifest["steps"]] == ["pass", "pending"]
    assert manifest["steps"][0]["name"] == "readiness_gate"
    assert manifest["steps"][1]["agent"] == "classify"
    assert len(manifest["sources"]) == 4


def test_run_writes_the_latest_symlink(fixture_project, tmp_path):
    runner.main(["--project", str(fixture_project), "--out", str(tmp_path), "--run-id", "testrun"])
    latest = tmp_path / "latest"
    assert latest.is_symlink() and latest.resolve().name == "testrun"


def test_run_refuses_when_the_rfp_is_removed(fixture_project, tmp_path):
    """The readiness gate is the system's ability to say no. Without it, thin input
    silently becomes a confident-looking brief."""
    project = tmp_path / "project"
    project.mkdir()
    for src in fixture_project.glob("*.md"):
        if "rfp" not in src.name:
            shutil.copy(src, project / src.name)

    out = tmp_path / "runs"
    code = runner.main(["--project", str(project), "--out", str(out), "--run-id", "testrun"])
    assert code == runner.EXIT_INSUFFICIENT_INPUT

    manifest = _manifest(out)
    assert manifest["outcome"] == "insufficient_input"
    step = manifest["steps"][0]
    assert step["status"] == "refused"
    assert "insufficient input" in step["verdict"]["message"]
    assert step["verdict"]["missing_required"] == ["rfp"]


def test_run_reports_an_undeclared_input_folder(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "notes.md").write_text("# scratch notes, no header\n", encoding="utf-8")

    code = runner.main(["--project", str(project), "--out", str(tmp_path / "runs"), "--run-id", "testrun"])
    assert code == runner.EXIT_GATE_ERROR
    assert _manifest(tmp_path / "runs")["outcome"] == "input_contract_error"


def test_no_model_handlers_are_registered_at_tier_0():
    """Tier 0 ships the sequence, not the stages. If this fails, a tier boundary moved."""
    assert runner.AGENT_HANDLERS == {}
