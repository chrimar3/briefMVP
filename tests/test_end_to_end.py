"""The whole Stage-1 orchestration, end to end, with the offline replay fake as the model.

Every gate is unit-tested elsewhere; nothing else drives Runner through all seven steps, the
artifact handoff between them, the verify-extract leg, readiness injection, the manifest, the
review pages and a resume leg together. The fake (`tools/replay/claude`) replays the
pre-sign-off recording derived from runs/tier3, so no model is called and nothing is spent.
"""

import json
import shutil

import pytest

from pipeline import PIPELINE_VERSION, gates, publish, replay, revisions, runner

FULL_STEPS = list(runner.STAGE_SELECTIONS["full"])


@pytest.fixture
def project(tmp_path, fixture_project):
    """A private copy of fixtures/northlight_01 (same folder name, so the same project_id)."""
    target = tmp_path / "projects" / fixture_project.name
    shutil.copytree(fixture_project, target, ignore=shutil.ignore_patterns("answer_key.json"))
    # Cross-workstream contract (round 1): every project folder declares its data class.
    (target / "data_declaration.json").write_text('{"data_class": "synthetic"}\n', encoding="utf-8")
    return target


@pytest.fixture
def replayed(fake_claude, monkeypatch, tmp_path):
    """Replay as the model, and a private reviews/ shelf so the repo shelf is never written."""
    shelf = tmp_path / "shelf"
    monkeypatch.setattr(publish, "DEFAULT_REVIEWS_DIR", shelf)
    return shelf


def _run(project, out, *extra, run_id="e2e"):
    return runner.main(["--project", str(project), "--out", str(out), "--run-id", run_id, *extra])


def _manifest(run_dir):
    return json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))


def _attempts(step):
    """Every subagent attempt a manifest step records, verification legs included."""
    found = []
    for key in ("classification", "synthesis", "render"):
        if isinstance(step.get(key), dict):
            found += step[key]["attempts"]
    for key in ("fidelity", "extracts"):
        for item in step.get(key) or []:
            found += item["attempts"] + ((item.get("verification") or {}).get("attempts") or [])
    return found


def test_full_run_completes_through_every_stage_with_zero_model_calls(project, replayed, tmp_path):
    out = tmp_path / "runs"
    assert _run(project, out) == runner.EXIT_OK

    run_dir = out / "e2e"
    manifest = _manifest(run_dir)
    assert manifest["outcome"] == "complete" and manifest["exit_code"] == 0
    assert manifest["pipeline_version"] == PIPELINE_VERSION
    assert [s["name"] for s in manifest["steps"]] == FULL_STEPS
    assert all(s["status"] == "pass" for s in manifest["steps"])

    # No model produced anything: every attempt reports the replay stand-in and zero cost.
    attempts = [a for s in manifest["steps"] for a in _attempts(s)]
    assert len(attempts) == 1 + 1 + 4 + 4 + 1 + 1  # classify, fidelity, 4 extract, 4 verify, synth, render
    assert all(a["subagent"]["model_ids"] == [replay.REPLAY_MODEL_ID] for a in attempts)
    assert all(a["subagent"]["cost_usd"] == 0 and a["violations"] == [] for a in attempts)

    # Artifact handoff: every stage's output is on disk where the next one looked for it.
    for source in ("background_brand_guidelines", "emails_thread", "rfp_meltemi", "transcript_kickoff"):
        assert (run_dir / "extracts" / f"{source}.json").is_file()
        assert (run_dir / "verification" / f"{source}.verify.json").is_file()
    assert (run_dir / "fidelity" / "transcript_kickoff.annotated.md").is_file()
    assert (run_dir / "input_snapshot.json").is_file()

    # The runner, not the model, owns readiness; the brief is a schema-valid unsigned draft.
    brief = json.loads((run_dir / "brief.json").read_text(encoding="utf-8"))
    gates.validate_brief(brief)
    assert brief["signoff"] == {"status": "draft"}
    assert all(c["status"] == "open" for c in brief["conflicts"])
    without = {k: v for k, v in brief.items() if k != "readiness"}
    assert brief["readiness"] == gates.compute_readiness_block(without)

    # Deterministic tail: review pages written, and the shelf copy went to the private shelf.
    for page in ("brief_review.html", "run_review.html", "brief_el.html", "brief_en.html"):
        assert (run_dir / page).is_file(), page
    assert sorted(p.suffix for p in replayed.iterdir()) == [".html"] * 4 + [".md"] * 2
    assert (out / "latest").resolve() == run_dir.resolve()


def test_resume_leg_reruns_render_only_and_keeps_the_earlier_record(project, replayed, tmp_path):
    out = tmp_path / "runs"
    assert _run(project, out) == runner.EXIT_OK
    run_dir = out / "e2e"
    first_render = (run_dir / "brief_en.md").read_bytes()

    assert _run(project, out, "--stage", "render") == runner.EXIT_OK

    manifest = _manifest(run_dir)
    assert manifest["outcome"] == "complete" and manifest["stage"] == "render"
    assert [s["name"] for s in manifest["steps"]] == FULL_STEPS
    earlier = [s["name"] for s in manifest["steps"] if s.get("from_earlier_run")]
    assert earlier == FULL_STEPS[:-1]  # only render ran in this leg
    assert (run_dir / "brief_en.md").read_bytes() == first_render
    archived = [p.name for p in (run_dir / "history").rglob("brief_en.md")]
    assert archived, "the invalidated render must be archived before the leg re-runs"


