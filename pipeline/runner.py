"""Step sequencer for the Brief Builder pipeline (PRD §5).

The runner owns *sequence and refusal*; the subagents own judgment. Every step is
declared below with the kind of thing it is — `deterministic` steps execute here,
`model` steps dispatch to a Claude Code subagent through `AGENT_HANDLERS`.

All seven Stage-1 steps are built. A run either completes, refuses (insufficient input),
halts for a human (low classification confidence, or a transcript the fidelity gate will not
vouch for), or fails a gate — and the exit code says which. Human sign-off is PRD step 8 and
deliberately absent: it is not a step the system executes, it is the gate it stops at.

Usage:
    python pipeline/runner.py --project fixtures/northlight_01
    python pipeline/runner.py --project fixtures/northlight_01 --stage extraction
    python pipeline/runner.py --project fixtures/northlight_01 --out /tmp/runs
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

if __package__ in (None, ""):  # allow `python pipeline/runner.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import PIPELINE_VERSION
from pipeline import agents, conflicts, creative, docview, extraction, gates, publish, review, run_review, stages

EXIT_OK = 0
EXIT_INSUFFICIENT_INPUT = 2
EXIT_PENDING_STAGE = 3
EXIT_GATE_ERROR = 4
EXIT_HALTED_FOR_HUMAN = 5

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
    # Step 8 (PRD §5) is human sign-off — not a runner step. Step 9 is Stage 2, and it runs
    # ONLY on a signed-off brief, never as part of the default Stage-1 flow (DR-8).
    Step(9, "creative_shadow", MODEL, "creative-shadow", "Shadow creative brief A/B (sonnet vs opus)"),
)

#: Which steps each stage selection runs. `extraction` is the Tier-1 path: prove the
#: extraction leg end-to-end without pretending the stages around it exist yet.
STAGE_SELECTIONS = {
    "full": ("readiness_gate", "classification", "fidelity_check", "extraction", "conflict_pass", "synthesis", "render"),
    "extraction": ("readiness_gate", "extraction"),
    # Re-run one leg against an existing run directory (`--run-id <existing>`). A run dir is
    # resumable state: re-rendering a brief should not mean re-extracting four sources.
    "synthesis": ("conflict_pass", "synthesis", "render"),
    "render": ("render",),
    # Stage 2. Deliberately its own selection — never bundled into "full", because it requires
    # the human sign-off that stands between the stages (DR-8).
    "creative": ("creative_shadow",),
}


#: What each step needs already in hand. A resumed leg whose inputs are not on disk must say
#: so plainly — the first version raised a bare `KeyError: 'brief'` from inside a handler,
#: which tells an account lead nothing about what to do next.
STEP_PREREQUISITES = {
    "conflict_pass": ("extracts",),
    "synthesis": ("classification", "extracts"),
    "render": ("brief",),
    "creative_shadow": ("brief",),
}

ARTIFACT_FILES = {
    "classification": "classification.json",
    "extracts": "extracts/*.json",
    "brief": "brief.json",
}


@dataclass
class RunContext:
    """Everything a step needs, and the run directory everything is written to."""

    project_dir: Path
    run_dir: Path
    run_id: str
    sources: list
    started_ts: str
    project_id: str = ""
    client_config: dict = None
    artifacts: dict = field(default_factory=dict)
    glossary_path: Optional[Path] = None
    source_filter: Optional[str] = None
    #: Demo-profile readiness policy (loaded dict) — None in every production run. When set,
    #: the input readiness gate's refusal is printed and recorded but does not stop the run,
    #: and the draft readiness block is computed with this policy instead of the shipped one.
    readiness_policy: Optional[dict] = None

    def selected_sources(self) -> list:
        """Sources this run acts on — all of them, or the one named by --source."""
        if not self.source_filter:
            return list(self.sources)
        chosen = [s for s in self.sources if s.source_id == self.source_filter]
        if not chosen:
            available = ", ".join(s.source_id for s in self.sources)
            raise gates.InputContractError(
                f"--source {self.source_filter!r} not in this project. Available: {available}"
            )
        return chosen


def _access_dirs(ctx: "RunContext") -> list:
    """The only directories a subagent may touch: project sources, run output, and the three
    read-only skeleton dirs. Deliberately NOT the repo root — that is where CLAUDE.md lives,
    and a runtime agent has no business seeing build governance (see pipeline/agents.py)."""
    return [
        str(ctx.project_dir),
        str(ctx.run_dir),
        str(gates.SCHEMA_DIR),
        str(Path(ctx.glossary_path).parent),
        str(gates.REPO_ROOT / "templates"),
        str(gates.CONFIG_DIR),  # channel_specs.json for the creative stage (DR-7 spec table)
    ]


def _summarise(attempts: list) -> str:
    cost = sum(a["subagent"].get("cost_usd") or 0.0 for a in attempts)
    models = sorted({m for a in attempts for m in a["subagent"].get("model_ids") or []})
    return f"{len(attempts)} attempt(s) · ${cost:.4f} · {', '.join(models) or 'model unreported'}"


def _classification_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 2 — project type, plus the onboarding tier read from client config (DR-11)."""
    outcome = stages.classify(
        sources=ctx.sources, run_dir=ctx.run_dir, project_id=ctx.project_id,
        client_config=ctx.client_config, glossary_path=ctx.glossary_path, access_dirs=_access_dirs(ctx),
    )
    ctx.artifacts["classification"] = outcome
    print(
        f"        {outcome['project_type']} ({outcome['classification_confidence']} confidence)"
        f" · tier {outcome['sensitivity_tier']} · {_summarise(outcome['attempts'])}"
    )
    return {"classification": outcome}


