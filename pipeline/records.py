"""Record I/O shared by every module that keeps JSON records in a run: one load, one atomic write.

Before this module each Tier 5–8 module read records its own way, with different answers to
"what does a corrupt record mean": revisions raised, retention silently used a default (so a
purge inventory could under-report copies), effort raised, the review pages skipped. Now:

* `load_optional(path, default)` — a missing record is the default; a record that exists but
  does not parse raises `CorruptRecordError`, naming the file. Never a silent default.
* `load_strict(path)` — the record must exist (FileNotFoundError otherwise) and parse.
* `atomic_write_text` / `write_json` — write to a temporary file in the same directory, fsync,
  then `os.replace`, so a reader sees the old record or the new one, never half of one.
* Records that name agency staff (`PERSONAL_RECORDS`: approvals, reviews, decisions, effort,
  the audit log) are written owner-only (0600), whoever writes them; `append_text` does the
  same for append-only logs. Any other file keeps the process umask.

A caller that deliberately degrades (a best-effort review page) catches `CorruptRecordError`
at its own boundary and says so there.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional, Union
from uuid import uuid4

PathLike = Union[str, Path]

#: Governance and effort records: personal data about agency staff (names, minutes, decisions).
#: Retention inventories them (pipeline/retention.py) and every write keeps them owner-only.
PERSONAL_RECORDS = ("approval.json", "language_review.json", "creative_draft.json", "creative_approval.json",
                    "amendments.json", "clarifications.json", "coverage_decisions.json", "releases.json",
                    "approval_withdrawals.json", "effort.json", "agency_inputs.json", "revision_lineage.json",
                    "audit_log.jsonl")

#: Owner read/write only: the mode of every personal record.
PRIVATE_MODE = 0o600


class CorruptRecordError(ValueError):
    """A record file exists but is not valid UTF-8 JSON. A ValueError, like every Tier 5–8 refusal."""

    def __init__(self, path: PathLike, reason: str):
        self.path = Path(path)
        super().__init__(f"{self.path}: corrupt record, not valid JSON ({reason}). "
                         f"Inspect or restore it; it is never read as empty.")


def _parse(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CorruptRecordError(path, str(exc)) from exc


def load_strict(path: PathLike) -> Any:
    """Parse a record that must exist: FileNotFoundError when absent, CorruptRecordError when unparseable."""
    return _parse(Path(path))


def load_optional(path: PathLike, default: Any = None) -> Any:
    """Parse a record that may be absent (then `default`); CorruptRecordError when it exists but is unparseable."""
    path = Path(path)
    if not path.exists():
        return default
    return _parse(path)


def is_personal(path: PathLike) -> bool:
    """True when the file name is one of the staff-data records in PERSONAL_RECORDS."""
    return Path(path).name in PERSONAL_RECORDS


def atomic_write_text(path: PathLike, text: str, *, private: Optional[bool] = None) -> None:
    """Replace `path` with `text` atomically (same-directory temp file, fsync, os.replace).

    `private=None` decides by name (`is_personal`); a private record is created owner-only
    (0600) and keeps that mode through the replace. Other files get the umask permissions. The
    temporary file is removed when the write or the replace fails, so a failed write leaves the
    old record and no debris.
    """
    path = Path(path)
    if private is None:
        private = is_personal(path)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, PRIVATE_MODE if private else 0o666)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def append_text(path: PathLike, text: str, *, private: Optional[bool] = None) -> None:
    """Append `text` to a log file, creating it if needed; a private log is (and stays) owner-only."""
    path = Path(path)
    if private is None:
        private = is_personal(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, PRIVATE_MODE if private else 0o666)
    with os.fdopen(fd, "a", encoding="utf-8") as handle:
        if private:
            os.fchmod(handle.fileno(), PRIVATE_MODE)  # tighten a log created before this rule
        handle.write(text)


def write_json(path: PathLike, value: Any, *, private: Optional[bool] = None) -> None:
    """Write `value` as indented UTF-8 JSON with a trailing newline, atomically; creates parent folders."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n", private=private)
