"""The seam between the deterministic runner and the Claude Code subagents.

One function matters here: `invoke`. It shells out to `claude -p --agent <name>`, which
means a pipeline run is reproducible by anyone with the repo and the CLI — no human in the
conversation loop. That is what makes `python pipeline/runner.py --project <folder>` the
whole demo, and it is what PRD §8's brief-champion runbook ("drop files → run one command →
read the verdict") actually requires.

`--output-format json` gives back usage, cost and — the part CLAUDE.md's workflow section
needs — the *resolved* model IDs behind the `haiku`/`sonnet` aliases. Alias resolution is
therefore observed per run rather than asserted from a registry table.

Clean substrate (PRD DR-1, README "substrate-dependent"): in production these stages are
metered API calls whose system prompt is the skeleton file alone. To model that here — and to
stop the repo's build-time `CLAUDE.md` leaking into a *runtime* agent's context — each subagent
is invoked with its definition passed inline (`--agents`) and run from a neutral working
directory that has no `CLAUDE.md` in its ancestry. `--add-dir` grants read/write only to the
specific project, schema, glossary, template and run directories, none of which is the repo
root. Verified empirically: `--agent` from the repo root loads `CLAUDE.md`; this path does not.
See `runs/tier_2_report.md` and the substrate-fix note.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

#: Overridable so tests never shell out to a real model.
CLAUDE_BIN = os.environ.get("BRIEF_BUILDER_CLAUDE_BIN", "claude")

#: Runtime agents read sources and write artifacts. This mirrors the `tools:` frontmatter —
#: belt and braces, because a permission prompt in a non-interactive run would hang it.
ALLOWED_TOOLS = ("Read", "Write")

DEFAULT_TIMEOUT_S = 600

#: Initial attempt + one repair round. Deliberately low, and shared by both repair loops so
#: the budget cannot diverge between them. Two is not a compromise: a transient slip is fixed
#: on the retry, while a *systematic* failure (the model making the same wrong choice every
#: time) should surface as a failure and be taught in the skeleton — not masked by burning more
#: retries on the same error. The citation-unresolvable investigation proved the point: a third
#: attempt would have re-failed identically; the fix belonged in SOURCES.md.
MAX_ATTEMPTS = 2

#: First `---` block only; the body (everything after) is the agent's system prompt.
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)

#: One neutral cwd per process, reused. It stays empty — agents read and write via absolute
#: paths under the --add-dir'd directories — so there is nothing to clean up between calls.
_NEUTRAL_CWD: Optional[str] = None


def _neutral_cwd() -> str:
    """A working directory with no CLAUDE.md in its ancestry, so none is auto-discovered."""
    global _NEUTRAL_CWD
    if _NEUTRAL_CWD is None or not os.path.isdir(_NEUTRAL_CWD):
        _NEUTRAL_CWD = tempfile.mkdtemp(prefix="bb-agent-cwd-")
    return _NEUTRAL_CWD


def _parse_frontmatter(text: str) -> tuple:
    """(frontmatter dict, body) for an agent .md file. Simple `key: value` lines only —
    deliberately no YAML dependency in the runtime path; the agent files use flat frontmatter."""
    match = _FRONTMATTER_RE.match(text)
    if not match:
        raise SubagentError("agent definition has no YAML frontmatter block")
    fields = {}
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip()
    return fields, match.group(2)


def build_inline_agent(name: str) -> dict:
    """Turn `.claude/agents/<name>.md` into the `--agents` inline payload {name: {...}}.

    Passing the definition inline is what lets the subagent run from a neutral cwd — the CLI
    never has to discover `.claude/agents/`, so it never has to sit in the repo where CLAUDE.md
    would be auto-loaded. The body is the system prompt verbatim (injected skill and all).
    """
    path = AGENTS_DIR / f"{name}.md"
    if not path.is_file():
        raise SubagentError(f"no agent definition at {path}")
    fields, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    spec = {"description": fields.get("description", ""), "prompt": body}
    tools = [t.strip() for t in fields.get("tools", "").split(",") if t.strip()]
    if tools:
        spec["tools"] = tools
    if fields.get("model"):
        spec["model"] = fields["model"]
    return {name: spec}


class SubagentError(Exception):
    """The subagent could not be run at all (binary missing, timeout, non-JSON output)."""


@dataclass
class SubagentResult:
    """What one subagent invocation cost and produced."""

    agent: str
    ok: bool
    result_text: str = ""
    session_id: str = ""
    model_ids: list = field(default_factory=list)
    cost_usd: Optional[float] = None
    duration_ms: Optional[int] = None
    num_turns: Optional[int] = None
    usage: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "agent": self.agent,
            "ok": self.ok,
            "session_id": self.session_id,
            "model_ids": self.model_ids,
            "cost_usd": self.cost_usd,
            "duration_ms": self.duration_ms,
            "num_turns": self.num_turns,
            "usage": self.usage,
        }


def _summarise_usage(payload: dict) -> dict:
    """Token counts, flattened across whichever shape the CLI reports."""
    usage = payload.get("usage") or {}
    keys = ("input_tokens", "output_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")
    summary = {k: usage.get(k) for k in keys if usage.get(k) is not None}

    model_usage = payload.get("modelUsage") or {}
    if model_usage and not summary:
        for per_model in model_usage.values():
            for k in keys:
                if per_model.get(k) is not None:
                    summary[k] = summary.get(k, 0) + per_model[k]
    return summary


def invoke(
    agent: str,
    prompt: str,
    access_dirs,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> SubagentResult:
    """Run one Claude Code subagent non-interactively, on a clean substrate, and report cost.

    `access_dirs` are the only directories the agent may read or write — the project sources,
    the schema, the glossary, the templates and the run output. The agent definition is passed
    inline and the process runs from a neutral cwd, so the repo's build-time CLAUDE.md is never
    auto-loaded into a runtime agent (see the module docstring).

    Raises SubagentError on infrastructure failure. A subagent that *ran* but produced bad
    output is not this function's problem — the caller validates artifacts against the schema,
    because "the model replied" and "the model was right" are different questions.
    """
    if shutil.which(CLAUDE_BIN) is None:
        raise SubagentError(
            f"'{CLAUDE_BIN}' not found on PATH. The pipeline drives Claude Code subagents; "
            f"set BRIEF_BUILDER_CLAUDE_BIN if the CLI lives elsewhere."
        )

    inline_agents = build_inline_agent(agent)
    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--agents", json.dumps(inline_agents, ensure_ascii=False),
        "--agent", agent,
        "--permission-mode", "acceptEdits",
        "--output-format", "json",
        "--allowedTools", *ALLOWED_TOOLS,
    ]
    seen = set()
    for directory in access_dirs:
        d = str(directory)
        if d not in seen:
            cmd += ["--add-dir", d]
            seen.add(d)

    try:
        proc = subprocess.run(
            cmd, cwd=_neutral_cwd(), capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise SubagentError(f"subagent '{agent}' exceeded {timeout_s}s") from exc

    if not proc.stdout.strip():
        raise SubagentError(
            f"subagent '{agent}' returned no output (exit {proc.returncode}): {proc.stderr[:800]}"
        )

    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise SubagentError(
            f"subagent '{agent}' returned non-JSON output: {proc.stdout[:800]}"
        ) from exc

    return SubagentResult(
        agent=agent,
        ok=(proc.returncode == 0 and not payload.get("is_error", False)),
        result_text=payload.get("result", "") or "",
        session_id=payload.get("session_id", "") or "",
        model_ids=sorted((payload.get("modelUsage") or {}).keys()),
        cost_usd=payload.get("total_cost_usd"),
        duration_ms=payload.get("duration_ms"),
        num_turns=payload.get("num_turns"),
        usage=_summarise_usage(payload),
    )
