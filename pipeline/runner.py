"""Step sequencer for the Brief Builder pipeline (PRD §5).

The runner owns *sequence and refusal*; the subagents own judgment. Every step is
declared below with the kind of thing it is — `deterministic` steps execute here,
`model` steps dispatch to a Claude Code subagent through `AGENT_HANDLERS`.

All seven Stage-1 steps are built. Before any of them, the project folder must carry a valid
`data_declaration.json` (pipeline/data_policy.py); without one the run is refused with exit 6.
A run either completes, refuses (insufficient input),
halts for a human (low classification confidence, or a transcript the fidelity gate will not
vouch for), or fails a gate — and the exit code says which. Human sign-off is PRD step 8 and
deliberately absent: it is not a step the system executes, it is the gate it stops at.

Live model calls are opt-in: with a real `claude` CLI the runner refuses (exit 7, before any run
directory exists) unless `--live` or `BRIEF_BUILDER_LIVE=1` is given. The offline replay binary
needs no opt-in. `--out` is hermetic: only a run written to the default `runs/` (or one given
`--publish`) is copied onto the repository's `reviews/` shelf, and never a non-synthetic one.

Usage:
    python pipeline/runner.py --project fixtures/northlight_01 --live
    python pipeline/runner.py --project fixtures/northlight_01 --stage extraction --live
    BRIEF_BUILDER_CLAUDE_BIN="$PWD/tools/replay/claude" \\
        python pipeline/runner.py --project fixtures/northlight_01 --out /tmp/runs
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import re
import shutil
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional, cast
from uuid import uuid4

if __package__ in (None, ""):  # allow `python pipeline/runner.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import (  # noqa: E402
    PIPELINE_VERSION,
    agents,
    approval,
    clock,
    conflicts,
    creative,
    data_policy,
    docview,
    extraction,
    gates,
    prescreen,
    publish,
    review,
    revisions,
    run_review,
    stages,
)

EXIT_OK = 0
EXIT_INSUFFICIENT_INPUT = 2
EXIT_PENDING_STAGE = 3
EXIT_GATE_ERROR = 4
EXIT_HALTED_FOR_HUMAN = 5
#: The project folder has no valid data declaration, or its data class forbids the paths given
#: (owner decision 4, 2026-09-22; pipeline/data_policy.py). Refused before any source is read.
EXIT_DATA_DECLARATION = 6
#: A real Claude Code CLI is on the path and nobody opted in to live model calls (`--live` or
#: BRIEF_BUILDER_LIVE=1). Refused before any run directory is created; the message names the
#: offline replay command instead.
EXIT_LIVE_NOT_ENABLED = 7

#: The default output directory. Only runs written here (or given --publish) reach reviews/.
DEFAULT_OUT_DIR = gates.REPO_ROOT / "runs"

DETERMINISTIC = "deterministic"
MODEL = "model"


class CorruptArtifactError(gates.GateError):
    """An artifact an earlier leg left in the run directory cannot be read.

    Raised while hydrating a resumed run. It names the file, and the runner records it in
    the manifest as outcome `corrupt_artifact` — never as lock contention.
    """


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
    Step(9, "creative_shadow", MODEL, "creative-shadow", "Creative drafts for human review (sonnet vs opus)"),
)

#: Which steps each stage selection runs. `extraction` is the Tier-1 path: prove the
#: extraction leg end-to-end without pretending the stages around it exist yet.
STAGE_SELECTIONS = {
    "full": (
        "readiness_gate",
        "classification",
        "fidelity_check",
        "extraction",
        "conflict_pass",
        "synthesis",
        "render",
    ),
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
    client_config: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    glossary_path: Optional[Path] = None
    source_filter: Optional[str] = None
    #: Demo-profile readiness policy (loaded dict) — None in every production run. When set,
    #: the input readiness gate's refusal is printed and recorded but does not stop the run,
    #: and the draft readiness block is computed with this policy instead of the shipped one.
    readiness_policy: Optional[dict] = None
    #: The step being executed (set by the runner before each step): it decides which earlier
    #: stages' outputs the agent's scope protects (`_access_dirs`).
    current_step: Optional[str] = None

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


#: Where a run keeps byte-identical copies of the declared sources and the client config it
#: hands to agents. Agents never get the project folder itself: it may hold harness-only files
#: (answer_key.json) and it is the human's original, not the run's working copy.
STAGED_INPUTS_DIR = "inputs"

#: Paths inside the run directory that no runtime agent may write: the staged inputs, the
#: evidence copies, every human decision record, and the durable logs. Denied to the agent by
#: permission rule (pipeline/agents.py) and re-checked by hash after every model step.
PROTECTED_RUN_PATHS = (
    STAGED_INPUTS_DIR, "evidence", "history", "creative_versions", "question_exchange", "diagnostics",
    "input_snapshot.json", "evidence_index.json", "run_manifest.json", "agency_inputs.json",
    "approval.json", "language_review.json", "coverage_decisions.json", "clarifications.json",
    "amendments.json", "agency_audit.json", "creative_draft.json", "creative_approval.json",
    "approval_withdrawals.json", "releases.json", "handover.json", "revision_lineage.json",
    "signoff_regime.json", "audit_log.jsonl",
)

#: Written by the runner itself while a model step runs, so left out of the integrity check
#: (still denied to agents by permission rule).
_RUNNER_WRITES_DURING_STEPS = ("diagnostics",)

#: What each step produces, relative to the run directory (a name without an extension is a
#: directory). Per-stage write scope: while a step runs, the outputs of every EARLIER step in
#: STEP_SEQUENCE are protected exactly like the human records — denied to the agent by
#: permission rule and hashed by the post-step integrity check — so a steered synthesis agent
#: cannot rewrite an extract, and a steered render or creative agent cannot rewrite brief.json.
STEP_OUTPUTS = {
    "readiness_gate": (),
    "classification": ("classification.json",),
    "fidelity_check": ("fidelity",),
    "extraction": ("extracts", "verification"),
    "conflict_pass": ("conflict_candidates.json",),
    "synthesis": ("brief.json", "coverage_ledger.json"),
    "render": ("brief_el.md", "brief_en.md", "brief_review.html", "brief_el.html", "brief_en.html"),
    "creative_shadow": ("creative",),
}


def earlier_step_outputs(step_name: Optional[str]) -> tuple:
    """Every output of the steps before `step_name` in STEP_SEQUENCE (empty for none/unknown)."""
    names = [s.name for s in STEP_SEQUENCE]
    if step_name not in names:
        return ()
    earlier = names[:names.index(step_name)]
    return tuple(out for name in earlier for out in STEP_OUTPUTS.get(name, ()))


def source_output_paths(step_name: str, source_id: str) -> tuple:
    """The files one source's leg of a per-source model step writes, relative to the run."""
    if step_name == "fidelity_check":
        return (f"fidelity/{source_id}.report.json", f"fidelity/{source_id}.annotated.md")
    if step_name == "extraction":
        return (f"extracts/{source_id}.json", f"verification/{source_id}.verify.json",
                f"verification/{source_id}.findings.json", f"verification/{source_id}.adjudication.json")
    return ()


