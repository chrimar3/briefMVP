"""Offline replay of a recorded run — the whole orchestration with zero model calls.

A new engineer (or CI) can watch every Stage-1 step run — work orders, gates, repair loop,
readiness injection, manifest, review pages — without a paid, authenticated `claude` CLI:

    BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" \\
        python3 pipeline/runner.py --project fixtures/northlight_01 --out /tmp/bb-replay

`tools/replay/claude` is a stand-in for the CLI, selected through the existing
`BRIEF_BUILDER_CLAUDE_BIN` override so `pipeline/agents.py` keeps exactly one call path (use
an absolute path: agents.invoke runs the binary from a neutral cwd). It hands its arguments
to `main()` below, which reads the work order (`-p`), finds the output paths the order
names, and copies the matching artifact from a recording (default
`tools/replay/recordings/northlight_01`, override with `BRIEF_BUILDER_REPLAY_RUN`). It then
prints a CLI-shaped JSON reply with zero usage and the model id `offline-replay`, so every
attempt in the manifest says plainly that no model produced it.

What replay is NOT: evidence of model quality. The artifacts are whatever the recording
holds; the gates re-check them against today's fixtures, so replay proves the wiring and the
gates, never the judgment. The default recording is derived from the graded `runs/tier3`
pack by `tools/replay/derive_recording.py`, which reverses only the human layer (sign-off,
conflict resolutions, readiness injection) and regenerates the two renders deterministically
against today's client-brief template — wiring fixtures, not evidence; see that script.

The fake accepts and ignores every flag it does not need (`--agents`, `--add-dir`,
`--effort`, …), so command-line changes in `agents.py` never break it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Pre-sign-off Stage-1 recording of fixtures/northlight_01, derived from runs/tier3.
DEFAULT_RECORDED_RUN = REPO_ROOT / "tools" / "replay" / "recordings" / "northlight_01"
RECORDED_RUN_ENV = "BRIEF_BUILDER_REPLAY_RUN"

#: Reported as the "model" of every replayed attempt, so a replayed manifest can never be
#: mistaken for a model run.
REPLAY_MODEL_ID = "offline-replay"

#: `  report    : /abs/path` style lines and the indented path under "exactly this path:".
#: A path runs to the end of its line, so directories with spaces survive; the render order's
#: trailing `(follows template_greek)` annotation is not part of the path.
_LABELLED_PATH_RE = re.compile(
    r"^[ \t]*(?:report|annotated|greek|english)[ \t]*:[ \t]*(/[^\n]*?)"
    r"(?:[ \t]+\(follows [^()\n]*\))?[ \t]*$",
    re.MULTILINE)
_EXACT_PATH_RE = re.compile(r"exactly this path[^\n]*:[ \t]*\n[ \t]*(/[^\n]*?)[ \t]*$", re.MULTILINE)
_REPAIR_PATH_RE = re.compile(r"previous extract at (/[^\n]+?) failed")
_PROJECT_ID_RE = re.compile(r"^\s*project_id\s*[:=]\s*(\S+)\s*$", re.MULTILINE)


class ReplayError(Exception):
    """The recording cannot answer this work order (wrong project, missing artifact)."""


def recorded_run() -> Path:
    """The recording being replayed: `$BRIEF_BUILDER_REPLAY_RUN` or the default recording."""
    configured = os.environ.get(RECORDED_RUN_ENV)
    return Path(configured).resolve() if configured else DEFAULT_RECORDED_RUN


def parse_cli(argv: list) -> tuple:
    """(agent, prompt) from a `claude` command line; every other flag is ignored.

    Accepts `-p PROMPT` / `--print PROMPT` and `--agent NAME` / `--agent=NAME`. When `-p` is
    a bare switch (prompt not on the command line) the prompt is read from stdin.
    """
    agent: Optional[str] = None
    prompt: Optional[str] = None
    index = 0
    while index < len(argv):
        token = argv[index]
        following = argv[index + 1] if index + 1 < len(argv) else None
        if token in ("-p", "--print"):
            if following is not None and not following.startswith("--"):
                prompt = following
                index += 1
            else:
                prompt = ""
        elif token == "--agent" and following is not None:
            agent = following
            index += 1
        elif token.startswith("--agent="):
            agent = token.split("=", 1)[1]
        index += 1
    if prompt == "" and not sys.stdin.isatty():
        prompt = sys.stdin.read()
    if not agent:
        raise ReplayError("no --agent on the command line")
    return agent, prompt or ""


def output_paths(prompt: str) -> list:
    """Every absolute output path a work order (or repair order) names, in order."""
    found = _EXACT_PATH_RE.findall(prompt) + _LABELLED_PATH_RE.findall(prompt)
    found += _REPAIR_PATH_RE.findall(prompt)
    return [Path(p) for p in dict.fromkeys(found)]


def _recorded_project_id(recording: Path) -> Optional[str]:
    classification = recording / "classification.json"
    if classification.is_file():
        return json.loads(classification.read_text(encoding="utf-8")).get("project_id")
    manifest = recording / "run_manifest.json"
    if manifest.is_file():
        project_dir = json.loads(manifest.read_text(encoding="utf-8")).get("project_dir")
        return Path(project_dir).name if project_dir else None
    return None


def _recorded_copy(recording: Path, target: Path) -> Path:
    """The recording's file for `target`: same parent folder name + file name, else same name."""
    for candidate in (recording / target.parent.name / target.name, recording / target.name):
        if candidate.is_file():
            return candidate
    raise ReplayError(f"the recording {recording} has no artifact for {target.name}")


