"""Durable per-attempt violation log — written as it happens, survives any later failure.

Two data-loss incidents motivated this file. The run manifest is written once at the end, so
(a) a resume that rewrites it truncates the history, and (b) a stage that raises mid-run never
records the attempts it already made — and a failing run is exactly the one whose violations you
want to read. This sink is append-only JSONL, one line per gated attempt, flushed immediately.
It is diagnostics, never a gate: nothing in the pipeline reads it back to make a decision.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

REPAIR_LOG = "diagnostics/repair_log.jsonl"


def record_attempt(run_dir: Path, stage: str, site: str, attempt: int, violations: list,
                   subagent: Optional[dict] = None) -> None:
    """Append one attempt's outcome. Best-effort: a diagnostics write must never break a run."""
    try:
        path = Path(run_dir) / REPAIR_LOG
        path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "stage": stage,
            "site": site,
            "attempt": attempt,
            "violation_count": len(violations),
            "violations": violations,
            "model_ids": (subagent or {}).get("model_ids") or [],
            "cost_usd": (subagent or {}).get("cost_usd"),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        pass  # a lost diagnostic line is acceptable; a broken run is not


def load_repair_log(run_dir: Path) -> list:
    """Read a run's repair log, or [] if none. Tolerates a truncated final line."""
    path = Path(run_dir) / REPAIR_LOG
    if not path.is_file():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
