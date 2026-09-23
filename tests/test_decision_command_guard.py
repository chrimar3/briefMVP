"""Coding agents are blocked from the human-decision commands (owner decision 2026-09-23 #4):
the tracked .claude/settings.json deny rules and the PreToolUse hook in tools/hooks/.

Synthetic command strings only: nothing here runs a decision command.
"""

import argparse
import importlib.util
import json
import subprocess
import sys

import pytest

from pipeline import agency, delivery, release_control, retention


@pytest.fixture(scope="module")
def guard(repo_root):
    spec = importlib.util.spec_from_file_location("guard_human_decisions",
                                                  repo_root / "tools" / "hooks" / "guard_human_decisions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BLOCKED = [
    "python3 -m pipeline.agency approve runs/x --actor 'Lead A' --summary ok",
    "python -m pipeline.agency attest runs/x --actor B --greek-register 4 --notes n --checks a",
    "python3.11 -m pipeline.agency resolve runs/x --index 0 --actor A --text July",
    "python3 -m pipeline.agency apply runs/x --candidate c.json --actor A --reason r",
    "python3 -m pipeline.agency answer runs/x --id q --status duplicate --text t --owner o --priority n --actor A",
    "python3 -m pipeline.agency exclude runs/x --fact f --reason r --actor A",
    "python3 -m pipeline.agency carry-decisions runs/new --parent runs/old --actor A",
    "python3 -m pipeline.delivery register runs/x --draft d.md --actor O",
    "python3 -m pipeline.delivery approve runs/x --actor C --notes n --checks all_facts_cited",
    "python3 -m pipeline.delivery release runs/x --output /tmp/p --actor T",
    "python3 -m pipeline.release_control withdraw runs/x --actor A --reason r",
    "python3 -m pipeline.retention purge --run runs/x --actor O --reason r",
    # argument order and interpreter flags
    "python3 -m pipeline.agency --actor 'Lead A' approve runs/x --summary ok",
    "python3 -u -W ignore -m pipeline.agency approve runs/x --actor A --summary s",
    "python3 -mpipeline.delivery release runs/x --output o --actor T",
    # prefixes, wrappers and compound commands
    "cd /repo && python3 -m pipeline.agency approve runs/x --actor A --summary s",
    "cd /repo; python3 -m pipeline.agency approve runs/x --actor A --summary s",
    "true || python3 -m pipeline.delivery approve runs/x --actor C --notes n --checks x",
    "PYTHONPATH=. BRIEF=1 python3 -m pipeline.agency resolve runs/x --index 0 --actor A --text t",
    "env -i PATH=/usr/bin python3 -m pipeline.agency approve runs/x --actor A --summary s",
    "timeout 60 python3 -m pipeline.delivery release runs/x --output o --actor T",
    "nohup python3 -m pipeline.agency approve runs/x --actor A --summary s &",
    "uv run python -m pipeline.agency approve runs/x --actor A --summary s",
    "/usr/bin/python3 -m pipeline.agency approve runs/x --actor A --summary s",
    "(cd /repo && python3 -m pipeline.agency attest runs/x --actor B --greek-register 4 --notes n --checks a)",
    "echo start\npython3 -m pipeline.agency approve runs/x --actor A --summary s",
    # path spellings
    "python3 pipeline/agency.py approve runs/x --actor A --summary s",
    "python3 ./pipeline/delivery.py release runs/x --output o --actor T",
    "python3 /abs/repo/pipeline/agency.py resolve runs/x --index 0 --actor A --text t",
    "./pipeline/agency.py approve runs/x --actor A --summary s",
    # shells and eval
    "bash -c 'python3 -m pipeline.agency approve runs/x --actor A --summary s'",
    "sh -c \"cd /repo && python3 -m pipeline.delivery approve runs/x --actor C --notes n --checks x\"",
    "zsh -lc 'python3 -m pipeline.agency resolve runs/x --index 0 --actor A --text t'",
    "eval python3 -m pipeline.agency approve runs/x --actor A --summary s",
    # in-process calls
    "python3 -c \"from pipeline import agency; agency.approve(Path('runs/x'), 'Lead A', 'ok')\"",
    "python3 -c 'import pipeline.delivery as d; d.release(r, o, \"T\")'",
    "python3 -c \"from pipeline import agency; agency.main(['resolve', 'runs/x'])\"",
    "python3 -c 'from pipeline import approval; approval.record_regime(r, \"brief_signoff\", \"A\", \"x\")'",
    "python3 - <<'EOF'\nfrom pipeline import agency\nagency.resolve(run, 0, 'A', 'July')\nEOF",
    "python3 <<EOF\nfrom pipeline import delivery\ndelivery.approve(run, 'C', 'n', CHECKS)\nEOF",
    "echo \"from pipeline import agency; agency.attest(r)\" | python3",
]

