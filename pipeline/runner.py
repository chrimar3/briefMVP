"""Step sequencer for the Brief Builder pipeline (PRD §5).

The runner owns *sequence and refusal*; the subagents own judgment. Every step is
declared below with the kind of thing it is — `deterministic` steps execute here,
`model` steps dispatch to a Claude Code subagent through `AGENT_HANDLERS`.

Tier 0 ships the sequence and the deterministic half. No model handler is registered
yet, so a run executes the readiness gate, records the sequence, writes a manifest, and
stops at the first unimplemented stage with exit code EXIT_PENDING_STAGE. That is the
honest state of the scaffold: it does not pretend to have drafted anything.

Usage:
    python pipeline/runner.py --project fixtures/northlight_01
    python pipeline/runner.py --project fixtures/northlight_01 --out /tmp/runs
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

if __package__ in (None, ""):  # allow `python pipeline/runner.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import PIPELINE_VERSION
from pipeline import gates

EXIT_OK = 0
EXIT_INSUFFICIENT_INPUT = 2
EXIT_PENDING_STAGE = 3
EXIT_GATE_ERROR = 4

DETERMINISTIC = "deterministic"
MODEL = "model"


@dataclass(frozen=True)
class Step:
    number: int
    name: str
    kind: str
    agent: Optional[str]
    description: str


#: PRD §5, verbatim in sequence. Human sign-off (step 8) is deliberately absent from the
#: runner: it is not a step the system executes, it is the gate the system stops at.
STEP_SEQUENCE = (
    Step(1, "readiness_gate", DETERMINISTIC, None, "Refuse to draft on insufficient input"),
    Step(2, "classification", MODEL, "classify", "Project type + onboarding sensitivity tier"),
    Step(3, "fidelity_check", MODEL, "fidelity-check", "Transcript fidelity gate + annotation"),
    Step(4, "extraction", MODEL, "extract", "Per-source citation-bearing extracts"),
    Step(5, "conflict_pass", DETERMINISTIC, None, "Cross-source contradictions — surfaced, never resolved"),
    Step(6, "synthesis", MODEL, "synthesize", "Assemble the canonical brief object"),
    Step(7, "render", MODEL, "render", "GR + EN documents from the same object"),
)

#: Model-step handlers, registered per tier as each stage is built.
#: Signature: handler(ctx: RunContext, step: Step) -> dict  (the step's manifest payload)
AGENT_HANDLERS: dict[str, Callable[["RunContext", Step], dict]] = {}


@dataclass
class RunContext:
    """Everything a step needs, and the run directory everything is written to."""

    project_dir: Path
    run_dir: Path
    run_id: str
    sources: list
    started_ts: str


class Runner:
    def __init__(self, project_dir: Path, out_dir: Path, run_id: Optional[str] = None):
        self.project_dir = Path(project_dir).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = self.out_dir / self.run_id
        self.steps: list[dict] = []

    # -- plumbing ----------------------------------------------------------------

    def _record(self, step: Step, status: str, **payload) -> dict:
        entry = {**asdict(step), "status": status, **payload}
        self.steps.append(entry)
        return entry

    def _write_manifest(self, outcome: str, exit_code: int) -> Path:
        manifest = {
            "run_id": self.run_id,
            "pipeline_version": PIPELINE_VERSION,
            "project_dir": str(self.project_dir),
            "started_ts": self.started_ts,
            "finished_ts": datetime.now().isoformat(timespec="seconds"),
            "outcome": outcome,
            "exit_code": exit_code,
            "sources": [s.as_meta() for s in self.sources],
            "steps": self.steps,
        }
        path = self.run_dir / "run_manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _update_latest_symlink(self) -> None:
        """`runs/latest` — what `eval/harness.py runs/latest` grades."""
        link = self.out_dir / "latest"
        try:
            if link.is_symlink() or link.exists():
                link.unlink()
            link.symlink_to(self.run_dir.name)
        except OSError as exc:  # pragma: no cover - filesystem-dependent
            print(f"  ! could not update {link}: {exc}", file=sys.stderr)

    # -- the sequence ------------------------------------------------------------

    def run(self) -> int:
        self.started_ts = datetime.now().isoformat(timespec="seconds")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        print(f"Brief Builder {PIPELINE_VERSION} · run {self.run_id}")
        print(f"  input : {self.project_dir}")
        print(f"  output: {self.run_dir}\n")

        try:
            self.sources = gates.discover_sources(self.project_dir)
        except gates.InputContractError as exc:
            self.sources = []
            print(f"[input contract] {exc}", file=sys.stderr)
            self._write_manifest("input_contract_error", EXIT_GATE_ERROR)
            return EXIT_GATE_ERROR

        for s in self.sources:
            print(f"  · {s.source_id} ({s.source_type}, {s.source_date})")
        print()

        ctx = RunContext(
            project_dir=self.project_dir,
            run_dir=self.run_dir,
            run_id=self.run_id,
            sources=self.sources,
            started_ts=self.started_ts,
        )

        for step in STEP_SEQUENCE:
            outcome, exit_code = self._execute(ctx, step)
            if outcome is not None:
                self._write_manifest(outcome, exit_code)
                self._update_latest_symlink()
                return exit_code

        self._write_manifest("complete", EXIT_OK)
        self._update_latest_symlink()
        return EXIT_OK

    def _execute(self, ctx: RunContext, step: Step) -> tuple[Optional[str], int]:
        """Run one step. Returns (terminal_outcome, exit_code); (None, 0) to continue."""
        label = f"[{step.number}] {step.name}"

        if step.name == "readiness_gate":
            verdict = gates.readiness_gate(ctx.sources)
            self._record(step, "pass" if verdict.ok else "refused", verdict=verdict.as_dict())
            print(f"{label}: {verdict.message}")
            if not verdict.ok:
                return "insufficient_input", EXIT_INSUFFICIENT_INPUT
            return None, EXIT_OK

        if step.name == "conflict_pass":
            # Deterministic cross-source pass, built in Tier 2. It reads the extracts
            # produced by step 4, so it cannot run before that stage exists.
            self._record(step, "pending", pending_since_tier=2)
            print(f"{label}: not implemented until Tier 2 — stopping.")
            return "pending_stage", EXIT_PENDING_STAGE

        handler = AGENT_HANDLERS.get(step.agent or "")
        if handler is None:
            self._record(step, "pending", agent=step.agent, pending_reason="no handler registered")
            print(f"{label}: subagent '{step.agent}' has no handler yet — stopping.")
            return "pending_stage", EXIT_PENDING_STAGE

        payload = handler(ctx, step)
        self._record(step, "pass", **payload)
        print(f"{label}: ok")
        return None, EXIT_OK


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Brief Builder Stage-1 pipeline.")
    parser.add_argument("--project", required=True, help="Input folder (any folder honouring the source-header contract)")
    parser.add_argument("--out", default=str(gates.REPO_ROOT / "runs"), help="Where run directories are written")
    parser.add_argument("--run-id", default=None, help="Override the timestamp run id (tests, reruns)")
    args = parser.parse_args(argv)

    try:
        return Runner(Path(args.project), Path(args.out), args.run_id).run()
    except gates.GateError as exc:
        print(f"[gate] {exc}", file=sys.stderr)
        return EXIT_GATE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
