"""One clock for every timestamp the pipeline writes: timezone-aware UTC, injectable for tests.

Before this module the run manifest (`started_ts`, `finished_ts`), the run id and the synthesis
and extraction work orders used naive local time while the audit log, approvals, effort ledger
and retention tombstones used UTC, so one run carried two time bases. Every writer now asks
this module. Tests freeze it with `frozen(...)` instead of patching `datetime` per module.

Calendar dates people type and compare (a data-declaration approval date, a client-pack review
date, a catalog's review due date) stay local `date.today()` comparisons with an injectable
`today=`: they are human dates, not event timestamps.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Optional

#: The injected time source, or None for the system clock. Set only through `set_clock`/`frozen`.
_source: Optional[Callable[[], datetime]] = None


def now() -> datetime:
    """The current time as an aware UTC datetime (the injected source's, when one is set)."""
    if _source is None:
        return datetime.now(timezone.utc)
    value = _source()
    if value.tzinfo is None:
        raise ValueError("clock: an injected time source must return an aware datetime")
    return value.astimezone(timezone.utc)


def timestamp(timespec: str = "auto") -> str:
    """ISO-8601 UTC timestamp with offset (`2026-09-23T10:00:00+00:00` for timespec='seconds')."""
    return now().isoformat(timespec=timespec)


def compact(fmt: str) -> str:
    """The current UTC time through `strftime(fmt)` — run ids and archive folder names."""
    return now().strftime(fmt)


def set_clock(source: Optional[Callable[[], datetime]]) -> Optional[Callable[[], datetime]]:
    """Install a time source (None restores the system clock); returns the previous one."""
    global _source
    previous, _source = _source, source
    return previous


@contextmanager
def frozen(when: datetime) -> Iterator[datetime]:
    """Within the block every timestamp the pipeline writes is `when` (must be aware)."""
    if when.tzinfo is None:
        raise ValueError("clock.frozen needs an aware datetime")
    previous = set_clock(lambda: when)
    try:
        yield when.astimezone(timezone.utc)
    finally:
        set_clock(previous)