ALLOWED = [
    "ls -la",
    "python3 -m pytest -q tests/test_governance_controls.py",
    "python3 -m pytest -q -k approve",
    "python3 -m pipeline.agency audit runs/x",
    "python3 -m pipeline.agency queue runs/x",
    "python3 -m pipeline.agency --help",
    "python3 -m pipeline.agency diff runs/x --before b.json",
    "python3 -m pipeline.release_control verify-log runs/rehearsal-lifecycle/records",
    "python3 -m pipeline.release_control verify pkg --run runs/x",
    "python3 -m pipeline.retention inventory --runs runs/x",
    "python3 -m pipeline.retention purge --run runs/x --dry-run --actor O --reason preview",
    "grep -n approve pipeline/agency.py",
    "sed -n 1,40p pipeline/delivery.py",
    "git diff pipeline/agency.py",
    "bash scripts/check.sh",
    "python3 runs/rehearsal-lifecycle/regenerate.py --out /tmp/x",
    "python3 -c 'from pipeline import agency; print(agency.audit(r, persist=False))'",
    "echo 'python3 -m pipeline.agency approve' > notes.txt",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_the_guard_blocks_every_spelling_of_a_decision_command(guard, command):
    assert guard.decision_in(command), command


@pytest.mark.parametrize("command", ALLOWED)
def test_the_guard_leaves_ordinary_work_alone(guard, command):
    assert guard.decision_in(command) is None, command


def test_the_hook_protocol_blocks_with_exit_2_and_a_reason(repo_root):
    script = repo_root / "tools" / "hooks" / "guard_human_decisions.py"
    def run(command):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
        return subprocess.run([sys.executable, str(script)], input=payload, capture_output=True, text=True, timeout=30)
    blocked = run("cd /repo && python3 -m pipeline.agency approve runs/x --actor A --summary s")
    assert blocked.returncode == 2 and "human-decision" in blocked.stderr and "owner decision" in blocked.stderr
    allowed = run("python3 -m pipeline.agency audit runs/x")
    assert allowed.returncode == 0 and allowed.stderr == ""
    assert subprocess.run([sys.executable, str(script)], input="not json", capture_output=True, text=True,
                          timeout=30).returncode == 0


def _subcommands(module, monkeypatch):
    """The subcommand names a module's argparse CLI defines, read from the parser itself."""
    captured = {}

    def capture(self, *args, **kwargs):
        captured["parser"] = self
        raise SystemExit(0)
    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", capture)
    with pytest.raises(SystemExit):
        module.main([])
    monkeypatch.undo()
    action = next(a for a in captured["parser"]._actions if isinstance(a, argparse._SubParsersAction))
    return set(action.choices)


#: Every subcommand is classified. A new subcommand fails this test until someone decides whether
#: it records a human decision (and so must be blocked for coding agents) or not.
READ_ONLY = {
    "pipeline.agency": {"init", "audit", "queue", "diff", "handover", "client-pack"},
    "pipeline.delivery": set(),
    "pipeline.release_control": {"verify", "verify-log"},
    "pipeline.retention": {"inventory"},
}


@pytest.mark.parametrize("name, module", [("pipeline.agency", agency), ("pipeline.delivery", delivery),
                                          ("pipeline.release_control", release_control),
                                          ("pipeline.retention", retention)])
def test_every_subcommand_is_classified_and_every_decision_is_guarded(guard, monkeypatch, name, module):
    commands = _subcommands(module, monkeypatch)
    decisions = guard.DECISION_COMMANDS[name]
    assert commands == decisions | READ_ONLY[name], f"unclassified subcommands in {name}"
    for command in decisions:
        assert guard.decision_in(f"python3 -m {name} {command} runs/x --actor A")


def test_settings_deny_every_decision_command_in_every_plain_spelling(guard, repo_root):
    settings = json.loads((repo_root / ".claude" / "settings.json").read_text(encoding="utf-8"))
    deny = set(settings["permissions"]["deny"])
    for module, commands in guard.DECISION_COMMANDS.items():
        if module == "pipeline.retention":
            continue                  # purge --dry-run is allowed; the hook tells them apart
        script = module.replace(".", "/") + ".py"
        for command in commands:
            for prefix in (f"python3 -m {module}", f"python -m {module}", f"python3 {script}", f"python {script}"):
                assert f"Bash({prefix} {command} *)" in deny, (prefix, command)
    hooks = settings["hooks"]["PreToolUse"]
    bash = [h for entry in hooks if entry["matcher"] == "Bash" for h in entry["hooks"]]
    assert any("tools/hooks/guard_human_decisions.py" in h["command"] for h in bash)


def test_the_settings_file_is_tracked_not_ignored(repo_root):
    result = subprocess.run(["git", "check-ignore", "-q", ".claude/settings.json"], cwd=repo_root, timeout=30)
    assert result.returncode == 1          # 1 = not ignored
