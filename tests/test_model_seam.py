"""Model-seam hardening before live runs (round 2, W-S; docs/SECURITY.md §3.2, §3.4, §3.8).

Offline only: the CLI is the replay fake or a hand-written stand-in, and stage handlers are
replaced where a test needs an agent to misbehave. What is proved here:

* per-stage write scope — every earlier stage's outputs are denied by rule and hashed around
  each model step (a render or creative step that rewrites brief.json fails; one source's
  extraction leg cannot touch another source's extract);
* stale outputs of an earlier leg are archived before a stage runs, so a resumed leg is never
  graded on an old artifact;
* `--no-session-persistence` and `--restricted` on every invocation; the CLI version is probed,
  recorded and refused below 2.1.280;
* live model calls are opt-in (`--live` / BRIEF_BUILDER_LIVE=1); the replay needs none;
* `--out` is hermetic: no reviews/ publication and no repository change unless asked for;
* the manifest records project_dir relative to the repo, the CLI, and the advisory prescreen
  of the declared sources only;
* the demo goes through the same declaration, staging and integrity checks as the runner.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pipeline import agents, extraction, gates, prescreen, publish, runner, stages

REPO = gates.REPO_ROOT
INJECTION = Path(__file__).resolve().parent / "injection_project"
sys.path.insert(0, str(REPO / "demo"))
import run_demo  # noqa: E402


# -- helpers -------------------------------------------------------------------------------


@pytest.fixture
def project(tmp_path):
    target = tmp_path / "project"
    shutil.copytree(INJECTION, target)
    return target


def _halt(ctx, step):
    raise stages.HaltForHuman("stop after the setup")


def _main(project, out, *extra, run_id="r", handlers=None, monkeypatch=None):
    for name, handler in (handlers or {}).items():
        monkeypatch.setitem(runner.AGENT_HANDLERS, name, handler)
    return runner.main(["--project", str(project), "--out", str(out), "--run-id", run_id,
                        "--glossary", str(project / "client.json"), *extra])


def _manifest(out, run_id="r"):
    return json.loads((out / run_id / "run_manifest.json").read_text(encoding="utf-8"))


def _fake_real_cli(tmp_path, version="2.1.280 (Claude Code)", counter=None):
    """A stand-in for a REAL claude binary (not the replay): answers --version, never a model."""
    fake = tmp_path / "bin" / "claude"
    fake.parent.mkdir(parents=True, exist_ok=True)
    count = f"open({str(counter)!r}, 'a').write('v\\n')\n    " if counter else ""
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "if sys.argv[1:] == ['--version']:\n"
        f"    {count}print({version!r}); sys.exit(0)\n"
        "print(json.dumps({'result': 'ok', 'session_id': 's', 'modelUsage': {'claude-test': {}}}))\n",
        encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    return fake


def _deny(scope):
    return set(agents.permission_rules(agents.AccessScope.coerce(scope))[1])


def _rule(path, recursive=False):
    return "/" + str(Path(path).resolve()) + ("/**" if recursive else "")


def _ctx(tmp_path, step, sources=()):
    return runner.RunContext(project_dir=INJECTION, run_dir=tmp_path / "run", run_id="r",
                             sources=list(sources), started_ts="", current_step=step)


def _doc(sid):
    return gates.SourceDoc(sid, "rfp", "2026-01-01", Path(f"{sid}.md"), "")


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if root.exists():
        for path in sorted(root.rglob("*")):
            digest.update(str(path.relative_to(root)).encode())
            if path.is_file():
                digest.update(path.read_bytes())
    return digest.hexdigest()


def _git_status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO,
                          capture_output=True, text=True, check=True).stdout


# -- per-stage write scope -------------------------------------------------------------------


def test_every_step_protects_the_outputs_of_every_earlier_step():
    assert runner.earlier_step_outputs("classification") == ()
    render = set(runner.earlier_step_outputs("render"))
    assert {"classification.json", "fidelity", "extracts", "verification", "conflict_candidates.json",
            "brief.json", "coverage_ledger.json"} <= render
    assert "brief_el.md" not in render
    creative = set(runner.earlier_step_outputs("creative_shadow"))
    assert {"brief.json", "brief_el.md", "brief_en.md", "extracts"} <= creative and "creative" not in creative
    synthesis = set(runner.earlier_step_outputs("synthesis"))
    assert {"extracts", "verification", "fidelity", "classification.json", "conflict_candidates.json"} <= synthesis
    assert "brief.json" not in synthesis


@pytest.mark.parametrize("step, denied, allowed", [
    ("synthesis", ["extracts", "verification", "fidelity"], ["brief.json"]),
    ("render", ["brief.json", "extracts", "classification.json", "conflict_candidates.json"], ["brief_el.md"]),
    ("creative_shadow", ["brief.json", "brief_en.md", "brief_el.md", "extracts"], ["creative"]),
])
def test_deny_rules_follow_the_step(tmp_path, step, denied, allowed):
    ctx = _ctx(tmp_path, step)
    deny = _deny(runner._access_dirs(ctx))
    run_dir = ctx.run_dir
    for name in denied:
        recursive = not Path(name).suffix
        assert f"Write({_rule(run_dir / name, recursive)})" in deny, (step, name)
        assert f"Edit({_rule(run_dir / name, recursive)})" in deny, (step, name)
    for name in allowed:
        recursive = not Path(name).suffix
        assert f"Write({_rule(run_dir / name, recursive)})" not in deny, (step, name)
    # The fixed human records stay protected in every step.
    assert f"Write({_rule(run_dir / 'approval.json')})" in deny


def test_one_sources_extraction_leg_cannot_write_another_sources_files(tmp_path):
    ctx = _ctx(tmp_path, "extraction", [_doc("rfp_a"), _doc("mail_b")])
    deny = _deny(runner._access_dirs(ctx, source_id="rfp_a"))
    run_dir = ctx.run_dir
    assert f"Write({_rule(run_dir / 'extracts' / 'mail_b.json')})" in deny
    assert f"Write({_rule(run_dir / 'verification' / 'mail_b.verify.json')})" in deny
    assert f"Write({_rule(run_dir / 'extracts' / 'rfp_a.json')})" not in deny
    assert f"Write({_rule(run_dir / 'verification' / 'rfp_a.verify.json')})" not in deny


def test_integrity_state_watches_earlier_outputs(tmp_path):
    ctx = _ctx(tmp_path, "synthesis")
    (ctx.run_dir / "extracts").mkdir(parents=True)
    (ctx.run_dir / "extracts" / "x.json").write_text("{}", encoding="utf-8")
    before = runner.integrity_state(ctx)
    (ctx.run_dir / "brief.json").write_text("{}", encoding="utf-8")        # its own output: fine
    assert runner.integrity_violations(before, runner.integrity_state(ctx)) == []
    (ctx.run_dir / "extracts" / "x.json").write_text('{"dropped": true}', encoding="utf-8")
    problems = runner.integrity_violations(before, runner.integrity_state(ctx))
    assert problems and "extracts/x.json was modified" in problems[0]


def _seed_brief_run(project, out, monkeypatch):
    """A run directory with the artifacts a render/creative leg resumes from."""
    assert _main(project, out, handlers={"classify": _halt}, monkeypatch=monkeypatch) == runner.EXIT_HALTED_FOR_HUMAN
    run_dir = out / "r"
    (run_dir / "brief.json").write_text('{"conflicts": [{"status": "open"}]}', encoding="utf-8")
    (run_dir / "extracts").mkdir()
    (run_dir / "extracts" / "inj_rfp.json").write_text('{"mandatories": ["keep"]}', encoding="utf-8")
    (run_dir / "brief_en.md").write_text("# rendered\n", encoding="utf-8")
    return run_dir


@pytest.mark.parametrize("stage, agent, target", [
    ("render", "render", "brief.json"),
    ("render", "render", "extracts/inj_rfp.json"),
    ("creative", "creative-shadow", "brief.json"),
    ("creative", "creative-shadow", "brief_en.md"),
])
def test_a_render_or_creative_step_that_rewrites_an_earlier_artifact_fails(project, tmp_path, monkeypatch,
                                                                          stage, agent, target):
    out = tmp_path / "runs"
    run_dir = _seed_brief_run(project, out, monkeypatch)
    if stage == "creative":   # render outputs exist only after render; the creative leg keeps them
        (run_dir / "brief_en.md").write_text("# rendered\n", encoding="utf-8")

    def obedient(ctx, step):
        path = Path(ctx.run_dir) / target
        path.write_text('{"conflicts": [{"status": "resolved_by_human"}]}', encoding="utf-8")
        return {"render": {}}

    code = _main(project, out, "--stage", stage, handlers={agent: obedient}, monkeypatch=monkeypatch)
    assert code == runner.EXIT_GATE_ERROR
    manifest = _manifest(out)
    assert manifest["outcome"] == "stage_failed"
    error = manifest["steps"][-1]["error"]
    assert error.startswith("integrity:") and f"{target} was modified" in error


def test_an_extraction_leg_that_touches_another_sources_extract_fails(project, tmp_path, monkeypatch):
    sources = gates.discover_sources(project)
    first, second = sources[0].source_id, sources[1].source_id

    def tampering_extract(source, run_dir, **kwargs):
        own = Path(run_dir) / "extracts" / f"{source.source_id}.json"
        own.parent.mkdir(parents=True, exist_ok=True)
        own.write_text("{}", encoding="utf-8")
        (Path(run_dir) / "extracts" / f"{second}.json").write_text('{"planted": true}', encoding="utf-8")
        return {"output_file": str(own)}

    monkeypatch.setattr(extraction, "extract_source", tampering_extract)
    out = tmp_path / "runs"
    assert _main(project, out, "--stage", "extraction") == runner.EXIT_GATE_ERROR
    error = _manifest(out)["steps"][-1]["error"]
    assert error.startswith(f"integrity: {first}'s leg changed another source's files")
    assert f"extracts/{second}.json was created" in error


# -- stale outputs ---------------------------------------------------------------------------


def test_model_output_paths_name_only_the_selected_sources():
    docs = [_doc("a"), gates.SourceDoc("t", "transcript", "2026-01-01", Path("t.md"), "")]
    assert runner.model_output_paths("extraction", docs[:1]) == (
        "extracts/a.json", "verification/a.verify.json", "verification/a.findings.json",
        "verification/a.adjudication.json")
    assert runner.model_output_paths("fidelity_check", docs) == ("fidelity/t.report.json", "fidelity/t.annotated.md")
    assert runner.model_output_paths("render") == ("brief_el.md", "brief_en.md")
    assert runner.model_output_paths("creative_shadow") == ("creative/creative_brief_sonnet.md",
                                                            "creative/creative_brief_opus.md")


def test_clear_stale_outputs_archives_never_deletes(tmp_path):
    (tmp_path / "extracts").mkdir()
    (tmp_path / "extracts" / "a.json").write_text("old", encoding="utf-8")
    (tmp_path / "extracts" / "b.json").write_text("other", encoding="utf-8")
    moved = runner.clear_stale_outputs(tmp_path, ["extracts/a.json", "verification/a.verify.json"])
    assert moved == ["extracts/a.json"]
    assert not (tmp_path / "extracts" / "a.json").exists() and (tmp_path / "extracts" / "b.json").exists()
    kept = list((tmp_path / "history").rglob("extracts/a.json"))
    assert len(kept) == 1 and kept[0].read_text(encoding="utf-8") == "old"
    assert runner.clear_stale_outputs(tmp_path, ["extracts/a.json"]) == []


def _replay_project(tmp_path, fixture_project):
    target = tmp_path / "projects" / fixture_project.name
    shutil.copytree(fixture_project, target, ignore=shutil.ignore_patterns("answer_key.json"))
    return target


def test_a_resumed_leg_is_never_graded_on_the_earlier_legs_artifact(tmp_path, fixture_project, fake_claude,
                                                                     monkeypatch):
    """Before: `--stage extraction --source X` kept X's extract and verification report in
    place (prepare_run only copies them), so an agent that wrote nothing passed the gate on
    the previous leg's files. Now they are archived first and the gate sees the absence."""
    project = _replay_project(tmp_path, fixture_project)
    out = tmp_path / "runs"
    assert runner.main(["--project", str(project), "--out", str(out), "--run-id", "e2e"]) == runner.EXIT_OK
    run_dir = out / "e2e"
    other_before = (run_dir / "extracts" / "rfp_meltemi.json").read_bytes()

    silent = lambda *a, **k: agents.SubagentResult(agent=a[0], ok=True)  # an agent that writes nothing
    monkeypatch.setattr(agents, "invoke", silent)
    code = runner.main(["--project", str(project), "--out", str(out), "--run-id", "e2e",
                        "--stage", "extraction", "--source", "transcript_kickoff"])
    assert code == runner.EXIT_GATE_ERROR
    step = _manifest(out, "e2e")["steps"][-1]
    assert step["name"] == "extraction" and step["status"] == "failed"
    assert "no file written" in step["error"]
    assert "extracts/transcript_kickoff.json" in step["stale_outputs_archived"]
    assert "verification/transcript_kickoff.verify.json" in step["stale_outputs_archived"]
    assert (run_dir / "extracts" / "rfp_meltemi.json").read_bytes() == other_before   # untouched
    assert list((run_dir / "history").rglob("*-stale-*/extracts/transcript_kickoff.json"))


