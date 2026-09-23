"""What every model stage shares: its two outcomes besides success, and the failure message."""

from __future__ import annotations

from pipeline import agents, gates


class StageError(gates.GateError):
    """A stage did not produce an acceptable artifact."""


class HaltForHuman(gates.GateError):
    """The pipeline stopped and asked, rather than guessing (DR-9, TRANSCRIPTS.md §4).

    Distinct from StageError on purpose: this is the system working as designed, and the run
    manifest should not read as if something broke.
    """


def stage_failure(agent: str, violations: list) -> StageError:
    """The StageError for a stage whose repair loop ran out of attempts, listing what still fails."""
    listed = "\n".join(f"  - {v}" for v in violations)
    return StageError(f"{agent}: no acceptable artifact after {agents.MAX_ATTEMPTS} attempts:\n{listed}")


#: Opens every gate-repair order (the replay stand-in, pipeline/replay.py, recognises one by it).
REPAIR_HEADER = "REPAIR ORDER"


def restating_repair_order(subject: str, violations: list, instruction: str, work_order: str) -> str:
    """A second-attempt prompt that stands on its own in a fresh session.

    Every attempt is a new `claude -p` session: the model has never seen the first order, so a
    repair order that says "rewrite the same file" or "check the source of your first order"
    hands it a task without its inputs (r1 review: 14/24 extraction repairs succeeded, several
    second attempts wrote nothing). This order therefore carries the gate's violations, the
    stage's own coda, and then the ORIGINAL work order restated verbatim — every input path,
    read rule and output path it named still holds.
    """
    listed = "\n".join(f"  - {v}" for v in violations)
    return f"""{REPAIR_HEADER} — your {subject} failed the runner's gate.

This is a fresh session: you have not seen the earlier attempt or the order it ran under, so
that work order is restated in full below. Every input path, read rule and output path in it
still holds. The earlier attempt's output, where one was written, is still at the output
path(s) the order names; you may read those output files in addition to the order's inputs.

Violations (from the deterministic gate, not from a model):
{listed}

{instruction}

===== ORIGINAL WORK ORDER (restated verbatim; it governs this attempt) =====
{work_order.rstrip()}
===== END ORIGINAL WORK ORDER =====
"""