def model_output_paths(step_name: str, sources: Iterable = ()) -> tuple:
    """The artifacts a model step's gate will judge, relative to the run — what must not
    survive from an earlier leg into this one. Per-source steps name only the given sources'
    files (so `--source X` never touches another source's extract)."""
    if step_name == "classification":
        return ("classification.json",)
    if step_name == "fidelity_check":
        return tuple(p for s in sources if s.source_type == "transcript"
                     for p in source_output_paths(step_name, s.source_id))
    if step_name == "extraction":
        return tuple(p for s in sources for p in source_output_paths(step_name, s.source_id))
    if step_name == "synthesis":
        return ("brief.json", "coverage_ledger.json")
    if step_name == "render":
        return ("brief_el.md", "brief_en.md")
    if step_name == "creative_shadow":
        return tuple(f"creative/creative_brief_{m}.md" for m in creative.AB_MODELS)
    return ()


def clear_stale_outputs(run_dir: Path, relative_paths: Iterable[str]) -> list:
    """Move every existing file among `relative_paths` into `history/<stamp>-stale/`, keeping
    its relative path; return what was moved.

    Called before a model step is invoked: an artifact left by an earlier leg (a resumed run,
    a retried demo leg) must never be what the gate judges when the agent writes nothing.
    Archived, never deleted — the earlier leg's evidence stays in the run.
    """
    run_dir = Path(run_dir)
    present = [rel for rel in relative_paths if (run_dir / rel).is_file()]
    if not present:
        return []
    target = run_dir / "history" / f"{clock.compact('%Y%m%dT%H%M%S')}-stale-{uuid4().hex[:8]}"
    for rel in present:
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(run_dir / rel), str(destination))
    return present

#: A source_id becomes a file name (extracts/<id>.json, verification/, fidelity/). Anything that
#: could name a different directory is refused before any path is built from it.
SAFE_SOURCE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")

#: Staged file names (inputs/<name>, inputs/client/<name>) follow the same rule: no separator,
#: no leading dot or dash, no space or comma a CLI permission-rule list could split on.
SAFE_FILE_NAME_RE = SAFE_SOURCE_ID_RE


def unsafe_file_name(name: str) -> bool:
    """True when `name` may not become a staged file name (validated like a source_id)."""
    return not SAFE_FILE_NAME_RE.fullmatch(name) or ".." in name


