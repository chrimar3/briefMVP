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
directory that has no `CLAUDE.md` in its ancestry. Verified empirically: `--agent` from the
repo root loads `CLAUDE.md`; this path does not. See `runs/tier_2_report.md` and the
substrate-fix note.

Least privilege (docs/SECURITY.md). A runtime agent reads client-authored text, so it is
treated as a component that may be steered by what it reads. `AccessScope` separates the ONE
directory it may write (the run directory) from the directories it may only read (schema/,
templates/, config/), and names the records inside the run directory it must never write
(staged inputs, human decisions, evidence copies, the audit log). `build_command` turns that
scope into CLI permission rules: path-scoped allow rules, explicit deny rules for every
read-only directory and protected record, a deny rule for any `answer_key.json`, no shell or
web tools, no user/project settings, hooks or MCP servers, and no interactive permission
prompts (anything not pre-approved is refused). The CLI enforces the rules; the runner's
post-stage integrity check (pipeline/runner.py) detects a write that got through anyway.

Session hygiene (round 2). Every invocation passes `--no-session-persistence`, so the CLI keeps
no transcript of what the agent read (client documents) in the operator's profile, and
`--restricted`, which drops every code-running tool and all settings files and confines the file
tools to the granted directories. The CLI's version is probed once per binary and refused below
`MIN_CLI_VERSION` — the release these flags were checked against — so an older CLI can never run
a stage without them. The probe result is what the run manifest records (`cli_record`).

Live calls are opt-in. Which binary is in use is decided here (`resolve_cli`, `is_replay_cli`);
the runner and the demo refuse to start a real CLI unless `--live` or `BRIEF_BUILDER_LIVE=1`
is given (`live_refusal`). The offline replay binary (`tools/replay/claude`) needs no opt-in.
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
from typing import Callable, Optional

from pipeline import diagnostics

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

#: Overridable so tests never shell out to a real model.
CLAUDE_BIN = os.environ.get("BRIEF_BUILDER_CLAUDE_BIN", "claude")

#: The offline stand-in for the CLI (pipeline/replay.py). It makes no model call, so running it
#: needs no live opt-in.
REPLAY_CLI = REPO_ROOT / "tools" / "replay" / "claude"

#: Live model calls are opt-in: `--live` on the command line, or this variable set to "1".
LIVE_ENV = "BRIEF_BUILDER_LIVE"

#: The oldest CLI release the flags in `build_command` were checked against (`claude --help`,
#: 2026-09-23). `--no-session-persistence`, `--restricted`, `--permission-prompts` and `--tools`
#: are recent; an older CLI is refused before any stage runs rather than trusted to reject them.
MIN_CLI_VERSION = (2, 1, 280)

#: `claude --version` answers within seconds; this is an infrastructure ceiling, not a gate.
VERSION_PROBE_TIMEOUT_S = 60

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")

#: {absolute binary path: its `--version` line}, probed once per process and binary.
_CLI_VERSIONS: dict = {}

#: Runtime agents read sources and write artifacts. This mirrors the `tools:` frontmatter and
#: is passed as `--tools`, so no other built-in tool is even available to the session.
ALLOWED_TOOLS = ("Read", "Write")

#: Denied outright, whatever an agent definition says (belt and braces over `--tools`).
DENIED_TOOLS = ("Bash", "WebFetch", "WebSearch", "NotebookEdit")

#: Setting sources the runtime CLI may load. Both resolve against the neutral cwd, which has no
#: `.claude/` directory, so in practice nothing loads: the operator's user-level settings, hooks,
#: permission rules and plugins never reach a runtime agent. (`user` is deliberately absent.)
SETTING_SOURCES = "project,local"

#: File names no runtime agent may read or write, wherever they are (the exam never sees itself
#: being taken). Mirrors gates.HARNESS_ONLY_FILES, which only governs source discovery.
HARNESS_ONLY_NAMES = ("answer_key.json",)

#: Repo directories that are specification, never output. A plain list of access dirs (legacy
#: callers such as demo/run_demo.py) is split with this: these are read-only, the rest writable.
READ_ONLY_REPO_DIRS = tuple(REPO_ROOT / d for d in ("schema", "config", "templates", "glossary", "skills", "fixtures"))

