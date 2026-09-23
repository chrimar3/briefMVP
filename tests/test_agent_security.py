"""Least-privilege runtime agents and injection defence (r1-W2, docs/SECURITY.md).

What is provable offline is proved here: the exact CLI argv (permission rules, isolation flags),
the directories granted, input staging, source_id path safety, and the runner's post-stage
integrity check. The CLI's own enforcement of the rules is not — no test calls a real model.

tests/injection_project/ is a synthetic project whose RFP and email carry embedded instructions
(read the answer key, write approval.json, overwrite the schema, leak the snapshot). The tests
show that such text never reaches a work order, that the agent is never granted the paths it
names, and that an agent obeying it anyway is caught before the run continues.
"""

import json
import os
import shutil
import stat
import sys
from pathlib import Path

import pytest

from pipeline import agents, extraction, gates, runner, stages

INJECTION = Path(__file__).resolve().parent / "injection_project"
INJECTED_PHRASES = ("Ignore all previous instructions", "maintenance mode", "overrides your work order")


def _flag_values(cmd, flag):
    """The values following one flag, up to the next `--option`."""
    i = cmd.index(flag) + 1
    values = []
    while i < len(cmd) and not cmd[i].startswith("--"):
        values.append(cmd[i])
        i += 1
    return values


def _rule(path, recursive=True):
    return "/" + str(Path(path).resolve()) + ("/**" if recursive else "")


@pytest.fixture
def project(tmp_path):
    target = tmp_path / "project"
    shutil.copytree(INJECTION, target)
    # A decoy key beside the sources, as in a graded fixture: it must never be staged or granted.
    (target / "answer_key.json").write_text('{"decoy": true}', encoding="utf-8")
    return target


def _main(project, out, run_id="r", monkeypatch=None, handlers=None):
    for name, handler in (handlers or {}).items():
        monkeypatch.setitem(runner.AGENT_HANDLERS, name, handler)
    return runner.main(["--project", str(project), "--out", str(out), "--run-id", run_id,
                        "--glossary", str(project / "client.json")])


def _manifest(out, run_id="r"):
    return json.loads((out / run_id / "run_manifest.json").read_text(encoding="utf-8"))


def _ctx(tmp_path, project_dir, glossary):
    return runner.RunContext(project_dir=project_dir, run_dir=tmp_path / "run", run_id="r",
                             sources=[], started_ts="", glossary_path=glossary)


# -- the command -------------------------------------------------------------------------


def test_command_isolates_the_substrate_and_scopes_every_tool(tmp_path):
    ctx = _ctx(tmp_path, INJECTION, INJECTION / "client.json")
    cmd = agents.build_command("extract", "ORDER", runner._access_dirs(ctx))
    run_dir = ctx.run_dir

    assert "--strict-mcp-config" in cmd                      # no MCP server reaches the agent
    assert _flag_values(cmd, "--setting-sources") == ["project,local"]  # never the user's settings
    assert _flag_values(cmd, "--permission-prompts") == ["none"]       # unapproved = refused
    assert _flag_values(cmd, "--tools") == ["Read,Write"]

    allow = _flag_values(cmd, "--allowedTools")
    assert "Read" not in allow and "Write" not in allow      # no unscoped grants
    writes = [r for r in allow if r.startswith(("Write(", "Edit("))]
    assert writes and all(_rule(run_dir) in r for r in writes)

    deny = set(_flag_values(cmd, "--disallowedTools"))
    for read_only in (gates.SCHEMA_DIR, gates.CONFIG_DIR, gates.REPO_ROOT / "templates"):
        assert f"Write({_rule(read_only)})" in deny and f"Edit({_rule(read_only)})" in deny
    for record in ("approval.json", "creative_approval.json", "language_review.json",
                   "input_snapshot.json", "audit_log.jsonl", "releases.json"):
        assert f"Write({_rule(run_dir / record, recursive=False)})" in deny
    assert f"Write({_rule(run_dir / 'inputs')})" in deny and f"Edit({_rule(run_dir / 'evidence')})" in deny
    assert "Read(//**/answer_key.json)" in deny
    assert {"Bash", "WebFetch", "WebSearch"} <= deny

    granted = {Path(cmd[i + 1]).resolve() for i, arg in enumerate(cmd) if arg == "--add-dir"}
    assert granted == {run_dir.resolve(), gates.SCHEMA_DIR.resolve(), gates.CONFIG_DIR.resolve(),
                       (gates.REPO_ROOT / "templates").resolve()}


