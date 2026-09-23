"""Record I/O shared by every module that keeps JSON records in a run: one load, one atomic write.

Before this module each Tier 5–8 module read records its own way, with different answers to
"what does a corrupt record mean": revisions raised, retention silently used a default (so a
purge inventory could under-report copies), effort raised, the review pages skipped. Now:

* `load_optional(path, default)` — a missing record is the default; a record that exists but
  does not parse raises `CorruptRecordError`, naming the file. Never a silent default.
* `load_strict(path)` — the record must exist (FileNotFoundError otherwise) and parse.
* `atomic_write_text` / `write_json` — write to a temporary file in the same directory, fsync,
  then `os.replace`, so a reader sees the old record or the new one, never half of one.

A caller that deliberately degrades (a best-effort review page) catches `CorruptRecordError`
at its own boundary and says so there.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Union
from uuid import uuid4

PathLike = Union[str, Path]


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


def atomic_write_text(path: PathLike, text: str) -> None:
    """Replace `path` with `text` atomically (same-directory temp file, fsync, os.replace).

    The temporary file is created like any other file (umask permissions) and is removed when
    the write or the replace fails, so a failed write leaves the old record and no debris.
    """
    path = Path(path)
    temporary = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def write_json(path: PathLike, value: Any) -> None:
    """Write `value` as indented UTF-8 JSON with a trailing newline, atomically; creates parent folders."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")
