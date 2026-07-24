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


def test_run_clears_the_gate_then_stops_cleanly_without_a_model(fixture_project, tmp_path):
    """With no model reachable, the deterministic half still runs and the failure is legible.

    Step 1 passes on real fixture input; step 2 fails with an infrastructure error rather than
    a mysterious hang, and the manifest records which stage stopped and why.
    """
    code = runner.main(["--project", str(fixture_project), "--out", str(tmp_path), "--run-id", "testrun"])
    assert code == runner.EXIT_GATE_ERROR

    manifest = _manifest(tmp_path)
    assert manifest["outcome"] == "stage_failed"
    assert [s["status"] for s in manifest["steps"]] == ["pass", "failed"]
    assert manifest["steps"][0]["name"] == "readiness_gate"
    assert manifest["steps"][1]["agent"] == "classify"
    assert "not found on PATH" in manifest["steps"][1]["error"]
    assert len(manifest["sources"]) == 4


def test_run_writes_the_latest_symlink(fixture_project, tmp_path):
    runner.main(["--project", str(fixture_project), "--out", str(tmp_path), "--run-id", "testrun"])
    latest = tmp_path / "latest"
    assert latest.is_symlink() and latest.resolve().name == "testrun"


def test_resuming_a_leg_preserves_the_earlier_run_record(fixture_project, tmp_path):
    """A resume must not rewrite the manifest with only the leg it re-ran.

    Regression: re-rendering an existing run left a manifest reading `outcome: complete` with a
    single step in it — a run record that lies by omission about what produced the artifacts.
    """
    run_dir = tmp_path / "testrun"
    run_dir.mkdir(parents=True)
    (run_dir / "brief.json").write_text(json.dumps({"meta": {}, "open_questions": []}), encoding="utf-8")
    (run_dir / "run_manifest.json").write_text(
        json.dumps({
            "run_id": "testrun",
            "steps": [
                {"name": "readiness_gate", "number": 1, "status": "pass"},
                {"name": "extraction", "number": 4, "status": "pass"},
                {"name": "render", "number": 7, "status": "failed"},
            ],
        }),
        encoding="utf-8",
    )

    runner.main(["--project", str(fixture_project), "--out", str(tmp_path),
                 "--run-id", "testrun", "--stage", "render"])

    steps = {s["name"]: s for s in _manifest(tmp_path)["steps"]}
    assert steps["readiness_gate"]["from_earlier_run"] is True
    assert steps["extraction"]["from_earlier_run"] is True
    # The re-run leg is replaced by this run's attempt, not duplicated from the old record.
    assert steps["render"].get("from_earlier_run") is None


def test_resuming_without_prerequisites_refuses_legibly(fixture_project, tmp_path):
    """`--stage render` on an empty run dir used to raise a bare KeyError from inside a handler."""
    code = runner.main(["--project", str(fixture_project), "--out", str(tmp_path),
                        "--run-id", "testrun", "--stage", "render"])
    assert code == runner.EXIT_GATE_ERROR

    manifest = _manifest(tmp_path)
    assert manifest["outcome"] == "missing_prerequisite"
    assert "brief.json" in manifest["steps"][0]["error"]


def test_every_stage_has_a_handler_at_tier_2():
    """Full Stage 1 — all four model stages built. If this fails, a tier boundary moved."""
    assert sorted(runner.AGENT_HANDLERS) == ["classify", "extract", "fidelity-check", "render", "synthesize"]
    model_steps = {s.agent for s in runner.STEP_SEQUENCE if s.kind == runner.MODEL}
    assert model_steps == set(runner.AGENT_HANDLERS)


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


def test_extraction_stage_selects_only_the_gate_and_step_4():
    """`--stage extraction` is the Tier-1 path: prove one leg without faking the rest."""
    assert runner.STAGE_SELECTIONS["extraction"] == ("readiness_gate", "extraction")