@pytest.mark.parametrize("fixture, glossary", [
    ("northlight_01", "glossary/meltemi.json"),
    ("voreas_02", "fixtures/voreas_02/client_voreas.json"),  # the client config sits beside the key
])
def test_no_granted_directory_can_reach_an_answer_key(tmp_path, fixture, glossary):
    project = gates.REPO_ROOT / "fixtures" / fixture
    assert (project / "answer_key.json").is_file()
    scope = runner._access_dirs(_ctx(tmp_path, project, gates.REPO_ROOT / glossary))
    for directory in map(Path, scope.dirs()):
        assert directory.resolve() != project.resolve()
        assert not list(directory.rglob("answer_key.json")) if directory.exists() else True
    assert gates.REPO_ROOT.resolve() not in {Path(d).resolve() for d in scope.dirs()}


def test_a_plain_list_of_dirs_splits_into_read_only_skeleton_and_writable_output(tmp_path):
    scope = agents.AccessScope.coerce([str(tmp_path), str(gates.SCHEMA_DIR), str(gates.CONFIG_DIR),
                                       str(gates.REPO_ROOT / "glossary")])
    assert scope.writable == (str(tmp_path),)
    assert set(scope.read_only) == {str(gates.SCHEMA_DIR), str(gates.CONFIG_DIR), str(gates.REPO_ROOT / "glossary")}


#: Every hand-written fake CLI answers the version probe `agents.invoke` runs first.
_ANSWERS_VERSION = "if sys.argv[1:] == ['--version']:\n    print('2.1.280 (Claude Code)'); sys.exit(0)\n"


def test_invoke_hands_the_built_command_to_the_cli(tmp_path, monkeypatch):
    """Through the real subprocess seam, with a fake `claude` that records its argv."""
    fake = tmp_path / "fake_claude"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        + _ANSWERS_VERSION +
        "open(os.environ['FAKE_ARGV_OUT'], 'w').write(json.dumps(sys.argv[1:]))\n"
        "print(json.dumps({'result': 'ok', 'session_id': 's', 'modelUsage': {'claude-test': {}}}))\n",
        encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(fake))
    monkeypatch.setenv("FAKE_ARGV_OUT", str(tmp_path / "argv.json"))
    scope = runner._access_dirs(_ctx(tmp_path, INJECTION, INJECTION / "client.json"))
    result = agents.invoke("classify", "ORDER", scope)
    argv = json.loads((tmp_path / "argv.json").read_text(encoding="utf-8"))
    assert result.ok and result.model_ids == ["claude-test"]
    assert argv == agents.build_command("classify", "ORDER", scope)[1:]