def unsafe_source_ids(sources) -> list:
    """Every declared source_id that must not become part of a file path, with the reason.

    Deliberately a separate check from `gates.parse_source_header` (whose behaviour the frozen
    harness depends on): the header contract says what a source IS; this says whether the
    runner may build paths from it.
    """
    problems = []
    for source in sources:
        sid = source.source_id
        if not SAFE_SOURCE_ID_RE.fullmatch(sid) or ".." in sid:
            problems.append(
                f"{Path(source.path).name}: source_id {sid!r} is not a safe identifier — use "
                f"letters, digits, '_', '-' or '.', starting with a letter or digit, and no '..'"
            )
    return problems


def stage_inputs(run_dir: Path, sources, glossary_path: Path) -> tuple:
    """Copy the declared sources and the client config into <run_dir>/inputs/, read-only.

    Byte-identical copies — the text the gates verify citations against is the same text — so
    work orders point agents at the run directory, never at the project folder. An existing
    staged copy must match byte for byte: a difference means something wrote to the run's
    inputs, and the run refuses rather than silently re-staging. Returns
    (staged_sources, staged_glossary_path).
    """
    target = Path(run_dir) / STAGED_INPUTS_DIR
    client_dir = target / "client"
    client_dir.mkdir(parents=True, exist_ok=True)
    names = [Path(s.path).name for s in sources] + [Path(glossary_path).name]
    unsafe = [n for n in names if unsafe_file_name(n)]
    if unsafe:
        raise gates.InputContractError(
            f"file name(s) {unsafe} cannot be staged: use letters, digits, '_', '-' or '.', "
            f"starting with a letter or digit, and no '..' (the rule for source_ids)")
    wanted = {(target / Path(s.path).name): Path(s.path) for s in sources}
    wanted[client_dir / Path(glossary_path).name] = Path(glossary_path)
    extra = sorted(str(p.relative_to(target)) for p in target.rglob("*")
                   if p.is_file() and p not in wanted)
    if extra:
        raise gates.InputContractError(
            f"{target}: staged inputs contain files this run did not declare {extra}; "
            f"use a new run directory")
    for staged, original in wanted.items():
        if original.name in gates.HARNESS_ONLY_FILES:
            raise gates.InputContractError(f"{original}: harness-only files are never staged")
        data = original.read_bytes()
        if staged.exists() or staged.is_symlink():
            if staged.is_symlink() or staged.read_bytes() != data:
                raise gates.InputContractError(
                    f"{staged}: staged input differs from {original}; the run's inputs were "
                    f"modified — use a new run directory")
            continue
        staged.write_bytes(data)
        staged.chmod(0o444)
    staged_sources = [dataclasses.replace(s, path=target / Path(s.path).name) for s in sources]
    return staged_sources, client_dir / Path(glossary_path).name


def protected_run_paths(step_name: Optional[str] = None, source_id: Optional[str] = None,
                        all_source_ids: Iterable[str] = ()) -> tuple:
    """Run-relative paths no agent may write during `step_name` (for one source's leg of it).

    The fixed records (PROTECTED_RUN_PATHS), every earlier step's outputs, and — within a
    per-source step — every OTHER source's files of that step, so the extractor of one source
    cannot rewrite another source's extract or verification report.
    """
    paths = list(PROTECTED_RUN_PATHS) + list(earlier_step_outputs(step_name))
    if step_name and source_id:
        paths += [p for other in all_source_ids if other != source_id
                  for p in source_output_paths(step_name, other)]
    return tuple(dict.fromkeys(paths))


def _access_dirs(ctx: RunContext, source_id: Optional[str] = None) -> agents.AccessScope:
    """What a subagent may touch. It may WRITE the run directory only — minus the protected
    records inside it and the outputs of every earlier step (`protected_run_paths`) — and READ
    the staged inputs there plus the skeleton directories (schema/, templates/, config/), which
    are read-only by permission rule.

    Never granted: the project folder (it can hold harness-only files; agents read the staged
    copies instead), the glossary's own folder (staged too), and the repo root, where CLAUDE.md
    lives — a runtime agent has no business seeing build governance (see pipeline/agents.py).
    """
    run_dir = Path(ctx.run_dir)
    protected = protected_run_paths(ctx.current_step, source_id,
                                    [s.source_id for s in ctx.sources or ()])
    return agents.AccessScope(
        writable=(str(run_dir),),
        read_only=(
            str(gates.SCHEMA_DIR),
            str(gates.REPO_ROOT / "templates"),
            str(gates.CONFIG_DIR),  # channel_specs.json for the creative stage (DR-7 spec table)
        ),
        protected=tuple(str(run_dir / name) for name in protected),
    )