def _fidelity_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 3 — every transcript is scored and annotated before extraction may read it."""
    transcripts = [s for s in ctx.selected_sources() if s.source_type == "transcript"]
    if not transcripts:
        print("        no transcripts in this project — nothing to score")
        return {"fidelity": [], "note": "no transcripts"}

    results = []
    for source in transcripts:
        print(f"      · scoring {source.source_id}…")
        outcome = stages.fidelity_check(source, ctx.run_dir, ctx.glossary_path, _access_dirs(ctx))
        ctx.artifacts.setdefault("annotated", {})[source.source_id] = Path(outcome["annotated_file"])
        print(
            f"        verdict={outcome['verdict']} · score={outcome['fidelity_score']}"
            f" · {outcome['tokens_flagged']} token(s) flagged · {_summarise(outcome['attempts'])}"
        )
        results.append(outcome)
    return {"fidelity": results}


def _extraction_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 4 — one `extract` subagent invocation per source, each gated on its artifact."""
    results = []
    for source in ctx.selected_sources():
        annotated = (ctx.artifacts.get("annotated") or {}).get(source.source_id)
        via = " (fidelity-annotated)" if annotated else ""
        print(f"      · extracting {source.source_id} ({source.source_type}){via}…")
        outcome = extraction.extract_source(
            source=source,
            run_dir=ctx.run_dir,
            project_id=ctx.project_id,
            client_config=ctx.client_config,
            glossary_path=ctx.glossary_path,
            access_dirs=_access_dirs(ctx),
            read_path=annotated,
        )
        ctx.artifacts.setdefault("extracts", {})[source.source_id] = json.loads(
            Path(outcome["output_file"]).read_text(encoding="utf-8")
        )
        print(
            f"        {outcome['item_count']} items · {outcome['open_question_count']} open questions"
            f" · {_summarise(outcome['attempts'])}"
        )
        verification = outcome.get("verification")
        if verification:
            risks = ", ".join(verification["risk_classes"]) or "none"
            print(
                f"        verified independently ({verification['model']}, risk: {risks}) · "
                f"{verification['issue_count']} issue(s) · {_summarise(verification['attempts'])}"
            )
        results.append(outcome)
    return {"extracts": results}