#: Measured stage durations run up to ~580s (render, the longest stage — see run manifests);
#: the original 600s ceiling was a coin flip that cost-audit C1 attempt 2 finally lost on a
#: slightly larger brief. 2× the observed maximum: an infrastructure ceiling, not a gate.
DEFAULT_TIMEOUT_S = 1200

#: Per-stage inference-depth policy (cost-audit C2). Levels the CLI accepts for --effort.
ROUTING_POLICY_PATH = REPO_ROOT / "config" / "model_routing.json"
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")

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


def build_inline_agent(name: str, model_override: Optional[str] = None) -> dict:
    """Turn `.claude/agents/<name>.md` into the `--agents` inline payload {name: {...}}.

    Passing the definition inline is what lets the subagent run from a neutral cwd — the CLI
    never has to discover `.claude/agents/`, so it never has to sit in the repo where CLAUDE.md
    would be auto-loaded. The body is the system prompt verbatim (injected skill and all).

    `model_override` swaps the alias for one call without editing the agent file — used by the
    Tier-4 A/B, which runs the *same* creative-shadow definition on sonnet and on opus. Model
    routing is otherwise a human decision (CLAUDE.md), so this is deliberately explicit.
    """
    path = AGENTS_DIR / f"{name}.md"
    if not path.is_file():
        raise SubagentError(f"no agent definition at {path}")
    fields, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
    spec = {"description": fields.get("description", ""), "prompt": body}
    tools = [t.strip() for t in fields.get("tools", "").split(",") if t.strip()]
    if tools:
        spec["tools"] = tools
    model = model_override or fields.get("model")
    if model:
        spec["model"] = model
    return {name: spec}


class SubagentError(Exception):
    """The subagent could not be run at all (binary missing, timeout, non-JSON output)."""


def _unique(paths) -> tuple:
    seen, out = set(), []
    for p in paths:
        s = str(p)
        if s not in seen:
            seen.add(s)
            out.append(s)
    return tuple(out)


@dataclass(frozen=True)
class AccessScope:
    """What one runtime agent may touch.

    `writable` — directories the agent may write (in practice: the run directory only).
    `read_only` — directories it may read and never write (schema/, templates/, config/).
    `protected` — files or directories INSIDE a writable directory that it must never write:
    staged inputs, human decision records, evidence copies, the audit log. Iterating a scope
    yields every granted directory, so older callers that treat it as a list keep working.
    """

    writable: tuple = ()
    read_only: tuple = ()
    protected: tuple = ()

    def dirs(self) -> list:
        return list(_unique(list(self.writable) + list(self.read_only)))

    def __iter__(self):
        return iter(self.dirs())

    @classmethod
    def coerce(cls, access_dirs) -> "AccessScope":
        """A scope as-is; a plain list split into read-only repo skeleton dirs and the rest."""
        if isinstance(access_dirs, cls):
            return access_dirs
        read_only_roots = [d.resolve() for d in READ_ONLY_REPO_DIRS]
        writable, read_only = [], []
        for directory in access_dirs or ():
            resolved = Path(directory).resolve()
            if any(resolved == r or r in resolved.parents for r in read_only_roots):
                read_only.append(str(directory))
            else:
                writable.append(str(directory))
        return cls(writable=_unique(writable), read_only=_unique(read_only))


def _rule_paths(path, recursive: bool) -> list:
    """Absolute-path permission-rule specifiers (`//abs/path`, gitignore-style) for one path.

    Both the path as given and its resolved form are emitted when they differ (macOS /tmp is a
    symlink to /private/tmp), so a rule cannot be sidestepped by the other spelling.
    """
    forms = _unique([Path(path).absolute(), Path(path).resolve()])
    suffix = "/**" if recursive else ""
    return ["/" + f.rstrip("/") + suffix for f in forms]