def replay(agent: str, prompt: str, recording: Optional[Path] = None) -> list:
    """Write the recorded artifacts for one work order; return the paths written."""
    recording = Path(recording) if recording else recorded_run()
    if not recording.is_dir():
        raise ReplayError(f"recorded run {recording} does not exist")
    asked = _PROJECT_ID_RE.search(prompt)
    recorded_id = _recorded_project_id(recording)
    if asked and recorded_id and asked.group(1) != recorded_id:
        raise ReplayError(
            f"the recording {recording.name} is project {recorded_id!r}; this work order is for "
            f"{asked.group(1)!r}. Replay only reproduces the project it recorded."
        )
    targets = output_paths(prompt)
    if not targets and prompt.lstrip().startswith("REPAIR ORDER"):
        # A repair order that names no path: the recording holds one answer per artifact, so
        # the honest replay leaves it unchanged and lets the gate judge it again.
        return []
    if not targets:
        raise ReplayError(f"no output path found in the {agent!r} work order")
    written = []
    for target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_recorded_copy(recording, target), target)
        written.append(target)
    return written


def cli_reply(agent: str, result: str, is_error: bool = False) -> dict:
    """A reply in the shape `claude -p --output-format json` prints, with zero usage."""
    zero = {"input_tokens": 0, "output_tokens": 0,
            "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0}
    return {
        "type": "result",
        "subtype": "error" if is_error else "success",
        "is_error": is_error,
        "result": result,
        "session_id": f"offline-replay-{agent}",
        "num_turns": 1,
        "duration_ms": 0,
        "total_cost_usd": 0.0,
        "usage": zero,
        "modelUsage": {REPLAY_MODEL_ID: dict(zero)},
    }


def main(argv: Optional[list] = None) -> int:
    """Entry point of the fake `claude` binary. Exit 0 on a replayed order, 1 otherwise."""
    argv = sys.argv[1:] if argv is None else argv
    if argv in (["-h"], ["--help"]):
        print(__doc__)
        return 0
    agent = "unknown"
    try:
        agent, prompt = parse_cli(argv)
        written = replay(agent, prompt)
    except (ReplayError, OSError, ValueError) as exc:
        print(json.dumps(cli_reply(agent, f"offline replay failed: {exc}", is_error=True)))
        print(f"offline replay: {exc}", file=sys.stderr)
        return 1
    names = ", ".join(p.name for p in written) or "nothing (repair order; recording unchanged)"
    print(json.dumps(cli_reply(agent, f"replayed {names} from {recorded_run().name}")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