def test_a_gate_failure_gets_one_repair_round_then_the_run_stops(project, replayed, tmp_path, monkeypatch):
    """A recording whose brief carries a model-written readiness block fails the synthesis gate
    on both attempts: exactly MAX_ATTEMPTS invocations, logged, then stage_failed / exit 4."""
    recording = tmp_path / "bad-recording"
    shutil.copytree(replay.DEFAULT_RECORDED_RUN, recording)
    brief = json.loads((recording / "brief.json").read_text(encoding="utf-8"))
    brief["readiness"] = {"verdict": "ready_for_review"}
    (recording / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv(replay.RECORDED_RUN_ENV, str(recording))

    out = tmp_path / "runs"
    assert _run(project, out) == runner.EXIT_GATE_ERROR

    run_dir = out / "e2e"
    manifest = _manifest(run_dir)
    assert manifest["outcome"] == "stage_failed"
    assert [s["status"] for s in manifest["steps"]] == ["pass"] * 5 + ["failed"]
    assert "readiness" in manifest["steps"][-1]["error"]
    log = [json.loads(line) for line in
           (run_dir / "diagnostics" / "repair_log.jsonl").read_text(encoding="utf-8").splitlines()]
    synth = [r for r in log if r["stage"] == "synthesize"]
    assert [r["attempt"] for r in synth] == [1, 2]
    assert all(r["violation_count"] >= 1 for r in synth)


def test_replaying_a_different_project_is_refused_not_faked(project, replayed, tmp_path):
    renamed = project.parent / "some_other_project"
    project.rename(renamed)
    out = tmp_path / "runs"
    assert _run(renamed, out) == runner.EXIT_GATE_ERROR
    manifest = _manifest(out / "e2e")
    assert manifest["outcome"] == "stage_failed"
    assert manifest["steps"][-1]["name"] == "classification"


# -- runner error reporting (round-1 fix: not every ValueError is a lock problem) ----------------

def test_corrupt_artifact_on_resume_is_named_and_manifested(project, tmp_path, capsys):
    """Was: '[run lock] Expecting property name…', exit 4, no manifest, no file named."""
    out = tmp_path / "runs"
    run_dir = out / "corrupt"
    run_dir.mkdir(parents=True)
    (run_dir / "brief.json").write_text("{broken", encoding="utf-8")

    code = _run(project, out, "--stage", "render", run_id="corrupt")

    assert code == runner.EXIT_GATE_ERROR
    err = capsys.readouterr().err
    assert "[run lock]" not in err
    assert "[corrupt artifact]" in err and "brief.json" in err
    manifest = _manifest(run_dir)
    assert manifest["outcome"] == "corrupt_artifact" and manifest["exit_code"] == runner.EXIT_GATE_ERROR
    assert "brief.json" in manifest["error"]
    assert (run_dir / "brief.json").read_text(encoding="utf-8") == "{broken"  # kept for inspection


def test_corrupt_earlier_manifest_is_preserved_in_history(project, tmp_path):
    out = tmp_path / "runs"
    run_dir = out / "corrupt"
    run_dir.mkdir(parents=True)
    (run_dir / "run_manifest.json").write_text("not json", encoding="utf-8")

    assert _run(project, out, "--stage", "render", run_id="corrupt") == runner.EXIT_GATE_ERROR

    assert _manifest(run_dir)["outcome"] == "corrupt_artifact"
    kept = [p.read_text(encoding="utf-8") for p in (run_dir / "history").rglob("run_manifest.json")]
    assert kept == ["not json"]


def test_corrupt_input_snapshot_is_named_not_called_a_lock(project, tmp_path, capsys):
    out = tmp_path / "runs"
    run_dir = out / "corrupt"
    run_dir.mkdir(parents=True)
    (run_dir / "input_snapshot.json").write_text("{", encoding="utf-8")

    assert _run(project, out, "--stage", "render", run_id="corrupt") == runner.EXIT_GATE_ERROR

    err = capsys.readouterr().err
    assert "[run lock]" not in err and "input_snapshot.json" in err
    assert _manifest(run_dir)["outcome"] == "corrupt_artifact"


def test_real_lock_contention_is_still_reported_as_a_run_lock(project, tmp_path, capsys):
    out = tmp_path / "runs"
    with revisions.run_lock(out / "busy"):
        code = _run(project, out, run_id="busy")
    assert code == runner.EXIT_GATE_ERROR
    assert "[run lock]" in capsys.readouterr().err
    assert not (out / "busy" / "run_manifest.json").exists()  # the holder owns the directory


def test_run_busy_error_is_a_value_error_for_existing_callers(tmp_path):
    with revisions.run_lock(tmp_path):
        with pytest.raises(revisions.RunBusyError):
            with revisions.run_lock(tmp_path):
                pass
    assert issubclass(revisions.RunBusyError, ValueError)