def permission_rules(scope: AccessScope) -> tuple:
    """(allow_rules, deny_rules) for one invocation, in Claude Code permission-rule syntax.

    Allow: Read on every granted directory; Write/Edit on the writable ones only.
    Deny (deny always wins): Write/Edit on every read-only directory and every protected
    record, Read/Write/Edit on any harness-only file anywhere, and the shell/web tools.
    """
    allow, deny = [], []
    for directory in scope.dirs():
        allow += [f"Read({p})" for p in _rule_paths(directory, True)]
    for directory in scope.writable:
        for p in _rule_paths(directory, True):
            allow += [f"Write({p})", f"Edit({p})"]
    for directory in scope.read_only:
        for p in _rule_paths(directory, True):
            deny += [f"Write({p})", f"Edit({p})"]
    for record in scope.protected:
        recursive = not Path(record).suffix  # directories are named without an extension
        for p in _rule_paths(record, recursive):
            deny += [f"Write({p})", f"Edit({p})"]
    for name in HARNESS_ONLY_NAMES:
        deny += [f"{tool}(//**/{name})" for tool in ("Read", "Write", "Edit")]
    deny += list(DENIED_TOOLS)
    return list(_unique(allow)), list(_unique(deny))


def build_command(agent: str, prompt: str, access_dirs, model_override: Optional[str] = None) -> list:
    """The exact argv for one runtime invocation — pure, so its security flags are testable.

    `access_dirs` is an AccessScope, or a plain list (split by AccessScope.coerce).
    """
    scope = AccessScope.coerce(access_dirs)
    inline_agents = build_inline_agent(agent, model_override=model_override)
    tools = inline_agents[agent].get("tools") or list(ALLOWED_TOOLS)
    allow, deny = permission_rules(scope)
    cmd = [
        CLAUDE_BIN,
        "-p", prompt,
        "--agents", json.dumps(inline_agents, ensure_ascii=False),
        "--agent", agent,
        "--permission-mode", "acceptEdits",
        # Nobody answers a prompt in a pipeline run: anything not pre-approved is refused
        # outright instead of hanging or being waved through.
        "--permission-prompts", "none",
        # No transcript of the client documents an agent read stays in the operator's CLI
        # profile (docs/pilot/DATA_PROTECTION.md §1, §6).
        "--no-session-persistence",
        # No code-running tool, no settings file of any source, file tools confined to the
        # --add-dir directories (docs/SECURITY.md §3.2). Kept alongside --tools and
        # --setting-sources: each flag states one restriction and is tested on its own.
        "--restricted",
        "--setting-sources", SETTING_SOURCES,
        "--strict-mcp-config",  # no --mcp-config is passed, so no MCP server loads
        "--output-format", "json",
        "--tools", ",".join(tools),
        "--allowedTools", *allow,
        "--disallowedTools", *deny,
    ]
    effort = stage_effort(agent)
    if effort:
        cmd += ["--effort", effort]
    for directory in scope.dirs():
        cmd += ["--add-dir", directory]
    return cmd


def stage_effort(agent: str, path: Optional[Path] = None) -> Optional[str]:
    """The --effort level for one stage, from config/model_routing.json; None = CLI default.

    A missing file means no policy (every stage at default) — that is a valid state, not an
    error. A malformed file or an invalid level fails loudly, mirroring
    `gates.load_readiness_policy`: a silent fallback would let a measured cost number and the
    config that supposedly produced it disagree without anyone noticing.
    """
    p = Path(path) if path else ROUTING_POLICY_PATH
    if not p.is_file():
        return None
    try:
        policy = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SubagentError(f"{p}: not valid JSON — {exc}") from exc
    level = (policy.get("effort") or {}).get(agent)
    if level is None:
        return None
    if level not in EFFORT_LEVELS:
        raise SubagentError(
            f"{p}: effort[{agent!r}] must be one of {list(EFFORT_LEVELS)}, got {level!r}"
        )
    return level


def resolve_cli() -> Optional[str]:
    """Absolute path of the CLI `CLAUDE_BIN` names, or None when it is not on PATH."""
    found = shutil.which(CLAUDE_BIN)
    return os.path.abspath(found) if found else None


def is_replay_cli(path: Optional[str]) -> bool:
    """True when `path` is the offline replay stand-in, which never calls a model."""
    if not path:
        return False
    try:
        return Path(path).resolve() == REPLAY_CLI.resolve()
    except OSError:
        return False