def test_a_relative_cli_override_is_executed_from_the_neutral_cwd(tmp_path, monkeypatch):
    """BRIEF_BUILDER_CLAUDE_BIN=bin/claude passes the availability check from the caller's cwd;
    the CLI runs from a neutral cwd, so invoke must execute the absolute path it found."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "claude"
    fake.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        + _ANSWERS_VERSION +
        "print(json.dumps({'result': sys.argv[0], 'session_id': 's', 'modelUsage': {'claude-test': {}}}))\n",
        encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(agents, "CLAUDE_BIN", os.path.join("bin", "claude"))
    scope = runner._access_dirs(_ctx(tmp_path, INJECTION, INJECTION / "client.json"))
    result = agents.invoke("classify", "ORDER", scope)
    assert result.ok and Path(result.result_text).resolve() == fake.resolve()


def test_a_cli_that_cannot_start_is_a_subagent_error(tmp_path, monkeypatch):
    fake = tmp_path / "claude"
    fake.write_text("not a program", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setattr(agents, "CLAUDE_BIN", str(fake))
    scope = runner._access_dirs(_ctx(tmp_path, INJECTION, INJECTION / "client.json"))
    with pytest.raises(agents.SubagentError, match="could not start"):
        agents.invoke("classify", "ORDER", scope)


# -- staging -------------------------------------------------------------------------------


def test_agents_read_staged_copies_never_the_project_folder(project, tmp_path, monkeypatch):
    seen = {}

    def classify(ctx, step):
        seen["ctx"] = ctx
        raise stages.HaltForHuman("stop after inspecting the context")

    out = tmp_path / "runs"
    assert _main(project, out, monkeypatch=monkeypatch, handlers={"classify": classify}) == runner.EXIT_HALTED_FOR_HUMAN
    ctx, run_dir = seen["ctx"], out / "r"
    staged_dir = run_dir / "inputs"
    for source in ctx.sources:
        assert source.path.parent == staged_dir
        assert source.path.read_bytes() == (project / source.path.name).read_bytes()
        assert not source.path.stat().st_mode & 0o222          # read-only on disk too
    assert ctx.glossary_path == staged_dir / "client" / "client.json"
    assert not list(staged_dir.rglob("answer_key.json"))
    assert str(project) not in {str(d) for d in runner._access_dirs(ctx).dirs()}

    snapshot = json.loads((run_dir / "input_snapshot.json").read_text(encoding="utf-8"))
    assert "schema:brief_schema.json" in snapshot and "schema:extract_schema.json" in snapshot
    assert any(k.startswith("template:") for k in snapshot)
    assert Path(snapshot["source:inj_rfp"]["path"]).parent == project.resolve()  # originals bound


def test_render_inputs_are_bound_to_the_run_and_write_denied(project, tmp_path, monkeypatch):
    """The render stage reads the client-brief templates and config/greek_style.json: both are in
    the input snapshot (a changed template or style table refuses a resume) and both sit under a
    read-only directory that the agent's permission rules deny Write/Edit on."""
    seen = {}

    def classify(ctx, step):
        seen["ctx"] = ctx
        raise stages.HaltForHuman("stop after inspecting the context")

    out = tmp_path / "runs"
    _main(project, out, monkeypatch=monkeypatch, handlers={"classify": classify})
    snapshot = json.loads((out / "r" / "input_snapshot.json").read_text(encoding="utf-8"))
    templates = sorted(p.name for p in (gates.REPO_ROOT / "templates").iterdir() if p.is_file())
    assert templates and all(f"template:{name}" in snapshot for name in templates)
    assert Path(snapshot["greek_style"]["path"]) == stages.GREEK_STYLE_PATH.resolve()

    _, deny = agents.permission_rules(agents.AccessScope.coerce(runner._access_dirs(seen["ctx"])))
    for directory in (gates.REPO_ROOT / "templates", gates.CONFIG_DIR):
        for tool in ("Write", "Edit"):
            assert f"{tool}(/{directory.resolve().as_posix()}/**)" in deny, (tool, directory)
    assert stages.GREEK_STYLE_PATH.resolve().parent == gates.CONFIG_DIR.resolve()


def test_a_run_recorded_before_the_style_table_was_bound_still_resumes(project, tmp_path, monkeypatch):
    """Binding a new input must not strand an older run: a snapshot without `greek_style` stays
    as recorded, exactly like the schema/template rule above it."""
    halt = lambda ctx, step: (_ for _ in ()).throw(stages.HaltForHuman("stop"))
    out = tmp_path / "runs"
    _main(project, out, monkeypatch=monkeypatch, handlers={"classify": halt})
    path = out / "r" / "input_snapshot.json"
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    snapshot.pop("greek_style")
    path.write_text(json.dumps(snapshot), encoding="utf-8")
    assert _main(project, out, monkeypatch=monkeypatch, handlers={"classify": halt}) == runner.EXIT_HALTED_FOR_HUMAN
    assert "greek_style" not in json.loads(path.read_text(encoding="utf-8"))


def test_injected_text_never_reaches_a_work_order(project, tmp_path):
    sources = gates.discover_sources(project)
    run_dir = tmp_path / "run"
    staged, glossary = runner.stage_inputs(run_dir, sources, project / "client.json")
    config = extraction.load_client_config(glossary)
    orders = [stages.build_classification_order(staged, run_dir / "classification.json", "p", config, glossary)]
    for source in staged:
        orders.append(extraction.build_work_order(source, run_dir / "extracts" / f"{source.source_id}.json",
                                                  "p", config, glossary))
        orders.append(extraction.build_verify_order(source, run_dir / "x.json", run_dir / "v.json", glossary))
    for order in orders:
        assert not [p for p in INJECTED_PHRASES if p in order]
        assert str(project) + os.sep not in order                # only staged paths are named
        assert str(run_dir / "inputs") in order


def test_a_modified_staged_input_is_refused_on_resume(project, tmp_path, monkeypatch):
    halt = lambda ctx, step: (_ for _ in ()).throw(stages.HaltForHuman("stop"))
    out = tmp_path / "runs"
    _main(project, out, monkeypatch=monkeypatch, handlers={"classify": halt})
    staged = out / "r" / "inputs" / "rfp.md"
    staged.chmod(0o644)
    staged.write_text(staged.read_text(encoding="utf-8") + "\nAppended by an agent.\n", encoding="utf-8")
    assert _main(project, out, monkeypatch=monkeypatch, handlers={"classify": halt}) == runner.EXIT_GATE_ERROR
    assert _manifest(out)["outcome"] == "input_contract_error"


