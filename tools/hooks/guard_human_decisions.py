#!/usr/bin/env python3
"""PreToolUse hook: AI coding agents may not run the human-decision commands (owner decision
2026-09-23 #4; docs/SECURITY.md §4).

Wired in the tracked `.claude/settings.json` for the Bash tool, next to `permissions.deny` rules
for the plain spellings. The deny rules match command prefixes; this hook parses the command so
the same commands are refused however they are spelled: `cd … &&` and other compound prefixes,
environment assignments, `env`/`uv run`/`poetry run` wrappers, `bash -c "…"`, `python`/`python3`/
`python3.x`, `-m pipeline.agency` or a path to `pipeline/agency.py`, interpreter flags before the
module, and the subcommand anywhere after it. `python -c` code and stdin/heredoc scripts that call
the decision functions in-process are refused too.

A decision — resolving a conflict, attesting the Greek, triaging a question, excluding a fact,
amending or approving a brief, registering, approving or releasing creative, withdrawing an
approval, purging data — records a named human's judgement. A model typing a name into one of
these commands would forge that judgement. The hook cannot read an agent's mind: a script file
that an agent writes and then runs is not inspected (the audit log, which vouches every decision
record, and separation of duties remain the controls). Humans run these commands in their own
terminal; nothing here affects them. Codex has no equivalent hook yet (docs/SECURITY.md §4).

Protocol: the hook reads the tool call as JSON on stdin; exit 2 with a reason on stderr blocks the
call, exit 0 allows it. `python3 tools/hooks/guard_human_decisions.py --check "<command>"` prints
the verdict for one command string (used by tests).
"""

from __future__ import annotations

import json
import re
import shlex
import sys
from typing import Iterable, List, Optional

#: module → subcommands that record a human decision. `retention purge` is refused unless it is a
#: `--dry-run` (a preview deletes nothing).
DECISION_COMMANDS = {
    "pipeline.agency": {"approve", "attest", "resolve", "apply", "answer", "exclude", "carry-decisions"},
    "pipeline.delivery": {"register", "approve", "release"},
    "pipeline.release_control": {"withdraw"},
    "pipeline.retention": {"purge"},
}
#: Decision functions reachable in-process (python -c, heredocs).
DECISION_FUNCTIONS = ("approve", "attest", "resolve", "apply_candidate", "record", "carry_decisions",
                      "register", "release", "withdraw", "record_regime", "purge")
_CODE_MODULE = re.compile(r"pipeline[./](agency|delivery|release_control|retention|approval|clarifications)\b"
                          r"|from\s+pipeline\s+import\s+[^\n;]*\b(agency|delivery|release_control|retention|approval"
                          r"|clarifications)\b")
_CODE_CALL = re.compile(r"\b(?:agency|delivery|release_control|retention|approval|clarifications)\s*\.\s*"
                        r"(?:" + "|".join(DECISION_FUNCTIONS) + r"|main)\s*\(")
_CODE_VERB = re.compile(r"""['"](?:""" + "|".join(sorted({c for cs in DECISION_COMMANDS.values() for c in cs}))
                        + r""")['"]""")
#: A decision function called through an alias (`import pipeline.delivery as d; d.release(...)`).
_CODE_ALIASED_CALL = re.compile(r"\.\s*(?:" + "|".join(f for f in DECISION_FUNCTIONS if f != "record")
                                + r")\s*\(")
_PYTHON = re.compile(r"^(?:python|pypy)(?:\d+(?:\.\d+)*)?$")
_SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
_WRAPPERS = {"env", "command", "exec", "nohup", "time", "nice", "sudo", "caffeinate", "stdbuf", "timeout",
             "gtimeout", "xargs"}
_RUNNERS = {("uv", "run"), ("poetry", "run"), ("pipenv", "run"), ("pdm", "run"), ("hatch", "run"),
            ("conda", "run")}
#: Interpreter flags that take a separate value.
_PY_VALUE_FLAGS = {"-W", "-X", "-Q"}
_OPERATORS = {"&&", "||", ";", "|", "&", "(", ")", ";;", "|&", "{", "}", "!"}


def _split_commands(command: str) -> List[List[str]]:
    """Simple commands of a shell line, split on operators; quotes respected."""
    lexer = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError:            # unbalanced quotes: fall back to a plain split
        tokens = command.replace("\n", " ; ").split()
    commands, current = [], []
    for token in tokens:
        if token in _OPERATORS or set(token) <= set(";&|()"):
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def _module_of(token: str) -> Optional[str]:
    """The decision module a `-m` name or script path refers to, else None."""
    name = token.strip()
    if name.endswith(".py"):
        match = re.search(r"(?:^|/)pipeline/(agency|delivery|release_control|retention)\.py$", name)
        return f"pipeline.{match.group(1)}" if match else None
    return name if name in DECISION_COMMANDS else None