# -- CLI flags and version -------------------------------------------------------------------


def test_every_invocation_disables_session_persistence_and_runs_restricted(tmp_path):
    for agent in ("classify", "extract", "verify-extract", "synthesize", "render", "creative-shadow"):
        cmd = agents.build_command(agent, "ORDER", runner._access_dirs(_ctx(tmp_path, None)))
        assert "--no-session-persistence" in cmd and "--restricted" in cmd, agent
        assert "--dangerously-skip-permissions" not in cmd and "bypassPermissions" not in cmd


def test_the_flags_reach_the_cli_through_the_subprocess_seam(fake_claude, tmp_path, monkeypatch):
    argv_log = tmp_path / "argv.json"
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_ARGV", str(argv_log))
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "exit:0")
    agents.invoke("classify", "ORDER", [tmp_path], timeout_s=60)
    argv = json.loads(argv_log.read_text(encoding="utf-8"))["argv"]
    assert "--no-session-persistence" in argv and "--restricted" in argv


@pytest.mark.parametrize("line, parsed", [
    ("2.1.280 (Claude Code)", (2, 1, 280)), ("claude 3.0.1", (3, 0, 1)), ("unknown", None), ("", None)])
def test_cli_version_parsing(line, parsed):
    assert agents.parse_cli_version(line) == parsed