def _synthesis_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 6 — assemble the canonical brief, then inject the readiness block the model may not write."""
    outcome = stages.synthesize(
        run_dir=ctx.run_dir, project_id=ctx.project_id, client_config=ctx.client_config,
        classification=ctx.artifacts["classification"], sources=ctx.selected_sources(),
        extracts=ctx.artifacts.get("extracts") or {}, glossary_path=ctx.glossary_path,
        access_dirs=_access_dirs(ctx), readiness_policy=ctx.readiness_policy,
    )
    ctx.artifacts["brief"] = json.loads(Path(outcome["output_file"]).read_text(encoding="utf-8"))
    readiness = outcome["readiness"]
    print(
        f"        {outcome['entry_count']} entries · {outcome['conflict_count']} conflicts"
        f" · {outcome['open_question_count']} open questions · {_summarise(outcome['attempts'])}"
    )
    print(
        f"        readiness: {readiness['fields_with_evidence']}/7 fields evidenced"
        f" · {readiness['low_confidence_share']} low-confidence share → {readiness['verdict']}"
    )
    return {"synthesis": outcome}


def _render_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 7 — both documents from the same object (DR-6)."""
    outcome = stages.render(
        run_dir=ctx.run_dir, brief=ctx.artifacts["brief"],
        glossary_path=ctx.glossary_path, access_dirs=_access_dirs(ctx),
    )
    print(
        f"        el={outcome['el_chars']} chars · en={outcome['en_chars']} chars"
        f" · {_summarise(outcome['attempts'])}"
    )
    # Deterministic tail of the render step, not a new model step: the account-lead
    # review page is a VIEW of brief.json (docs/FABLE_MISSION_visualisation.md), and
    # the styled document views typeset the two rendered markdown documents.
    # Best-effort: the view must never fail a run whose model artifacts succeeded.
    try:
        outcome["review_file"] = str(review.write_review(ctx.run_dir))
        outcome["document_views"] = [str(p) for p in docview.write_documents(ctx.run_dir)]
        print(f"        review page → {outcome['review_file']}")
    except Exception as exc:
        print(f"        review page skipped: {exc}")
    return {"render": outcome}


def _creative_handler(ctx: "RunContext", step: Step) -> dict:
    """Step 9 (Tier 4) — shadow creative brief A/B, sonnet vs opus, on the signed brief (DR-8)."""
    brief = ctx.artifacts["brief"]
    results = creative.run_ab(ctx.run_dir, brief, ctx.glossary_path, _access_dirs(ctx))
    for outcome in results:
        print(
            f"      · {outcome['model_alias']:<7} → {Path(outcome['output_file']).name}"
            f" · {outcome['chars']} chars · {_summarise(outcome['attempts'])}"
        )
    ctx.artifacts["creative"] = results
    return {"creative": results}


#: Model-step handlers, registered per tier as each stage is built.
#: Signature: handler(ctx: RunContext, step: Step) -> dict  (the step's manifest payload)
AGENT_HANDLERS: dict[str, Callable[["RunContext", Step], dict]] = {
    "classify": _classification_handler,
    "fidelity-check": _fidelity_handler,
    "extract": _extraction_handler,
    "synthesize": _synthesis_handler,
    "render": _render_handler,
    "creative-shadow": _creative_handler,
}