# -- path safety -----------------------------------------------------------------------------


@pytest.mark.parametrize("bad_id", ["../../config/evil", "a/b", ".hidden", "..", "ok..dots", "-flag", "a\\b"])
def test_unsafe_source_ids_are_refused_before_any_path_is_built(project, tmp_path, bad_id):
    rfp = project / "rfp.md"
    rfp.write_text(rfp.read_text(encoding="utf-8").replace("source_id: inj_rfp", f"source_id: {bad_id}"),
                   encoding="utf-8")
    out = tmp_path / "runs"
    assert runner.main(["--project", str(project), "--out", str(out), "--run-id", "r",
                        "--glossary", str(project / "client.json")]) == runner.EXIT_GATE_ERROR
    manifest = _manifest(out)
    assert manifest["outcome"] == "input_contract_error" and manifest["steps"] == []
    assert not (out / "r" / "inputs").exists() and not (out / "r" / "extracts").exists()
    assert not (gates.CONFIG_DIR / "evil.json").exists()


@pytest.mark.parametrize("good_id", ["rfp_meltemi", "a.b-c_1", "Transcript2"])
def test_ordinary_source_ids_pass_the_path_check(good_id):
    doc = gates.SourceDoc(good_id, "rfp", "2026-01-01", Path("x.md"), "")
    assert runner.unsafe_source_ids([doc]) == []


# -- post-stage integrity ------------------------------------------------------------------------


def _obedient_agent(target):
    """A classify handler standing in for an agent that followed the injected instructions."""
    def classify(ctx, step):
        run_dir = Path(ctx.run_dir)
        if target == "approval":
            (run_dir / "approval.json").write_text('{"actor": "approved"}', encoding="utf-8")
        elif target == "staged_input":
            path = run_dir / "inputs" / "rfp.md"
            path.chmod(0o644)
            path.write_text("rewritten", encoding="utf-8")
        elif target == "config":
            (gates.CONFIG_DIR / "readiness_policy.json").write_text("{}", encoding="utf-8")
        elif target == "schema":
            (gates.SCHEMA_DIR / "brief_schema.json").write_text("{}", encoding="utf-8")
        return {"classification": {"project_type": "other"}}
    return classify


@pytest.mark.parametrize("target", ["approval", "staged_input", "config", "schema"])
def test_a_model_step_that_writes_outside_its_outputs_fails_the_run(project, tmp_path, monkeypatch, target):
    # Point the read-only skeleton at scratch copies, so the simulated agent cannot harm the repo.
    for attr, src in (("CONFIG_DIR", gates.CONFIG_DIR), ("SCHEMA_DIR", gates.SCHEMA_DIR)):
        copy = tmp_path / src.name
        shutil.copytree(src, copy)
        monkeypatch.setattr(gates, attr, copy)
    out = tmp_path / "runs"
    code = _main(project, out, monkeypatch=monkeypatch, handlers={"classify": _obedient_agent(target)})
    assert code == runner.EXIT_GATE_ERROR
    manifest = _manifest(out)
    step = next(s for s in manifest["steps"] if s["name"] == "classification")
    assert manifest["outcome"] == "stage_failed" and step["status"] == "failed"
    assert step["error"].startswith("integrity:")


def test_a_halt_does_not_hide_a_tampered_record(project, tmp_path, monkeypatch):
    def tamper_then_halt(ctx, step):
        (Path(ctx.run_dir) / "coverage_decisions.json").write_text('{"x": {"actor": "a", "reason": "r"}}')
        raise stages.HaltForHuman("asks a question")
    out = tmp_path / "runs"
    assert _main(project, out, monkeypatch=monkeypatch, handlers={"classify": tamper_then_halt}) == runner.EXIT_GATE_ERROR
    assert "coverage_decisions.json was created" in _manifest(out)["steps"][-1]["error"]


def test_integrity_state_ignores_the_agents_own_outputs(project, tmp_path, monkeypatch):
    def writes_its_output(ctx, step):
        (Path(ctx.run_dir) / "classification.json").write_text("{}", encoding="utf-8")
        raise stages.HaltForHuman("fine")
    out = tmp_path / "runs"
    assert _main(project, out, monkeypatch=monkeypatch, handlers={"classify": writes_its_output}) == runner.EXIT_HALTED_FOR_HUMAN