@pytest.mark.parametrize("version, ok", [
    ("2.1.279 (Claude Code)", False), ("2.0.999 (Claude Code)", False), ("2.1.280 (Claude Code)", True),
    ("2.2.0 (Claude Code)", True), ("not a version", False)])
def test_a_cli_below_the_minimum_version_is_refused(fake_claude, monkeypatch, version, ok):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_VERSION", version)
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "exit:0")
    if ok:
        assert agents.invoke("classify", "ORDER", [], timeout_s=60).ok
    else:
        with pytest.raises(agents.SubagentError, match="older than 2.1.280|cannot read a version"):
            agents.invoke("classify", "ORDER", [], timeout_s=60)


def test_the_version_is_probed_once_per_binary(tmp_path, monkeypatch):
    counter = tmp_path / "probes.txt"
    fake = _fake_real_cli(tmp_path, counter=counter)
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(fake))
    agents.invoke("classify", "ORDER", [], timeout_s=60)
    agents.invoke("classify", "ORDER", [], timeout_s=60)
    assert counter.read_text(encoding="utf-8") == "v\n"


# -- live calls are opt-in -------------------------------------------------------------------


def test_a_real_cli_without_opt_in_is_refused_before_anything_is_created(project, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(_fake_real_cli(tmp_path)))
    out = tmp_path / "runs"
    assert _main(project, out, handlers={"classify": _halt}, monkeypatch=monkeypatch) == runner.EXIT_LIVE_NOT_ENABLED == 7
    assert not out.exists()
    err = capsys.readouterr().err
    assert "[live calls]" in err and "--live" in err and "tools/replay/claude" in err