def live_opt_in(explicit: Optional[bool] = None) -> bool:
    """The caller's live opt-in: an explicit flag wins, else `BRIEF_BUILDER_LIVE=1`."""
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(LIVE_ENV, "") == "1"


#: The offline command every live-call refusal points at.
REPLAY_HINT = ('BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" python3 pipeline/runner.py '
               "--project fixtures/northlight_01 --out /tmp/bb-replay")


def live_refusal(explicit: Optional[bool] = None) -> Optional[str]:
    """Why a run must not start (a real CLI without the live opt-in), or None when it may.

    A binary that is not on PATH is not refused here: nothing can be invoked, and `invoke`
    reports the missing CLI when a stage first needs it. The replay binary needs no opt-in.
    """
    found = resolve_cli()
    if found is None or is_replay_cli(found) or live_opt_in(explicit):
        return None
    return (f"live model calls are opt-in: {found} is a real Claude Code CLI, and a run spends "
            f"usage on the operator's account. Pass --live (or set {LIVE_ENV}=1) for an "
            f"owner-authorised live run. To watch the pipeline offline, with zero model calls:\n"
            f"  {REPLAY_HINT}")


def parse_cli_version(text: str) -> Optional[tuple]:
    """(major, minor, patch) from a `claude --version` line, or None when there is none."""
    match = _VERSION_RE.search(text or "")
    return tuple(int(part) for part in match.groups()) if match else None


def cli_version(path: str) -> str:
    """The first line `<path> --version` prints, probed once per process, from the neutral cwd."""
    if path not in _CLI_VERSIONS:
        try:
            proc = subprocess.run([path, "--version"], cwd=_neutral_cwd(), capture_output=True,
                                  text=True, timeout=VERSION_PROBE_TIMEOUT_S, check=False)
        except subprocess.TimeoutExpired as exc:
            raise SubagentError(f"'{path} --version' exceeded {VERSION_PROBE_TIMEOUT_S}s") from exc
        except OSError as exc:
            raise SubagentError(f"could not start {path!r} to read its version: {exc}") from exc
        lines = (proc.stdout or "").strip().splitlines()
        _CLI_VERSIONS[path] = lines[0].strip() if lines else ""
    return _CLI_VERSIONS[path]


def require_supported_cli(path: str) -> str:
    """The CLI's version line; SubagentError when it is unreadable or below MIN_CLI_VERSION."""
    line = cli_version(path)
    version = parse_cli_version(line)
    minimum = ".".join(map(str, MIN_CLI_VERSION))
    if version is None:
        raise SubagentError(f"{path}: cannot read a version from '--version' (got {line!r}); "
                            f"Brief Builder needs Claude Code {minimum} or later")
    if version < MIN_CLI_VERSION:
        raise SubagentError(
            f"{path}: Claude Code {'.'.join(map(str, version))} is older than {minimum}, the release "
            f"the runtime flags (--no-session-persistence, --restricted, --permission-prompts, "
            f"--tools) were checked against. Update the CLI; no stage runs on an older one."
        )
    return line