def _hash_tree(path: Path) -> dict:
    """{relative name: sha256} for a file, or for every file under a directory; {} if absent."""
    path = Path(path)
    if path.is_file():
        return {".": revisions.file_hash(path)}
    if not path.is_dir():
        return {}
    return {str(p.relative_to(path)): revisions.file_hash(p)
            for p in sorted(path.rglob("*")) if p.is_file()}


def integrity_state(ctx: RunContext, originals=(), scope: Optional[agents.AccessScope] = None) -> dict:
    """Hashes of everything a model step must leave untouched: the read-only skeleton dirs,
    the protected paths inside the run directory (human records and earlier steps' outputs),
    and the original project inputs. `scope` defaults to the current step's `_access_dirs`."""
    scope = agents.AccessScope.coerce(scope if scope is not None else _access_dirs(ctx))
    watched = list(scope.read_only)
    watched += [p for p in scope.protected if Path(p).name not in _RUNNER_WRITES_DURING_STEPS]
    watched += [str(p) for p in originals]
    return {p: _hash_tree(Path(p)) for p in watched}


def integrity_violations(before: dict, after: dict) -> list:
    """Every watched path whose content changed between two `integrity_state` snapshots."""
    problems = []
    for path in sorted(set(before) | set(after)):
        old, new = before.get(path, {}), after.get(path, {})
        for name in sorted(set(old) | set(new)):
            if old.get(name) != new.get(name):
                change = "created" if name not in old else "removed" if name not in new else "modified"
                shown = path if name == "." else f"{path}/{name}"
                problems.append(f"{shown} was {change} during a model step")
    return problems


def _summarise(attempts: list) -> str:
    """One progress line per stage: attempts, tokens and models (tokens, not dollars — the
    operator is on a subscription; the manifest keeps the CLI's own cost field for audit)."""
    tokens = sum(sum(v for v in (a["subagent"].get("usage") or {}).values() if isinstance(v, int))
                 for a in attempts)
    models = sorted({m for a in attempts for m in a["subagent"].get("model_ids") or []})
    return f"{len(attempts)} attempt(s) · {tokens:,} tokens · {', '.join(models) or 'model unreported'}"


def _glossary(ctx: RunContext) -> Path:
    """The staged client config a model step reads. `main` resolves it before the first step, so
    the Optional field is a Path here (typed for mypy only; nothing is checked or changed)."""
    return cast(Path, ctx.glossary_path)


def _classification_handler(ctx: RunContext, step: Step) -> dict:
    """Step 2 — project type, plus the onboarding tier read from client config (DR-11)."""
    outcome = stages.classify(
        sources=ctx.sources, run_dir=ctx.run_dir, project_id=ctx.project_id,
        client_config=ctx.client_config, glossary_path=_glossary(ctx), access_dirs=_access_dirs(ctx),
    )
    ctx.artifacts["classification"] = outcome
    print(
        f"        {outcome['project_type']} ({outcome['classification_confidence']} confidence)"
        f" · tier {outcome['sensitivity_tier']} · {_summarise(outcome['attempts'])}"
    )
    return {"classification": outcome}


def _fidelity_handler(ctx: RunContext, step: Step) -> dict:
    """Step 3 — every transcript is scored and annotated before extraction may read it."""
    transcripts = [s for s in ctx.selected_sources() if s.source_type == "transcript"]
    if not transcripts:
        print("        no transcripts in this project — nothing to score")
        return {"fidelity": [], "note": "no transcripts"}

    results = []
    for source in transcripts:
        print(f"      · scoring {source.source_id}…")
        outcome = stages.fidelity_check(source, ctx.run_dir, _glossary(ctx), _access_dirs(ctx))
        ctx.artifacts.setdefault("annotated", {})[source.source_id] = Path(outcome["annotated_file"])
        print(
            f"        verdict={outcome['verdict']} · score={outcome['fidelity_score']}"
            f" · {outcome['tokens_flagged']} token(s) flagged · {_summarise(outcome['attempts'])}"
        )
        results.append(outcome)
    return {"fidelity": results}


def _extraction_handler(ctx: RunContext, step: Step) -> dict:
    """Step 4 — one `extract` subagent invocation per source, each gated on its artifact."""
    results = []
    for source in ctx.selected_sources():
        annotated = (ctx.artifacts.get("annotated") or {}).get(source.source_id)
        via = " (fidelity-annotated)" if annotated else ""
        print(f"      · extracting {source.source_id} ({source.source_type}){via}…")
        # One source's leg may write only that source's extract and verification files: the
        # other sources' files are denied by rule and hashed around the leg.
        scope = _access_dirs(ctx, source_id=source.source_id)
        before = integrity_state(ctx, (), scope)
        outcome = extraction.extract_source(
            source=source,
            run_dir=ctx.run_dir,
            project_id=ctx.project_id,
            client_config=ctx.client_config,
            glossary_path=_glossary(ctx),
            access_dirs=scope,
            read_path=annotated,
        )
        tampered = integrity_violations(before, integrity_state(ctx, (), scope))
        if tampered:
            raise gates.GateError(f"integrity: {source.source_id}'s leg changed another source's files: "
                                  + "; ".join(tampered))
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


