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
