"""agents.invoke — the one subprocess seam between the runner and a model — tested for real.

Everywhere else the seam is monkeypatched away. Here the real `subprocess.run` path runs
against the fake CLI (`tools/replay/claude`), whose failure modes are switched by environment
variable so the command line stays exactly what invoke built. The assertions hold the stable
contract (prompt, agent, inline definition, JSON output, scoped directories, neutral cwd) and
deliberately not every permission flag, which the least-privilege work may change.
"""

import json
from pathlib import Path

import pytest

from pipeline import agents, replay


def _flag_values(argv, flag):
    return [argv[i + 1] for i, token in enumerate(argv[:-1]) if token == flag]


def test_command_line_carries_prompt_agent_definition_and_scoped_dirs(fake_claude, tmp_path, monkeypatch):
    argv_log = tmp_path / "argv.json"
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_ARGV", str(argv_log))
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "exit:0")
    dirs = [tmp_path / "project", tmp_path / "run", tmp_path / "project"]  # duplicate on purpose

    result = agents.invoke("classify", "WORK ORDER text", dirs, timeout_s=60)

    record = json.loads(argv_log.read_text(encoding="utf-8"))
    argv = record["argv"]
    assert _flag_values(argv, "-p") == ["WORK ORDER text"]
    assert _flag_values(argv, "--agent") == ["classify"]
    inline = json.loads(_flag_values(argv, "--agents")[0])
    assert list(inline) == ["classify"] and inline["classify"]["prompt"].strip()
    assert _flag_values(argv, "--output-format") == ["json"]
    assert _flag_values(argv, "--add-dir") == [str(tmp_path / "project"), str(tmp_path / "run")]
    # Clean substrate: the CLI runs from a neutral directory with no CLAUDE.md above it.
    cwd = Path(record["cwd"]).resolve()
    assert agents.REPO_ROOT.resolve() not in [cwd, *cwd.parents]
    assert not any((d / "CLAUDE.md").exists() for d in [cwd, *cwd.parents])
    assert result.ok and result.agent == "classify"


def test_reply_is_parsed_into_usage_model_ids_and_cost(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "exit:0")
    result = agents.invoke("classify", "order", [], timeout_s=60)
    assert result.model_ids == [replay.REPLAY_MODEL_ID]
    assert result.cost_usd == 0.0
    assert result.usage == {"input_tokens": 0, "output_tokens": 0,
                            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    assert result.session_id == "offline-replay-fake"


def test_empty_stdout_is_an_infrastructure_error(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "empty")
    with pytest.raises(agents.SubagentError, match="returned no output.*no stdout on purpose"):
        agents.invoke("classify", "order", [], timeout_s=60)


def test_non_json_stdout_is_an_infrastructure_error(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "non_json")
    with pytest.raises(agents.SubagentError, match="non-JSON output: this is not JSON"):
        agents.invoke("classify", "order", [], timeout_s=60)


def test_is_error_reply_is_not_ok(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "is_error")
    result = agents.invoke("classify", "order", [], timeout_s=60)
    assert result.ok is False and result.result_text == "simulated CLI error"


def test_nonzero_exit_with_json_reply_is_not_ok(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "exit:3")
    result = agents.invoke("classify", "order", [], timeout_s=60)
    assert result.ok is False


def test_timeout_becomes_a_subagent_error(fake_claude, monkeypatch):
    monkeypatch.setenv("BRIEF_BUILDER_FAKE_CLAUDE_MODE", "sleep:10")
    with pytest.raises(agents.SubagentError, match="exceeded 1s"):
        agents.invoke("classify", "order", [], timeout_s=1)


def test_missing_binary_is_reported_before_any_subprocess(monkeypatch):
    monkeypatch.setattr(agents, "CLAUDE_BIN", "/nonexistent/brief-builder-claude")
    with pytest.raises(agents.SubagentError, match="not found on PATH"):
        agents.invoke("classify", "order", [], timeout_s=60)