def _synthesis_handler(ctx: RunContext, step: Step) -> dict:
    """Step 6 — assemble the canonical brief, then inject the readiness block the model may not write."""
    outcome = stages.synthesize(
        run_dir=ctx.run_dir, project_id=ctx.project_id, client_config=ctx.client_config,
        classification=ctx.artifacts["classification"], sources=ctx.selected_sources(),
        extracts=ctx.artifacts.get("extracts") or {}, glossary_path=_glossary(ctx),
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


def _render_handler(ctx: RunContext, step: Step) -> dict:
    """Step 7 — both documents from the same object (DR-6)."""
    outcome = stages.render(
        run_dir=ctx.run_dir, brief=ctx.artifacts["brief"],
        glossary_path=_glossary(ctx), access_dirs=_access_dirs(ctx),
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


def _creative_handler(ctx: RunContext, step: Step) -> dict:
    """Step 9 (Tier 4) — shadow creative brief A/B, sonnet vs opus, on the signed brief (DR-8)."""
    brief = ctx.artifacts["brief"]
    bound_specs = revisions.load(ctx.run_dir / "input_snapshot.json", {}).get("channel_specs")
    results = creative.run_ab(ctx.run_dir, brief, _glossary(ctx), _access_dirs(ctx),
                             spec_table_path=Path(bound_specs["path"]) if bound_specs else None)
    for outcome in results:
        print(
            f"      · {outcome['model_alias']:<7} → {Path(outcome['output_file']).name}"
            f" · {outcome['chars']} chars · {_summarise(outcome['attempts'])}"
        )
    ctx.artifacts["creative"] = results
    return {"creative": results}


#: Model-step handlers, registered per tier as each stage is built.
#: Signature: handler(ctx: RunContext, step: Step) -> dict  (the step's manifest payload)
AGENT_HANDLERS: dict[str, Callable[[RunContext, Step], dict]] = {
    "classify": _classification_handler,
    "fidelity-check": _fidelity_handler,
    "extract": _extraction_handler,
    "synthesize": _synthesis_handler,
    "render": _render_handler,
    "creative-shadow": _creative_handler,
}


def repo_relative(path: Path) -> str:
    """`path` relative to the repository when it lies inside it, else absolute — what a
    manifest records, so committed evidence carries no machine-specific prefix."""
    resolved = Path(path).resolve()
    try:
        return str(resolved.relative_to(gates.REPO_ROOT.resolve()))
    except ValueError:
        return str(resolved)


def _read_artifact(path: Path) -> dict:
    """Load one JSON artifact of an earlier leg; a file that will not parse is named, not guessed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise CorruptArtifactError(
            f"{path.name} in {path.parent} is not valid JSON ({exc}). Inspect or remove it, "
            f"then resume, or start a new run."
        ) from exc


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
        *,
        live: Optional[bool] = None,
        publish: Optional[bool] = None,
        reviews_dir: Optional[Path] = None,
    ):
        """`live`: the live-call opt-in (None = BRIEF_BUILDER_LIVE). `publish`: copy a completed
        synthetic run onto the reviews/ shelf (None = only when `out_dir` is the default runs/).
        `reviews_dir`: the shelf (None = the repository's reviews/)."""
        self.project_dir = Path(project_dir).resolve()
        self.out_dir = Path(out_dir).resolve()
        self.live = live
        self.publish = (self.out_dir == DEFAULT_OUT_DIR.resolve()) if publish is None else bool(publish)
        self.reviews_dir = Path(reviews_dir) if reviews_dir else None
        self.cli: Optional[dict] = None
        self.prescreen: Optional[dict] = None
        self.run_id = run_id or clock.compact("%Y%m%d-%H%M%S-%f")
        self.run_dir = self.out_dir / self.run_id
        self.stage = stage
        self.glossary = glossary
        self.source = source
        self.demo_profile = Path(demo_profile) if demo_profile else None
        self.steps: list[dict] = []
        self.sources: list = []
        self.started_ts: str = ""
        #: The human's original input files (sources + client config) — watched, never granted.
        self._originals: list = []
        self.data_declaration: Optional[dict] = None

    # -- plumbing ----------------------------------------------------------------

    def _record(self, step: Step, status: str, **payload) -> dict:
        entry = {**asdict(step), "status": status, **payload}
        self.steps.append(entry)
        return entry

    def _write_manifest(self, outcome: str, exit_code: int, error: Optional[str] = None) -> Path:
        manifest = {
            "run_id": self.run_id,
            "pipeline_version": PIPELINE_VERSION,
            "project_dir": repo_relative(self.project_dir),
            "started_ts": self.started_ts,
            "finished_ts": clock.timestamp("seconds"),
            "outcome": outcome,
            "exit_code": exit_code,
            "stage": self.stage,
            "demo_profile": str(self.demo_profile) if self.demo_profile else None,
            "data_declaration": self.data_declaration,
            "live": bool((self.cli or {}).get("live")),
            "cli": self.cli,
            "prescreen": self.prescreen,
            "sources": [s.as_meta() for s in self.sources],
            "steps": self.steps,
        }
        if error:
            manifest["error"] = error
        path = self.run_dir / "run_manifest.json"
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        # Deterministic walkthrough view of whatever this run produced — every outcome
        # gets one, refusals included. The view must never change a run's outcome.
        try:
            run_review.write_run_review(self.run_dir)
        except Exception as exc:
            print(f"        run review page skipped: {exc}")
        self._publish(outcome)
        return path

    def _publish(self, outcome: str) -> None:
        """Copy a completed run's pages onto the reviews/ shelf — only when asked for.

        The shelf is for email / synced-folder distribution (mission §8) and lives inside the
        repository, so `--out` is hermetic: a run written anywhere but the default runs/ touches
        nothing outside its output directory unless --publish is passed, and a non-synthetic run
        never publishes into the repository. Refusals publish nothing (no brief page).
        """
        if not self.publish:
            return
        if (self.data_declaration or {}).get("data_class") != data_policy.SYNTHETIC:
            if outcome == "complete":
                print("        reviews/ shelf skipped: only synthetic runs publish into the repository")
            return
        try:
            published = publish.publish_locked(self.run_dir, self.reviews_dir)
            if published:
                print(f"        reviews/ shelf: {', '.join(p.name for p in published)}")
        except Exception as exc:
            print(f"        reviews publish skipped: {exc}")

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
            previous = _read_artifact(prior_manifest).get("steps") or []
            rerunning = set(STAGE_SELECTIONS[self.stage])
            self.steps = [
                {**step, "from_earlier_run": True}
                for step in previous
                if step.get("name") not in rerunning
            ]

        loaded = []
        classification = self.run_dir / "classification.json"
        if classification.is_file():
            ctx.artifacts["classification"] = _read_artifact(classification)
            loaded.append("classification")

        extracts_dir = self.run_dir / "extracts"
        if extracts_dir.is_dir():
            for path in sorted(extracts_dir.glob("*.json")):
                ctx.artifacts.setdefault("extracts", {})[path.stem] = _read_artifact(path)
            if ctx.artifacts.get("extracts"):
                loaded.append(f"{len(ctx.artifacts['extracts'])} extract(s)")

        brief_path = self.run_dir / "brief.json"
        if brief_path.is_file():
            ctx.artifacts["brief"] = _read_artifact(brief_path)
            loaded.append("brief")

        if loaded:
            print(f"  resuming with: {', '.join(loaded)}\n")

    def _corrupt_artifact(self, exc: CorruptArtifactError) -> int:
        """Report an unreadable resume artifact by name and record it in the manifest.

        The unreadable file stays where it is for inspection, and a copy of the earlier
        manifest is kept in history/ before this leg's manifest replaces it.
        """
        print(f"[corrupt artifact] {exc}", file=sys.stderr)
        revisions.archive(self.run_dir, ["run_manifest.json"], copy_only=True)
        self._write_manifest("corrupt_artifact", EXIT_GATE_ERROR, error=str(exc))
        return EXIT_GATE_ERROR

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
        # Only lock contention is reported as a lock problem. Anything else keeps its own name:
        # gate errors are recorded per step, an unreadable resume artifact as outcome
        # `corrupt_artifact`, and an unexpected error as a traceback — never as contention.
        # Two refusals come first, before the run lock creates the run directory: a project
        # folder that does not exist, and a real CLI nobody opted in to.
        if not self.project_dir.is_dir():
            print(f"[input] project folder not found: {self.project_dir} — pass --project with a folder "
                  f"holding data_declaration.json and the source documents", file=sys.stderr)
            return EXIT_INSUFFICIENT_INPUT
        refusal = agents.live_refusal(self.live)
        if refusal:
            print(f"[live calls] {refusal}", file=sys.stderr)
            return EXIT_LIVE_NOT_ENABLED
        try:
            with revisions.run_lock(self.run_dir):
                return self._run_locked()
        except revisions.RunBusyError as exc:
            print(f"[run lock] {exc}", file=sys.stderr)
            return EXIT_GATE_ERROR

    def _run_locked(self) -> int:
        self.started_ts = clock.timestamp("seconds")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        # The model transport, recorded in every manifest: binary, `--version`, replay or live.
        self.cli = agents.cli_record(self.live)
        print(f"Brief Builder {PIPELINE_VERSION} · run {self.run_id}")
        print(f"  input : {self.project_dir}")
        print(f"  output: {self.run_dir}")
        transport = ("offline replay (no model calls)" if self.cli["replay"]
                     else "LIVE model calls" if self.cli["live"] else "no CLI found")
        print(f"  model : {transport} · {self.cli.get('version') or self.cli['binary']}\n")

        # Input contract, first clause: what kind of material is this? Refused before any
        # source is read, so an undeclared folder never reaches a work order or a model.
        try:
            declaration = data_policy.require_for_run(
                self.project_dir, out_dir=self.out_dir, glossary=self.glossary)
        except data_policy.DataDeclarationError as exc:
            self.data_declaration = {"refused": str(exc)}
            print(f"[data declaration] {exc}", file=sys.stderr)
            self._write_manifest("data_declaration_refused", EXIT_DATA_DECLARATION)
            return EXIT_DATA_DECLARATION
        self.data_declaration = declaration.as_record()
        print(f"  data  : {declaration.data_class}"
              + ("" if declaration.is_synthetic else f" · approval {declaration.approval_ref}"
                 f" by {declaration.approved_by} on {declaration.approved_on}") + "\n")

        try:
            self.sources = gates.discover_sources(self.project_dir)
        except gates.InputContractError as exc:
            self.sources = []
            print(f"[input contract] {exc}", file=sys.stderr)
            self._write_manifest("input_contract_error", EXIT_GATE_ERROR)
            return EXIT_GATE_ERROR

        unsafe = unsafe_source_ids(self.sources)
        if unsafe:
            # Before any path is built from a source_id (extracts/, fidelity/, verification/).
            print("[input contract] " + "; ".join(unsafe), file=sys.stderr)
            self._write_manifest("input_contract_error", EXIT_GATE_ERROR)
            return EXIT_GATE_ERROR

        for s in self.sources:
            print(f"  · {s.source_id} ({s.source_type}, {s.source_date})")
        print()

        # Advisory personal-data pre-screen of the declared sources only (never another file in
        # the folder): counts and line numbers, never values; never blocks (pipeline/prescreen.py).
        try:
            self.prescreen = prescreen.scan(self.project_dir, files=[s.path for s in self.sources])
            if self.prescreen["sources_with_findings"]:
                print(f"  prescreen (advisory): {self.prescreen['sources_with_findings']} source(s) with "
                      f"personal-data signals {self.prescreen['totals']} — see run_manifest.json\n")
        except (OSError, ValueError, KeyError) as exc:
            self.prescreen = {"advisory": True, "blocking": False, "error": str(exc)}

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

        paths = {f"source:{s.source_id}": s.path for s in self.sources}
        paths.update({"glossary": glossary_path,
                      "channel_specs": gates.CONFIG_DIR / "channel_specs.json",
                      "campaign_profiles": gates.CONFIG_DIR / "campaign_profiles.json",
                      "model_routing": gates.CONFIG_DIR / "model_routing.json",
                      "readiness_policy": self.demo_profile or gates.CONFIG_DIR / "readiness_policy.json"})
        snapshot = self.run_dir / "input_snapshot.json"
        try:
            bound = (_read_artifact(snapshot) if snapshot.is_file() else {}).get("channel_specs")
        except CorruptArtifactError as exc:
            return self._corrupt_artifact(exc)
        if (self.run_dir / "agency_inputs.json").exists() and bound:
            paths["channel_specs"] = Path(bound["path"])
        paths.update({f"skill:{p.name}": p for p in (gates.REPO_ROOT / "skills").glob("*.md")})
        # The schemas and templates are read at runtime by gates and agents, so they are bound
        # too. A snapshot recorded before they were bound stays as recorded — adding keys to it
        # would read as an input change and strand every legacy run.
        skeleton = {f"schema:{p.name}": p for p in sorted(gates.SCHEMA_DIR.glob("*.json"))}
        skeleton.update({f"template:{p.name}": p for p in sorted((gates.REPO_ROOT / "templates").iterdir())
                         if p.is_file()})
        recorded = revisions.load(self.run_dir / "input_snapshot.json")
        if recorded is None or any(key in recorded for key in skeleton):
            paths.update(skeleton)
        # The render stage's Greek style table (preferred terms, banned calques) is a runtime
        # input too. Bound on the same rule, keyed on its own presence, so a run recorded before
        # it was bound keeps resuming on its recorded inputs.
        style = {"greek_style": stages.GREEK_STYLE_PATH}
        if recorded is None or any(key in recorded for key in style):
            paths.update(style)
        try:
            approval.prepare_run(self.run_dir, paths, self.stage)
        except (ValueError, OSError) as exc:
            print(f"[revision safety] {exc}", file=sys.stderr)
            return EXIT_GATE_ERROR

        # Agents read staged copies inside the run directory, never the project folder.
        try:
            ctx.sources, ctx.glossary_path = stage_inputs(self.run_dir, self.sources, glossary_path)
        except (gates.GateError, OSError) as exc:
            print(f"[input staging] {exc}", file=sys.stderr)
            self._write_manifest("input_contract_error", EXIT_GATE_ERROR)
            return EXIT_GATE_ERROR
        self._originals = [s.path for s in self.sources] + [glossary_path]

        try:
            self._hydrate(ctx)
        except CorruptArtifactError as exc:
            return self._corrupt_artifact(exc)

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
        ctx.current_step = step.name
        # An artifact an earlier leg left behind must never be what this leg's gate judges:
        # archive it into history/ before the agent is invoked (the agent writes it anew).
        try:
            selected = ctx.selected_sources()
        except gates.InputContractError:
            selected = []  # an unknown --source: the handler reports it as this step's failure
        stale = clear_stale_outputs(ctx.run_dir, model_output_paths(step.name, selected))
        if stale:
            print(f"        archived {len(stale)} output(s) of an earlier leg into history/ before this step")
        before = integrity_state(ctx, self._originals)

        def check_integrity() -> None:
            # Permission rules are the first line; this is the second. Whatever the CLI
            # allowed, a model step that changed a read-only or human-owned file fails.
            tampered = integrity_violations(before, integrity_state(ctx, self._originals))
            if tampered:
                raise gates.GateError("integrity: " + "; ".join(tampered)
                                      + " — runtime agents may write only their own outputs")

        try:
            try:
                payload = handler(ctx, step)
            except stages.HaltForHuman:
                check_integrity()  # a halt must not hide a tampered file
                raise
            check_integrity()
        except stages.HaltForHuman as exc:
            # Not a failure: the system asked instead of guessing (DR-9, DR-12).
            self._record(step, "halted_for_human", agent=step.agent, question=str(exc),
                         **({"stale_outputs_archived": stale} if stale else {}))
            print(f"{label}: HALTED FOR HUMAN — {exc}")
            return "halted_for_human", EXIT_HALTED_FOR_HUMAN
        except (gates.GateError, agents.SubagentError) as exc:
            self._record(step, "failed", agent=step.agent, error=str(exc),
                         **({"stale_outputs_archived": stale} if stale else {}))
            print(f"{label}: FAILED — {exc}", file=sys.stderr)
            return "stage_failed", EXIT_GATE_ERROR

        if stale:
            payload = {**payload, "stale_outputs_archived": stale}
        self._record(step, "pass", **payload)
        print(f"{label}: ok")
        return None, EXIT_OK


def _line_buffered_stdout() -> None:
    """Progress lines reach a log or pipe as they happen, not when the buffer fills."""
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(line_buffering=True)
        except (ValueError, OSError):  # pragma: no cover - a replaced or closed stream
            pass


def main(argv: Optional[list] = None) -> int:
    """CLI entry point: parse the flags, run one leg, return its exit code."""
    _line_buffered_stdout()
    parser = argparse.ArgumentParser(description="Run the Brief Builder Stage-1 pipeline.")
    parser.add_argument(
        "--project",
        required=True,
        help="Input folder: data_declaration.json at its root plus *.md sources "
        "honouring the source-header contract",
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT_DIR),
                        help="Where run directories are written (default runs/). Hermetic: nothing outside it "
                             "is written unless --publish is given")
    parser.add_argument("--live", action="store_true", default=None,
                        help="Allow live model calls through a real Claude Code CLI (or set BRIEF_BUILDER_LIVE=1). "
                             "Without it a real CLI is refused (exit 7); the offline replay binary needs no opt-in")
    parser.add_argument("--publish", dest="publish", action="store_true", default=None,
                        help="Copy a completed synthetic run's pages onto the reviews/ shelf "
                             "(default: only for runs written to the default runs/)")
    parser.add_argument("--no-publish", dest="publish", action="store_false",
                        help="Never copy this run onto the reviews/ shelf")
    parser.add_argument("--reviews-dir", default=None, help="The shelf --publish writes to (default reviews/)")
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
            live=args.live,
            publish=args.publish,
            reviews_dir=Path(args.reviews_dir) if args.reviews_dir else None,
        ).run()
    except gates.GateError as exc:
        print(f"[gate] {exc}", file=sys.stderr)
        return EXIT_GATE_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