@pytest.mark.parametrize("opt_in", ["flag", "env"])
def test_the_live_opt_in_lets_a_real_cli_run_and_is_recorded(project, tmp_path, monkeypatch, opt_in):
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(_fake_real_cli(tmp_path)))
    extra = ["--live"] if opt_in == "flag" else []
    if opt_in == "env":
        monkeypatch.setenv(agents.LIVE_ENV, "1")
    out = tmp_path / "runs"
    assert _main(project, out, *extra, handlers={"classify": _halt}, monkeypatch=monkeypatch) == runner.EXIT_HALTED_FOR_HUMAN
    manifest = _manifest(out)
    assert manifest["live"] is True
    assert manifest["cli"]["version"] == "2.1.280 (Claude Code)" and manifest["cli"]["replay"] is False


def test_the_replay_binary_needs_no_opt_in(project, tmp_path, monkeypatch, fake_claude):
    out = tmp_path / "runs"
    assert _main(project, out, handlers={"classify": _halt}, monkeypatch=monkeypatch) == runner.EXIT_HALTED_FOR_HUMAN
    cli = _manifest(out)["cli"]
    assert _manifest(out)["live"] is False and cli["replay"] is True
    assert cli["version"].startswith("2.1.280") and "offline replay" in cli["version"]


def test_a_missing_project_folder_fails_before_any_run_directory(tmp_path, capsys):
    out = tmp_path / "runs"
    code = runner.main(["--project", str(tmp_path / "no-such-project"), "--out", str(out)])
    assert code == runner.EXIT_INSUFFICIENT_INPUT and not out.exists()
    assert "project folder not found" in capsys.readouterr().err