def cli_record(explicit_live: Optional[bool] = None) -> dict:
    """What a run manifest records about the model transport: binary, version, replay, live.

    Probes `--version` once (no model call). Never raises: a missing or unreadable CLI is
    recorded as such, and `invoke` refuses it when a stage needs it.
    """
    found = resolve_cli()
    replay = is_replay_cli(found)
    record = {
        "binary": Path(found).name if found else CLAUDE_BIN,
        "found": bool(found),
        "replay": replay,
        "live": bool(found) and not replay and live_opt_in(explicit_live),
        "version": None,
        "min_version": ".".join(map(str, MIN_CLI_VERSION)),
    }
    if found:
        try:
            record["version"] = cli_version(found)
        except SubagentError as exc:
            record["version_error"] = str(exc)
    return record


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
    model_override: Optional[str] = None,
) -> SubagentResult:
    """Run one Claude Code subagent non-interactively, on a clean substrate, and report cost.

    `access_dirs` is the agent's AccessScope (or a plain list, see AccessScope.coerce): the run
    directory it may write, the skeleton directories it may only read, and the records inside
    the run directory it may never write. The agent definition is passed
    inline and the process runs from a neutral cwd, so the repo's build-time CLAUDE.md is never
    auto-loaded into a runtime agent (see the module docstring). `model_override` swaps the
    model alias for this one call (the Tier-4 A/B runs the same agent on sonnet and opus).

    Raises SubagentError on infrastructure failure. A subagent that *ran* but produced bad
    output is not this function's problem — the caller validates artifacts against the schema,
    because "the model replied" and "the model was right" are different questions.
    """
    found = resolve_cli()
    if found is None:
        raise SubagentError(
            f"'{CLAUDE_BIN}' not found on PATH. The pipeline drives Claude Code subagents; "
            f"set BRIEF_BUILDER_CLAUDE_BIN if the CLI lives elsewhere."
        )
    # Below MIN_CLI_VERSION nothing runs (probed once per binary, no model call).
    require_supported_cli(found)

    cmd = build_command(agent, prompt, access_dirs, model_override=model_override)
    # Execute exactly what the availability check found, made absolute here: the process starts
    # in a neutral cwd, where a relative BRIEF_BUILDER_CLAUDE_BIN would no longer resolve.
    cmd[0] = found

    try:
        proc = subprocess.run(
            cmd, cwd=_neutral_cwd(), capture_output=True, text=True, timeout=timeout_s, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise SubagentError(f"subagent '{agent}' exceeded {timeout_s}s") from exc
    except OSError as exc:
        raise SubagentError(f"subagent '{agent}': could not start {cmd[0]!r}: {exc}") from exc

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


#: Appended to the token-heavy work orders (extraction, synthesis, render). The deterministic
#: gates read artifacts, never transcripts — every artifact token echoed into the visible reply
#: is spend without a reader. Measured in cost-audit C0: output tokens ran 4–13× artifact size,
#: and serial one-file-per-turn reads inflated the per-turn cache writes.
OUTPUT_DISCIPLINE = """EFFICIENCY — output discipline (the gate reads your FILES, never your prose)
  Read all of your input files in ONE message, as parallel Read calls — never one per turn.
  Compose each artifact directly inside its Write call. Do not draft, quote, or echo artifact
  content in your visible reply or working notes.
  Run your skill's self-check silently and fix problems in the file itself; mention a check in
  your reply only to report a violation you could not fix."""


def repair_order(subject: str, violations: list, instruction: str) -> str:
    """The standard second-attempt prompt: the failures verbatim, then the stage's own coda."""
    listed = "\n".join(f"  - {v}" for v in violations)
    return f"REPAIR ORDER — your {subject} failed the gate:\n{listed}\n\n{instruction}"


def run_gated(
    agent: str,
    order: str,
    check: Callable[[], list],
    repair_prompt: Callable[[list], str],
    access_dirs,
    *,
    stage: str,
    site: str,
    run_dir: Optional[Path] = None,
    model_override: Optional[str] = None,
) -> tuple:
    """Invoke a subagent, gate its artifact, allow exactly one repair round (MAX_ATTEMPTS).

    The single invoke-gate-repair mechanism behind every model stage — extraction, the four
    stages of stages.py and the creative shadow all run through here, so the attempt budget,
    the attempt record shape and the durable diagnostics cannot diverge between them. (The
    creative stage once carried its own copy of this loop and was invisible to
    eval/repair_analysis.py as a result.)

    Each attempt is logged to the durable repair sink before the loop can raise, so a stage
    that gives up still leaves a full record of why (see pipeline/diagnostics.py). `stage` and
    `site` label those records — site distinguishes work within a stage (a source_id, a model
    alias). Returns (attempts, failing_violations); the second is None on success.
    """
    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = invoke(agent, order, access_dirs, model_override=model_override)
        violations = check()
        attempts.append({"attempt": attempt, "subagent": result.as_dict(), "violations": violations})
        if run_dir is not None:
            diagnostics.record_attempt(run_dir, stage, site, attempt, violations, result.as_dict())
        if not violations:
            return attempts, None
        order = repair_prompt(violations)
    return attempts, attempts[-1]["violations"]