class Runner:
    def __init__(
        self,
        project_dir: Path,
        out_dir: Path,
        run_id: Optional[str] = None,
        stage: str = "full",
        glossary: Optional[Path] = None,
        source: Optional[str] = None,
        demo_profile: Optional[Path] = None,
    ):
        self.project_dir = Path(project_dir).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = self.out_dir / self.run_id
        self.stage = stage
        self.glossary = glossary
        self.source = source
        self.demo_profile = Path(demo_profile) if demo_profile else None
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
            "stage": self.stage,
            "demo_profile": str(self.demo_profile) if self.demo_profile else None,
            "sources": [s.as_meta() for s in self.sources],
            "steps": self.steps,
        }
        path = self.run_dir / "run_manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Deterministic walkthrough view of whatever this run produced — every outcome
        # gets one, refusals included. The view must never change a run's outcome.
        try:
            run_review.write_run_review(self.run_dir)
        except Exception as exc:
            print(f"        run review page skipped: {exc}")
        # Completed runs also land on the shareable reviews/ shelf (email / synced
        # folder distribution — mission §8). Refusals stay in runs/ for the operator.
        try:
            published = publish.publish_run(self.run_dir)
            if published:
                print(f"        reviews/ shelf: {', '.join(p.name for p in published)}")
        except Exception as exc:
            print(f"        reviews publish skipped: {exc}")
        return path

    def _hydrate(self, ctx: RunContext) -> None:
        """Load artifacts an earlier run already produced in this directory.

        Makes a run directory resumable, so re-running one leg (`--stage render --run-id <id>`)
        costs one model call instead of re-extracting every source. Only reads what is there;
        a fresh run hydrates nothing.
        """
        # Carry forward the record of steps this directory already ran. Without this, resuming
        # one leg rewrites run_manifest.json with only that leg and the run reads as a complete
        # pipeline that executed a single step — an audit trail that lies by omission.
        prior_manifest = self.run_dir / "run_manifest.json"
        if prior_manifest.is_file():
            previous = json.loads(prior_manifest.read_text(encoding="utf-8")).get("steps") or []
            rerunning = set(STAGE_SELECTIONS[self.stage])
            self.steps = [
                {**step, "from_earlier_run": True}
                for step in previous
                if step.get("name") not in rerunning
            ]

        loaded = []
        classification = self.run_dir / "classification.json"
        if classification.is_file():
            ctx.artifacts["classification"] = json.loads(classification.read_text(encoding="utf-8"))
            loaded.append("classification")

        extracts_dir = self.run_dir / "extracts"
        if extracts_dir.is_dir():
            for path in sorted(extracts_dir.glob("*.json")):
                ctx.artifacts.setdefault("extracts", {})[path.stem] = json.loads(
                    path.read_text(encoding="utf-8")
                )
            if ctx.artifacts.get("extracts"):
                loaded.append(f"{len(ctx.artifacts['extracts'])} extract(s)")

        brief_path = self.run_dir / "brief.json"
        if brief_path.is_file():
            ctx.artifacts["brief"] = json.loads(brief_path.read_text(encoding="utf-8"))
            loaded.append("brief")

        if loaded:
            print(f"  resuming with: {', '.join(loaded)}\n")

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

        try:
            glossary_path = extraction.resolve_glossary(self.glossary)
            client_config = extraction.load_client_config(glossary_path)
        except gates.GateError as exc:
            print(f"[client config] {exc}", file=sys.stderr)
            self._write_manifest("client_config_error", EXIT_GATE_ERROR)
            return EXIT_GATE_ERROR

        print(f"  client: {client_config['client_id']} · tier {client_config['sensitivity_tier']}\n")

        readiness_policy = None
        if self.demo_profile:
            try:
                readiness_policy = gates.load_readiness_policy(self.demo_profile)
            except gates.GateError as exc:
                print(f"[demo profile] {exc}", file=sys.stderr)
                self._write_manifest("demo_profile_error", EXIT_GATE_ERROR)
                return EXIT_GATE_ERROR
            print(f"  DEMO PROFILE: {self.demo_profile} — recorded in the run manifest\n")

        ctx = RunContext(
            project_dir=self.project_dir,
            run_dir=self.run_dir,
            run_id=self.run_id,
            sources=self.sources,
            started_ts=self.started_ts,
            project_id=self.project_dir.name,
            client_config=client_config,
            glossary_path=glossary_path,
            source_filter=self.source,
            readiness_policy=readiness_policy,
        )

        self._hydrate(ctx)

        selected = STAGE_SELECTIONS[self.stage]
        for step in (s for s in STEP_SEQUENCE if s.name in selected):
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

        missing = [k for k in STEP_PREREQUISITES.get(step.name, ()) if not ctx.artifacts.get(k)]
        if missing:
            needed = ", ".join(f"{k} ({ARTIFACT_FILES[k]})" for k in missing)
            message = (
                f"step '{step.name}' needs {needed} in the run directory, and it is not there. "
                f"Run an earlier stage first, or use --stage full."
            )
            self._record(step, "failed", agent=step.agent, error=message)
            print(f"{label}: FAILED — {message}", file=sys.stderr)
            return "missing_prerequisite", EXIT_GATE_ERROR

        if step.name == "readiness_gate":
            verdict = gates.readiness_gate(ctx.sources)
            if not verdict.ok and ctx.readiness_policy is not None:
                # Demo profile: the production gate's refusal is shown and recorded — never
                # hidden — but the run continues. The manifest carries both the refusal and
                # the profile, so no demo run can pass itself off as a production run.
                self._record(step, "refused_overridden_demo_profile", verdict=verdict.as_dict())
                print(f"{label}: {verdict.message}")
                print(f"{label}: DEMO PROFILE OVERRIDE — production input gate refused this "
                      f"input; continuing for the live demo. This run is marked in its manifest.")
                return None, EXIT_OK
            self._record(step, "pass" if verdict.ok else "refused", verdict=verdict.as_dict())
            print(f"{label}: {verdict.message}")
            if not verdict.ok:
                return "insufficient_input", EXIT_INSUFFICIENT_INPUT
            return None, EXIT_OK

        if step.name == "conflict_pass":
            outcome = conflicts.run_conflict_pass(ctx.artifacts.get("extracts") or {}, ctx.run_dir)
            self._record(step, "pass", **outcome)
            print(
                f"{label}: {outcome['candidate_count']} candidate field(s)"
                f" {outcome['candidate_fields']} · {outcome['internal_conflict_count']} internal"
            )
            return None, EXIT_OK

        handler = AGENT_HANDLERS.get(step.agent or "")
        if handler is None:
            self._record(step, "pending", agent=step.agent, pending_reason="no handler registered")
            print(f"{label}: subagent '{step.agent}' has no handler yet — stopping.")
            return "pending_stage", EXIT_PENDING_STAGE

        print(f"{label}: dispatching '{step.agent}'…")
        try:
            payload = handler(ctx, step)
        except stages.HaltForHuman as exc:
            # Not a failure: the system asked instead of guessing (DR-9, DR-12).
            self._record(step, "halted_for_human", agent=step.agent, question=str(exc))
            print(f"{label}: HALTED FOR HUMAN — {exc}")
            return "halted_for_human", EXIT_HALTED_FOR_HUMAN
        except (gates.GateError, agents.SubagentError) as exc:
            self._record(step, "failed", agent=step.agent, error=str(exc))
            print(f"{label}: FAILED — {exc}", file=sys.stderr)
            return "stage_failed", EXIT_GATE_ERROR

        self._record(step, "pass", **payload)
        print(f"{label}: ok")
        return None, EXIT_OK


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Brief Builder Stage-1 pipeline.")
    parser.add_argument("--project", required=True, help="Input folder (any folder honouring the source-header contract)")
    parser.add_argument("--out", default=str(gates.REPO_ROOT / "runs"), help="Where run directories are written")
    parser.add_argument("--run-id", default=None, help="Override the timestamp run id (tests, reruns)")
    parser.add_argument(
        "--stage",
        default="full",
        choices=sorted(STAGE_SELECTIONS),
        help="Which leg of the pipeline to run ('extraction' = readiness gate + step 4 only)",
    )
    parser.add_argument("--glossary", default=None, help="Client config; defaults to the single file in glossary/")
    parser.add_argument("--source", default=None, help="Restrict extraction to one source_id")
    parser.add_argument(
        "--demo-profile", default=None, metavar="POLICY_JSON",
        help="Live-demo mode: readiness policy file for the draft verdict; the production "
             "input gate's refusal is printed and recorded in the manifest but does not stop "
             "the run. Never used in production runs.")
    args = parser.parse_args(argv)

    try:
        return Runner(
            Path(args.project),
            Path(args.out),
            args.run_id,
            stage=args.stage,
            glossary=Path(args.glossary) if args.glossary else None,
            source=args.source,
            demo_profile=Path(args.demo_profile) if args.demo_profile else None,
        ).run()
    except gates.GateError as exc:
        print(f"[gate] {exc}", file=sys.stderr)
        return EXIT_GATE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
