"""Content-bound review and safe reuse; no model calls or implicit human decisions.

A leaf utility of the Tier 5–8 layer: hashing, input snapshots, evidence copies, run locks,
archives and the hash-chained audit log. It imports no policy module. The approval policy
(`require_current_approval`) lives in `pipeline.approval`, and decision carry-forward
(`carry_decisions`) in `pipeline.clarifications`; both names still resolve here, lazily, for
existing callers. Record I/O is `pipeline.records`, timestamps are `pipeline.clock`.
"""
from __future__ import annotations

import fcntl
import hashlib
import importlib
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Union
from uuid import uuid4

from pipeline import clock, records

#: The per-run advisory lock file. Its absence means no locked operation ever mutated the run.
RUN_LOCK_FILE = ".run.lock"

PathLike = Union[str, Path]

#: Record I/O, re-exported under the names every Tier 5–8 module already uses.
write_json = records.write_json
load = records.load_optional
CorruptRecordError = records.CorruptRecordError

#: Names that moved out of this module; resolved lazily so this module imports no policy.
_MOVED = {"require_current_approval": "pipeline.approval", "carry_decisions": "pipeline.clarifications"}


def __getattr__(name: str) -> Any:
    """Compatibility: `revisions.require_current_approval` / `revisions.carry_decisions` still resolve."""
    if name in _MOVED:
        return getattr(importlib.import_module(_MOVED[name]), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


class RunBusyError(ValueError):
    """Another cooperating process holds the run lock. The one error `run_lock` raises itself.

    A ValueError subclass so every existing caller that handles ValueError keeps working;
    callers that must tell contention apart from a bad artifact catch this class only.
    """


def digest(value: Any) -> str:
    """SHA-256 of the canonical (sorted-key) JSON encoding of `value`."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def timestamp() -> str:
    """UTC ISO-8601 timestamp for decision records (`pipeline.clock`)."""
    return clock.timestamp()


def file_hash(path: PathLike) -> str:
    """SHA-256 of a file's bytes."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_state(paths: Mapping[str, PathLike]) -> dict:
    """{key: {path, sha256}} for every input file, sorted by key — the run's input snapshot."""
    return {key: {"path": str(Path(path).resolve()), "sha256": file_hash(path)}
            for key, path in sorted(paths.items())}


def verify_inputs(run_dir: PathLike) -> None:
    """Raise ValueError when any input recorded in the run's snapshot changed or the source set did."""
    state = load(Path(run_dir) / "input_snapshot.json", {})
    recorded_sources = {Path(item["path"]).resolve() for key, item in state.items() if key.startswith("source:")}
    for directory in {p.parent for p in recorded_sources}:
        current_sources = {p.resolve() for p in directory.glob("*.md") if p.is_file()}
        if current_sources != {p for p in recorded_sources if p.parent == directory}:
            raise ValueError("The source document set changed; use a new run with all current sources.")
    for key, item in state.items():
        if not Path(item["path"]).is_file() or file_hash(item["path"]) != item["sha256"]:
            raise ValueError(f"Input {key} changed; use a new run with current sources.")


def fingerprint(run_dir: PathLike) -> str:
    """Digest of the files a human approval is bound to (brief, renders, inputs, decisions, extracts)."""
    run_dir = Path(run_dir)
    names = ["brief.json", "brief_el.md", "brief_en.md", "input_snapshot.json",
             "agency_inputs.json", "clarifications.json", "coverage_decisions.json", "evidence_index.json"]
    files = [run_dir / n for n in names] + sorted((run_dir / "extracts").glob("*.json"))
    return digest({str(p.relative_to(run_dir)): file_hash(p) for p in files if p.is_file()})


def archive(run_dir: PathLike, names: list, copy_only: bool = False) -> None:
    """Move (or copy) the named run artifacts into a fresh `history/<UTC stamp>-<id>/` folder."""
    run_dir = Path(run_dir)
    files = [run_dir / n for n in names if (run_dir / n).exists()]
    if not files:
        return
    target = run_dir / "history" / (clock.compact("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8])
    target.mkdir(parents=True)
    for path in files:
        if copy_only:
            if path.is_dir():
                shutil.copytree(path, target / path.name)
            else:
                shutil.copy2(path, target / path.name)
        else:
            shutil.move(str(path), str(target / path.name))


def prepare_run(run_dir: PathLike, paths: Mapping[str, PathLike], stage: str,
                require_approval: Optional[Callable[[Path], None]] = None) -> None:
    """Refuse changed-input reuse. Archive invalidated products before a leg rerun.

    Legacy runs without a snapshot remain usable for the original demo; they cannot
    receive agency approval until initialized and explicitly reviewed. The creative stage of
    an agency-managed run needs `require_approval` (the policy check this utility does not
    own); without it the call refuses — use `pipeline.approval.prepare_run`, which binds it.
    """
    run_dir = Path(run_dir)
    state = input_state(paths)
    previous = load(run_dir / "input_snapshot.json")
    if previous is not None:
        verify_inputs(run_dir)
    if previous is not None and (any(previous.get(k) != v for k, v in state.items())
            or {k for k in previous if k.startswith("source:")} != {k for k in state if k.startswith("source:")}):
        raise ValueError("Inputs/configuration changed; create a new run instead of reusing stale artifacts.")
    # A legacy artifact was not necessarily made from today's inputs: never backfill proof.
    if previous is None and not (run_dir / "brief.json").exists() and not (run_dir / "extracts").exists():
        write_json(run_dir / "input_snapshot.json", state)
    capture_evidence(run_dir, paths)
    if stage == "creative":
        if (run_dir / "agency_inputs.json").exists():
            if require_approval is None:
                raise ValueError("The creative stage of an agency-managed run needs the approval "
                                 "check; call pipeline.approval.prepare_run")
            require_approval(run_dir)
        return
    downstream = ["approval.json", "language_review.json", "agency_audit.json", "creative_approval.json", "creative_draft.json", "creative", "brief_review.html", "run_review.html",
                  "brief_el.html", "brief_en.html", "brief_el.md", "brief_en.md"]
    if stage in ("synthesis", "extraction", "full"):
        downstream += ["brief.json", "conflict_candidates.json"]
    if stage == "extraction":
        # Keep unaffected source extracts for --source resumes, but preserve every
        # original before the extractor can overwrite its selected output path.
        archive(run_dir, ["extracts", "fidelity"], copy_only=True)
    if stage == "full":
        downstream += ["classification.json", "extracts", "fidelity"]
    archive(run_dir, downstream)


def changes(before: dict, after: dict) -> dict:
    """Field-level content comparison, useful before approving a changed brief."""
    return {key: {"before": before.get(key), "after": after.get(key)}
            for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)}


@contextmanager
def run_lock(run_dir: Union[str, Path]) -> Iterator[None]:
    """One cooperating process may mutate a run at a time; OS releases on crash.

    Exclusive and fail-fast: raises RunBusyError, never blocks. Creates the run directory and
    its lock file, so use it only for operations that write. Read-only views use `read_lock`.
    """
    run_dir = Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / RUN_LOCK_FILE).open('a+') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunBusyError('Run is busy in another operation; retry after it finishes') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


@contextmanager
def read_lock(run_dir: Union[str, Path]) -> Iterator[None]:
    """Consistent read of a run that never creates anything in it.

    Status and portfolio views read committed evidence folders (runs/tier3, …) that must stay
    byte-identical, so this never creates a directory or a lock file. When the lock file
    exists, a shared non-blocking lock excludes a concurrent writer (RunBusyError, like
    `run_lock`). When it does not, no locked writer has ever touched the run; if one starts
    while the read is in progress, the lock file appears and the read is refused as busy
    instead of returning a possibly half-updated view.
    """
    run_dir = Path(run_dir)
    lock_path = run_dir / RUN_LOCK_FILE
    if not lock_path.is_file():
        yield
        if lock_path.exists():
            raise RunBusyError('Run changed during a read-only check; retry after it finishes')
        return
    with lock_path.open('r') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunBusyError('Run is busy in another operation; retry after it finishes') from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def capture_evidence(run_dir: PathLike, paths: Mapping[str, PathLike]) -> None:
    """Keep hash-named copies. Capturing is not an assertion of model provenance."""
    run_dir = Path(run_dir)
    state = load(run_dir / 'evidence_index.json', {})
    for key, original in sorted(paths.items()):
        original = Path(original)
        if original.name == 'answer_key.json':
            raise ValueError('Answer keys are never evidence inputs')
        data = original.read_bytes()
        hashed = hashlib.sha256(data).hexdigest()
        relative = Path('evidence') / (hashed + original.suffix)
        target = run_dir / relative
        target.parent.mkdir(exist_ok=True)
        if target.exists():
            if target.read_bytes() != data:
                raise ValueError('Stored evidence copy failed integrity verification')
        else:
            with target.open('xb') as handle:
                handle.write(data)
        state[key] = {'file': str(relative), 'sha256': hashed, 'original': str(original.resolve())}
    write_json(run_dir / 'evidence_index.json', state)


def verify_evidence(run_dir: PathLike) -> None:
    """Raise ValueError when a preserved evidence copy is missing, outside the run or modified."""
    run_dir = Path(run_dir).resolve()
    for key, item in load(run_dir / 'evidence_index.json', {}).items():
        path = (run_dir / item['file']).resolve()
        if run_dir not in path.parents or not path.is_file() or file_hash(path) != item['sha256']:
            raise ValueError(f'Preserved evidence {key} is missing, outside run or modified')


# --------------------------------------------------------------------------------------
# Append-only, hash-chained audit log of human decisions (docs/SECURITY.md)
# --------------------------------------------------------------------------------------

AUDIT_LOG = "audit_log.jsonl"
GENESIS_SHA256 = "0" * 64

#: Records a human decision leaves behind, and the log event that must vouch for each one.
#: `verify_audit_log` cross-checks them, so deleting the tail of the log (which a chain alone
#: cannot see) is caught while the record it explained still exists.
_VOUCHED_RECORDS = {"approval.json": "brief_approved", "creative_approval.json": "creative_approved"}
_VOUCHED_LISTS = {"amendments.json": "brief_amended", "approval_withdrawals.json": "approval_withdrawn",
                  "releases.json": "creative_released"}


def _line_hash(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def append_audit(run_dir: PathLike, event: str, actor: str, record: Any = None,
                 details: Optional[dict] = None) -> dict:
    """Append one decision to <run>/audit_log.jsonl, chained to the previous line's SHA-256.

    `record` names the file the decision wrote (hashed as written), or a list entry appended
    to one (`{"file": name, "entry": value}`, hashed with `digest`). The log is local
    tamper-EVIDENCE for a cooperating team, not identity: actors are the names people typed.
    Callers hold the run lock, so appends are serialised.
    """
    run_dir = Path(run_dir)
    if not isinstance(actor, str) or not actor.strip():
        raise ValueError("An audit entry needs a named human actor")
    path = run_dir / AUDIT_LOG
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    entry = {"seq": len(lines) + 1, "at": timestamp(), "event": event, "actor": actor,
             "prev_sha256": _line_hash(lines[-1]) if lines else GENESIS_SHA256}
    if isinstance(record, dict):
        entry["record"] = record["file"]
        entry["entry_sha256"] = digest(record["entry"])
    elif record is not None:
        entry["record"] = str(record)
        entry["record_sha256"] = file_hash(run_dir / record)
    if details:
        entry["details"] = details
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def read_audit_log(run_dir: PathLike) -> list:
    """Every entry of the run's audit log, in order ([] when there is none)."""
    path = Path(run_dir) / AUDIT_LOG
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def verify_audit_log(run_dir: PathLike) -> list:
    """Every reason the audit trail cannot be trusted as written; [] when it is intact.

    Detects an edited, inserted, reordered or deleted line (chain or sequence break), and a
    decision record no log entry vouches for: a current approval.json or creative_approval.json
    whose exact bytes were never logged, or an amendment, withdrawal or release receipt with no
    matching entry (a truncated log, or a record written around the commands). It does not
    authenticate who typed a name.
    """
    run_dir = Path(run_dir)
    path = run_dir / AUDIT_LOG
    problems, entries = [], []
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    previous = GENESIS_SHA256
    for number, line in enumerate(lines, 1):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            problems.append(f"audit log line {number} is not valid JSON")
            previous = _line_hash(line)
            continue
        if not isinstance(entry, dict):
            problems.append(f"audit log line {number} is not an entry object")
            previous = _line_hash(line)
            continue
        if entry.get("seq") != number:
            problems.append(f"audit log line {number}: sequence {entry.get('seq')!r} — a line was "
                            f"removed, inserted or reordered")
        if entry.get("prev_sha256") != previous:
            problems.append(f"audit log line {number}: previous-entry hash does not match — an "
                            f"earlier line was edited or removed")
        previous = _line_hash(line)
        entries.append(entry)
    for name, event in _VOUCHED_RECORDS.items():
        if (run_dir / name).is_file():
            sha = file_hash(run_dir / name)
            if not any(e.get("event") == event and e.get("record_sha256") == sha for e in entries):
                problems.append(f"{name} is not vouched for by any '{event}' audit entry — written "
                                f"outside the commands, or the log was truncated")
    for name, event in _VOUCHED_LISTS.items():
        logged = {e.get("entry_sha256") for e in entries if e.get("event") == event}
        items = load(run_dir / name, [])
        for index, item in enumerate(items if isinstance(items, list) else []):
            if digest(item) not in logged:
                problems.append(f"{name}[{index}] has no matching '{event}' audit entry")
    return problems


def require_intact_audit_log(run_dir: PathLike) -> None:
    """Raise ValueError (the Tier 5–7 refusal type) when `verify_audit_log` finds anything."""
    problems = verify_audit_log(run_dir)
    if problems:
        raise ValueError("Audit log check failed: " + "; ".join(problems))
