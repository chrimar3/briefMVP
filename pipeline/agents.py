"""The seam between the deterministic runner and the Claude Code subagents.

One function matters here: `invoke`. It shells out to `claude -p --agent <name>`, which
means a pipeline run is reproducible by anyone with the repo and the CLI — no human in the
conversation loop. That is what makes `python pipeline/runner.py --project <folder>` the
whole demo, and it is what PRD §8's brief-champion runbook ("drop files → run one command →
read the verdict") actually requires.

`--output-format json` gives back usage, cost and — the part CLAUDE.md's workflow section
needs — the *resolved* model IDs behind the `haiku`/`sonnet` aliases. Alias resolution is
therefore observed per run rather than asserted from a registry table.

Substrate note (PRD DR-1, README "substrate-dependent"): in production these stages are
metered API calls whose system prompt is the skeleton file alone. Here they are Claude Code
subagents, which additionally see the repo's `CLAUDE.md` build governance because memory
loads from the working directory upward. That is an artifact of the demo substrate, not of
the design; see `runs/tier_1_report.md` §6.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

#: Overridable so tests never shell out to a real model.
CLAUDE_BIN = os.environ.get("BRIEF_BUILDER_CLAUDE_BIN", "claude")

#: Runtime agents read sources and write artifacts. This mirrors the `tools:` frontmatter —
#: belt and braces, because a permission prompt in a non-interactive run would hang it.
ALLOWED_TOOLS = ("Read", "Write")

DEFAULT_TIMEOUT_S = 600


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
    cwd: Path,
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> SubagentResult:
    """Run one Claude Code subagent non-interactively and report what it cost.

    Raises SubagentError on infrastructure failure. A subagent that *ran* but produced bad
    output is not this function's problem — the caller validates artifacts against the schema,
    because "the model replied" and "the model was right" are different questions.
    """
    if shutil.which(CLAUDE_BIN) is None:
        raise SubagentError(
            f"'{CLAUDE_BIN}' not found on PATH. The pipeline drives Claude Code subagents; "
            f"set BRIEF_BUILDER_CLAUDE_BIN if the CLI lives elsewhere."
        )

    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--agent", agent,
        "--permission-mode", "acceptEdits",
        "--output-format", "json",
        "--allowedTools", *ALLOWED_TOOLS,
    ]

    try:
        proc = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout_s, check=False
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