# -- hermetic output and the manifest --------------------------------------------------------


def test_a_replay_run_with_out_elsewhere_leaves_the_repository_unchanged(tmp_path, fixture_project, fake_claude):
    """No monkeypatched shelf here: the real reviews/ and the real git status are compared."""
    project = _replay_project(tmp_path, fixture_project)
    status, shelf = _git_status(), _tree_hash(REPO / "reviews")
    latest = os.readlink(REPO / "runs" / "latest") if (REPO / "runs" / "latest").is_symlink() else None
    out = tmp_path / "runs"
    assert runner.main(["--project", str(project), "--out", str(out), "--run-id", "h"]) == runner.EXIT_OK
    assert _git_status() == status
    assert _tree_hash(REPO / "reviews") == shelf
    assert (os.readlink(REPO / "runs" / "latest") if (REPO / "runs" / "latest").is_symlink() else None) == latest
    assert (out / "h" / "brief_review.html").is_file()


def test_publishing_happens_for_the_default_out_or_on_request(tmp_path, fixture_project, fake_claude, monkeypatch):
    project = _replay_project(tmp_path, fixture_project)
    shelf = tmp_path / "shelf"
    monkeypatch.setattr(publish, "DEFAULT_REVIEWS_DIR", shelf)
    monkeypatch.setattr(runner, "DEFAULT_OUT_DIR", tmp_path / "default-runs")
    assert runner.main(["--project", str(project), "--run-id", "d"]) == runner.EXIT_OK
    assert (tmp_path / "default-runs" / "d" / "run_manifest.json").is_file()
    assert len(list(shelf.iterdir())) == 6
    other = tmp_path / "other-shelf"
    assert runner.main(["--project", str(project), "--out", str(tmp_path / "elsewhere"), "--run-id", "e",
                        "--publish", "--reviews-dir", str(other)]) == runner.EXIT_OK
    assert len(list(other.iterdir())) == 6
    untouched = tmp_path / "untouched-shelf"
    monkeypatch.setattr(publish, "DEFAULT_REVIEWS_DIR", untouched)
    assert runner.main(["--project", str(project), "--run-id", "n", "--no-publish"]) == runner.EXIT_OK
    assert runner.main(["--project", str(project), "--out", str(tmp_path / "elsewhere"), "--run-id", "x"]) == runner.EXIT_OK
    assert not untouched.exists()


def test_manifest_records_project_dir_relative_to_the_repo(fixture_project, tmp_path, monkeypatch):
    monkeypatch.setitem(runner.AGENT_HANDLERS, "classify", _halt)
    out = tmp_path / "runs"
    runner.main(["--project", str(fixture_project), "--out", str(out), "--run-id", "rel"])
    assert _manifest(out, "rel")["project_dir"] == "fixtures/northlight_01"
    assert runner.repo_relative(tmp_path) == str(tmp_path.resolve())