def _decision_in(module: str, args: List[str]) -> Optional[str]:
    blocked = DECISION_COMMANDS[module]
    for arg in args:
        if arg in blocked:
            if module == "pipeline.retention" and arg == "purge" and "--dry-run" in args:
                return None
            return f"python -m {module} {arg}"
    return None


def _code_decision(code: str) -> Optional[str]:
    """In-process decision calls in Python source handed to the interpreter on the command line."""
    if _CODE_CALL.search(code):
        return "an in-process call of a human-decision function"
    if _CODE_MODULE.search(code) and (_CODE_VERB.search(code) or _CODE_ALIASED_CALL.search(code)):
        return "an in-process human-decision command"
    return None


def _python_decision(args: List[str], whole: str) -> Optional[str]:
    """`args` follow the interpreter name."""
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-m" and i + 1 < len(args):
            module = _module_of(args[i + 1])
            return _decision_in(module, args[i + 2:]) if module else None
        if arg.startswith("-m") and len(arg) > 2:
            module = _module_of(arg[2:])
            return _decision_in(module, args[i + 1:]) if module else None
        if arg == "-c" and i + 1 < len(args):
            return _code_decision(args[i + 1])
        if arg.startswith("-c") and len(arg) > 2:
            return _code_decision(arg[2:])
        if arg in _PY_VALUE_FLAGS:
            i += 2
            continue
        if arg == "-" or arg.startswith("<"):         # script on stdin: a heredoc, `<` or a pipe
            return _code_decision(whole)
        if arg.startswith("-"):
            i += 1
            continue
        module = _module_of(arg)
        return _decision_in(module, args[i + 1:]) if module else None
    return _code_decision(whole)          # interpreter reading stdin (a heredoc or a pipe)


def _strip_prefixes(words: List[str]) -> List[str]:
    while words:
        head = words[0].rsplit("/", 1)[-1]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", words[0]):
            words = words[1:]
        elif head in _WRAPPERS:
            words = words[1:]
            while words and words[0].startswith("-"):      # wrapper options (env -i, nice -n 5 …)
                words = words[2:] if words[0] in ("-n", "-u", "-C", "-S", "-s", "-k") else words[1:]
            if head in ("timeout", "gtimeout") and words:                # timeout [options] DURATION COMMAND
                words = words[1:]
        elif len(words) > 1 and (head, words[1]) in _RUNNERS:
            words = words[2:]
        else:
            break
    return words


def decision_in(command: str, depth: int = 0) -> Optional[str]:
    """What human-decision command `command` would run, or None when it runs none."""
    if depth > 4:
        return "a command nested too deeply to inspect"
    for words in _split_commands(command):
        words = _strip_prefixes(words)
        if not words:
            continue
        program = words[0].rsplit("/", 1)[-1]
        if program in _SHELLS or program == "eval":
            script = None
            if program == "eval":
                script = " ".join(words[1:])
            elif any(w.startswith("-") and not w.startswith("--") and "c" in w[1:] for w in words[1:]):
                index = next(i for i, w in enumerate(words[1:], 1)
                             if w.startswith("-") and not w.startswith("--") and "c" in w[1:])
                script = words[index + 1] if index + 1 < len(words) else ""
            elif len(words) > 1 and not words[1].startswith("-"):
                script = None                       # `bash script.sh`: a file, not inspected
            if script is not None:
                found = decision_in(script, depth + 1)
                if found:
                    return found
            continue
        if _PYTHON.match(program):
            found = _python_decision(words[1:], command)
        else:
            module = _module_of(words[0])
            found = _decision_in(module, words[1:]) if module else None
        if found:
            return found
    return None


def _reason(found: str) -> str:
    return (f"Blocked: {found} records a named human's decision. AI coding agents never run the "
            f"human-decision commands (owner decision 2026-09-23 #4; docs/SECURITY.md §4). Prepare the exact "
            f"command for the person who owns the decision and let them run it in their own terminal. Tests "
            f"exercise these commands in temporary directories through pytest.")


def main(argv: Optional[Iterable[str]] = None) -> int:
    """Hook entry point (JSON on stdin) or `--check COMMAND` for a single verdict."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--check"]:
        found = decision_in(" ".join(argv[1:]))
        print(json.dumps({"blocked": bool(found), "reason": _reason(found) if found else None}))
        return 2 if found else 0
    try:
        payload = json.load(sys.stdin)
    except (ValueError, OSError):
        return 0                                  # not a tool call we understand: never block by accident
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str):
        return 0
    found = decision_in(command)
    if found:
        print(_reason(found), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