def test_manifest_records_the_prescreen_of_the_declared_sources_only(project, tmp_path, monkeypatch):
    (project / "notes.txt").write_text("contact synthetic.person@example.invalid\n", encoding="utf-8")
    out = tmp_path / "runs"
    _main(project, out, handlers={"classify": _halt}, monkeypatch=monkeypatch)
    screen = _manifest(out)["prescreen"]
    declared = sorted(p.name for p in project.glob("*.md"))
    assert screen["advisory"] is True and screen["blocking"] is False and screen["mode"] == "given_files"
    assert sorted(s["file"] for s in screen["sources"]) == declared
    assert "synthetic.person@example.invalid" not in json.dumps(screen)


def test_prescreen_of_a_declared_folder_skips_non_source_files(tmp_path):
    folder = tmp_path / "p"
    folder.mkdir()
    (folder / "rfp.md").write_text("# RFP\nsource_id: rfp · source_type: rfp · source_date: 2026-01-01\n\nbody\n",
                                   encoding="utf-8")
    (folder / "README.md").write_text("mail synthetic.person@example.invalid\n", encoding="utf-8")
    (folder / "notes.txt").write_text("mail synthetic.person@example.invalid\n", encoding="utf-8")
    report = prescreen.scan(folder)
    assert report["mode"] == "declared_sources" and [s["file"] for s in report["sources"]] == ["rfp.md"]
    assert report["totals"] == {}


@pytest.mark.parametrize("bad", ["my notes.md", "a,b.md", "..x.md"])
def test_staged_file_names_are_validated_like_source_ids(tmp_path, bad):
    original = tmp_path / bad
    original.write_text("x", encoding="utf-8")
    doc = gates.SourceDoc("ok_id", "rfp", "2026-01-01", original, "x")
    with pytest.raises(gates.InputContractError, match="cannot be staged"):
        runner.stage_inputs(tmp_path / "run", [doc], INJECTION / "client.json")
    assert not (tmp_path / "run" / "inputs" / bad).exists()


# -- routing policy fails loudly -------------------------------------------------------------


def _routing(tmp_path, payload):
    path = tmp_path / "model_routing.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return path


@pytest.mark.parametrize("payload, needle", [
    ("{not json", "not readable JSON"),
    ([], "must be a JSON object"),
    ({"verify_extract": "sonnet"}, "must be an object"),
    ({"verify_extract": {"strong_modle": "sonnet"}}, "unknown key"),
    ({"verify_extract": {"strong_model": ""}}, "strong_model must be"),
    ({"verify_extract": {"base_model": 3}}, "base_model must be"),
    ({"verify_extract": {"risk_classes": "figures"}}, "risk_classes must be a list"),
    ({"verify_extract": {"risk_classes": ["figures", "vibes"]}}, "not computed"),
])
def test_a_malformed_routing_config_fails_loudly(tmp_path, payload, needle):
    with pytest.raises(extraction.ExtractionError, match=needle):
        extraction._verify_policy(_routing(tmp_path, payload))


def test_a_missing_routing_config_or_block_means_the_defaults(tmp_path):
    assert extraction._verify_policy(tmp_path / "absent.json")["strong_model"] == "sonnet"
    assert extraction._verify_policy(_routing(tmp_path, {"effort": {}}))["risk_classes"] == list(extraction.RISK_CLASSES)
    policy = extraction._verify_policy(_routing(tmp_path, {"verify_extract": {"base_model": "sonnet",
                                                                               "_note": "sonnet-only"}}))
    assert policy["base_model"] == "sonnet"


# -- the demo --------------------------------------------------------------------------------


TRANSCRIPT = REPO / "fixtures" / "northlight_01" / "transcript_kickoff.md"
GLOSSARY = REPO / "glossary" / "meltemi.json"


def test_demo_refuses_a_real_cli_without_opt_in(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(_fake_real_cli(tmp_path)))
    out = tmp_path / "out"
    code = run_demo.main([str(TRANSCRIPT), "--glossary", str(GLOSSARY), "--out", str(out)])
    assert code == run_demo.EXIT_LIVE_NOT_ENABLED and not out.exists()
    assert "[live calls]" in capsys.readouterr().err


def test_demo_refuses_input_without_a_data_declaration(tmp_path, fake_claude):
    folder = tmp_path / "undeclared"
    folder.mkdir()
    shutil.copy(TRANSCRIPT, folder / TRANSCRIPT.name)
    out = tmp_path / "out"
    code = run_demo.main([str(folder / TRANSCRIPT.name), "--glossary", str(GLOSSARY), "--out", str(out)])
    assert code == run_demo.EXIT_DATA_DECLARATION and not out.exists()
    with pytest.raises(SystemExit, match="declaration-folder"):
        run_demo.main(["-", "--glossary", str(GLOSSARY), "--out", str(out)])


def test_demo_replay_stages_inputs_and_records_the_transport(tmp_path, fake_claude):
    out = tmp_path / "out"
    status = _git_status()
    assert run_demo.main([str(TRANSCRIPT), "--glossary", str(GLOSSARY), "--out", str(out)]) == 0
    (run_dir,) = list(out.iterdir())
    staged = run_dir / "inputs" / TRANSCRIPT.name
    assert staged.read_bytes() == TRANSCRIPT.read_bytes() and not staged.stat().st_mode & 0o222
    assert (run_dir / "inputs" / "client" / GLOSSARY.name).is_file()
    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["cli"]["replay"] is True and manifest["live"] is False
    assert manifest["data_declaration"]["data_class"] == "synthetic"
    assert manifest["prescreen"]["scanned_files"] == 1
    assert (run_dir / "extracts" / "transcript_kickoff.json").is_file()
    assert _git_status() == status


def test_demo_fails_a_step_that_tampers_with_a_staged_input(tmp_path, fake_claude, monkeypatch):
    def tampering_classify(sources, run_dir, *args):
        staged = Path(run_dir) / "inputs" / TRANSCRIPT.name
        staged.chmod(0o644)
        staged.write_text("rewritten", encoding="utf-8")
        return {"attempts": []}

    monkeypatch.setattr(stages, "classify", tampering_classify)
    code = run_demo.main([str(TRANSCRIPT), "--glossary", str(GLOSSARY), "--out", str(tmp_path / "out")])
    assert code == run_demo.EXIT_INTEGRITY


# -- the shell entry points ------------------------------------------------------------------


def _shell_env(**extra):
    env = {k: v for k, v in os.environ.items() if k not in (agents.LIVE_ENV, "BRIEF_BUILDER_CLAUDE_BIN")}
    env.update(extra)
    return env


@pytest.mark.parametrize("script", ["demo.sh", "run_full.sh"])
def test_shell_scripts_parse(script):
    assert subprocess.run(["bash", "-n", str(REPO / script)], capture_output=True).returncode == 0


def test_run_full_without_a_mode_starts_nothing(tmp_path):
    proc = subprocess.run(["bash", str(REPO / "run_full.sh"), "--out", str(tmp_path / "o")],
                          capture_output=True, text=True, env=_shell_env())
    assert proc.returncode == 7 and "opt-in" in proc.stderr
    assert not (tmp_path / "o").exists()


def test_run_full_replay_rehearses_offline_into_its_out_dir(tmp_path):
    status, shelf = _git_status(), _tree_hash(REPO / "reviews")
    out = tmp_path / "o"
    proc = subprocess.run(["bash", str(REPO / "run_full.sh"), "--replay", "--out", str(out)],
                          capture_output=True, text=True, env=_shell_env(DEMO_NO_OPEN="1"))
    assert proc.returncode == 0 and "started (--replay)" in proc.stdout
    manifest = out / "live" / "run_manifest.json"
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline and not (manifest.is_file() and '"exit_code"' in manifest.read_text()):
        time.sleep(0.5)
    record = json.loads(manifest.read_text(encoding="utf-8"))
    assert record["outcome"] == "complete" and record["cli"]["replay"] is True
    assert _git_status() == status and _tree_hash(REPO / "reviews") == shelf


def test_demo_sh_replay_runs_offline(tmp_path):
    proc = subprocess.run(["bash", str(REPO / "demo.sh"), "--replay", "--out", str(tmp_path / "d")],
                          capture_output=True, text=True, env=_shell_env(DEMO_NO_OPEN="1"))
    assert proc.returncode == 0, proc.stderr
    assert "VERIFICATION GATES" in proc.stdout and "offline replay" in proc.stdout
