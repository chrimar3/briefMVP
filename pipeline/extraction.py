"""Pipeline step 4 — per-source extraction, driven by the `extract` subagent.

The runner owns everything deterministic around the model call: which source, which paths,
which client config, and — critically — whether the artifact that comes back is acceptable.
The subagent's own self-check (SOURCES.md §8) is a quality aid, not a gate; the gate is here,
in code, where it cannot be talked out of a verdict.

Work orders carry paths and client configuration, never fixture content: the same code runs
on any Input folder honouring the source-header contract.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from pipeline import agents, gates


class ExtractionError(gates.GateError):
    """The extract stage did not produce an acceptable artifact."""


def resolve_glossary(explicit: Optional[Path] = None, glossary_dir: Optional[Path] = None) -> Path:
    """Find the client glossary. Explicit path wins; otherwise the single file in `glossary/`.

    Refuses to choose between several — picking a client config by guesswork is the kind of
    silent error that produces a perfectly-formatted brief for the wrong client.
    """
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ExtractionError(f"glossary not found: {path}")
        return path

    glossary_dir = Path(glossary_dir or gates.REPO_ROOT / "glossary")
    candidates = sorted(glossary_dir.glob("*.json"))
    if len(candidates) == 1:
        return candidates[0]
    raise ExtractionError(
        f"{len(candidates)} glossaries in {glossary_dir} — pass --glossary to name the client config."
    )


def load_client_config(glossary_path: Path) -> dict:
    """Client identity + onboarding sensitivity tier. The tier is read, never inferred (DR-11)."""
    config = json.loads(Path(glossary_path).read_text(encoding="utf-8"))
    client_id = config.get("client_id")
    if not client_id:
        raise ExtractionError(f"{glossary_path}: no client_id in client config.")
    gates.enforce_sensitivity_tier(config.get("sensitivity_tier"))
    return config


def build_work_order(
    source: gates.SourceDoc,
    output_file: Path,
    project_id: str,
    client_config: dict,
    glossary_path: Path,
    fidelity_annotated: bool = False,
    read_path: Optional[Path] = None,
) -> str:
    """The prompt handed to the `extract` subagent.

    Deliberately contains no source content — only paths, identifiers and the output contract.
    The governing rules reach the agent through the injected SOURCES.md in its definition, so
    this order never restates them and never gets to quietly reinterpret them.
    """
    schema_path = gates.SCHEMA_DIR / "extract_schema.json"

    # SOURCES.md §2 assumes transcripts arrive annotated by the fidelity gate. When that step
    # has not run, the agent is the only line of defence against script collapse, and it is
    # entitled to know that rather than assuming a gate cleaned the input.
    precondition = ""
    if source.source_type == "transcript" and not fidelity_annotated:
        precondition = (
            "\nPRECONDITION\n"
            "  This transcript has NOT passed the fidelity gate — there are no [FIDELITY: ...]\n"
            "  annotations in it. SOURCES.md §2 assumes annotated input; since that assumption\n"
            "  does not hold here, rule G carries the full weight: any token sequence that looks\n"
            "  like a glossary term collapsed into Greek script stays exactly as the source wrote\n"
            "  it, with an extraction_note proposing the match and confidence low.\n"
        )
    elif source.source_type == "transcript" and fidelity_annotated:
        precondition = (
            "\nPRECONDITION\n"
            "  This transcript HAS passed the fidelity gate and carries inline `[FIDELITY: ...]`\n"
            "  annotations. Carry each flagged token per rule G: the token itself stays exactly as\n"
            "  written, and the annotation's proposal goes into an extraction_note.\n"
            "  The annotations are NOT part of the transcript. Never quote one inside an `anchor`\n"
            "  and never treat one as something a speaker said — anchors are copied from the\n"
            "  spoken text alone, and are verified against the unannotated original.\n"
        )

    return f"""EXTRACTION WORK ORDER — Brief Builder pipeline step 4.

Extract ONE source into ONE JSON file. Your governing rules are the SOURCES.md content in
your agent definition; this order supplies only the parameters.

INPUT
  source_file      : {read_path or source.path}
  source_type      : {source.source_type}
  source_date      : {source.source_date}
  project_id       : {project_id}
  client_id        : {client_config['client_id']}
  sensitivity_tier : {client_config['sensitivity_tier']}
  client_glossary  : {glossary_path}
  output_contract  : {schema_path}

{precondition}
READ ONLY THESE THREE FILES: source_file, client_glossary, output_contract.
Read no other file in this repository under any circumstances. In particular, any file named
`answer_key.json` is test apparatus and is off limits — reading it would invalidate the run.

OUTPUT
  Write one JSON object to exactly this path (create parent directories if needed):
    {output_file}

  meta block — use these values verbatim:
    project_id     = {project_id}
    source_id      = {source.source_id}
    source_type    = {source.source_type}
    source_date    = {source.source_date}
    extraction_ts  = {datetime.now().isoformat(timespec="seconds")}
    agent_version  = 1.0

  The object is validated against output_contract by the runner, which fails the run rather
  than repairing anything. Note in particular:
    - `additionalProperties` is false throughout — emit exactly the specified keys, no extras.
    - All 11 top-level keys must be present; empty arrays are correct where there is nothing.
    - Every item requires all 7 of: value, lang, location, anchor, speaker_or_author,
      qualifier, confidence. An item with an empty `location` or `anchor` fails the run.

{agents.OUTPUT_DISCIPLINE}

When the file is written, reply with one line: the output path and the number of items emitted.
Do not print the JSON to your reply.
"""


def build_repair_order(output_file: Path, violations: list) -> str:
    """Second attempt: the failures, verbatim, and nothing else."""
    listed = "\n".join(f"  - {v}" for v in violations)
    return f"""REPAIR ORDER — your previous extract at {output_file} failed the runner's gate.

Violations:
{listed}

Fix exactly these problems and rewrite the same file. Do not re-extract from scratch, do not
drop items to make errors go away, and do not invent `location` or `anchor` values to satisfy
the check — if an item genuinely cannot be located in the source, the item should not exist
(SOURCES.md rule 2). Reply with one line when the file is rewritten.
"""


def check_extract(path: Path, source_text: str = "", glossary: Optional[dict] = None) -> list:
    """Every reason this artifact is unacceptable, in one pass.

    Four layers, cheapest first: parses · schema-valid · citations present · citations *real*
    and protected terms unrepaired. The last layer is the one that matters — a silently
    repaired token and an invented timestamp both produce a schema-perfect file, so schema
    validation alone would wave through exactly the failure mode PRD R2 calls the dangerous one.

    Returned together rather than one at a time so the repair attempt sees the whole picture —
    a loop that fixes one violation per round is a way to burn attempts.
    """
    if not path.is_file():
        return [f"no file written at {path}"]
    try:
        extract = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]

    violations = []
    try:
        gates.validate_extract(extract)
    except gates.SchemaValidationError as exc:
        violations.extend(exc.errors)
    violations.extend(gates.find_uncited_items(extract))
    if source_text:
        violations.extend(gates.verify_citations(extract, source_text))
        violations.extend(gates.verify_internal_conflict_citations(extract, source_text))
        if glossary:
            violations.extend(gates.find_unsourced_glossary_terms(extract, source_text, glossary))
    return violations


#: Independent-verification routing (human decision 2026-07-30: extraction runs on sonnet and
#: every extract gets a fresh-session second check; the checker itself runs the strong model
#: whenever the extract carries risk classes). Policy knobs live in config/model_routing.json
#: under "verify_extract" so the routing is config-visible; these are the fallbacks.
_VERIFY_DEFAULTS = {"strong_model": "sonnet", "base_model": None,
                    "risk_classes": ["mandatories", "figures", "garbling", "low_confidence"]}


def _verify_policy() -> dict:
    path = gates.CONFIG_DIR / "model_routing.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8")).get("verify_extract") or {}
    except (OSError, json.JSONDecodeError):
        loaded = {}
    return {**_VERIFY_DEFAULTS, **loaded}


def risk_classes(extract: dict) -> list:
    """Deterministic risk read of one extract — which classes make the verifier run strong.

    mandatories: the one asymmetric field (a missed brand rule is the worst miss).
    figures: any digit or currency signal in a value — numbers are where drift costs money.
    garbling: rule-G flags present — fidelity of corrupted tokens is under active question.
    low_confidence: the extractor itself is unsure somewhere.
    """
    items = [(f, i) for f in gates.BRIEF_FIELDS for i in (extract.get(f) or [])]
    risky = []
    if extract.get("mandatories"):
        risky.append("mandatories")
    if any(re.search(r"\d|€|\bEUR\b", (i.get("value") or "")) for _, i in items):
        risky.append("figures")
    if extract.get("extraction_notes"):
        risky.append("garbling")
    if any((i.get("confidence") == "low") for _, i in items):
        risky.append("low_confidence")
    return risky


def build_verify_order(source: gates.SourceDoc, extract_file: Path, report_file: Path,
                       glossary_path: Path, read_path: Optional[Path] = None) -> str:
    """The prompt handed to the `verify-extract` subagent — parameters only, like every order;
    the reviewer's rules live in its agent definition."""
    return f"""VERIFICATION WORK ORDER — Brief Builder pipeline step 4b.

Independently check ONE finished extract against its source. You are a fresh set of eyes:
report what the extract missed or distorted, per the rules in your agent definition.

INPUT
  source_file : {read_path or source.path}
  extract_file: {extract_file}
  client_glossary: {glossary_path}

READ ONLY THESE THREE FILES: source_file, extract_file, client_glossary.
Read no other file in this repository under any circumstances. In particular, any file named
`answer_key.json` is test apparatus and is off limits — reading it would invalidate the run.

OUTPUT
  Write one JSON report to exactly this path (create parent directories if needed):
    {report_file}
  with source_id = {source.source_id} and the verdict/issues shape from your definition.

When the file is written, reply with one line: the verdict and the number of issues.
Do not print the JSON to your reply.
"""


def check_verify_report(report_file: Path) -> list:
    """Deterministic gate on the verifier's report: shape only — its judgment is its own."""
    if not report_file.is_file():
        return [f"no file written at {report_file}"]
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]
    violations = []
    if report.get("verdict") not in ("confirms", "issues_found"):
        violations.append(f"verdict {report.get('verdict')!r} is not 'confirms' or 'issues_found'")
    issues = report.get("issues")
    if not isinstance(issues, list):
        violations.append("issues must be a list")
    else:
        for idx, issue in enumerate(issues):
            if not isinstance(issue, dict) or not (issue.get("problem") or "").strip():
                violations.append(f"issues[{idx}]: needs a non-empty 'problem'")
        if report.get("verdict") == "confirms" and issues:
            violations.append("verdict 'confirms' with a non-empty issues list — pick one")
        if report.get("verdict") == "issues_found" and not issues:
            violations.append("verdict 'issues_found' with no issues — pick one")
    return violations


def extract_source(
    source: gates.SourceDoc,
    run_dir: Path,
    project_id: str,
    client_config: dict,
    glossary_path: Path,
    access_dirs,
    read_path: Optional[Path] = None,
) -> dict:
    """Run the `extract` subagent on one source until the artifact passes, or give up loudly.

    `read_path` lets a transcript be read in its fidelity-annotated form while every citation is
    still verified against the *original* text. The annotations are a reading aid for the agent;
    they are not part of the evidence, and an anchor that quotes one is a fabricated citation.
    """
    output_file = run_dir / "extracts" / f"{source.source_id}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    order = build_work_order(
        source, output_file, project_id, client_config, glossary_path,
        fidelity_annotated=read_path is not None, read_path=read_path,
    )
    attempts, failed = agents.run_gated(
        "extract", order,
        lambda: check_extract(output_file, source.text, client_config),
        lambda v: build_repair_order(output_file, v),
        access_dirs, stage="extraction", site=source.source_id, run_dir=run_dir,
    )
    if failed:
        raise ExtractionError(
            f"{source.source_id}: no acceptable extract after {agents.MAX_ATTEMPTS} attempts. "
            f"Last violations:\n" + "\n".join(f"  - {v}" for v in failed)
        )

    extract = json.loads(output_file.read_text(encoding="utf-8"))

    # Independent second check (step 4b): a fresh-session reviewer reads source + extract and
    # reports what the deterministic gates cannot see (missed claims, drift, mis-attribution).
    # Risk-routed model: strong when the extract carries risk classes, base otherwise. Its
    # findings drive ONE standard repair round of the extractor; the deterministic gates then
    # re-verify the repaired artifact. One verification round by design — no verify loop.
    policy = _verify_policy()
    risks = risk_classes(extract)
    verify_model = policy["strong_model"] if risks else policy["base_model"]
    report_file = run_dir / "verification" / f"{source.source_id}.verify.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    verify_order = build_verify_order(source, output_file, report_file, glossary_path, read_path)
    verify_attempts, verify_failed = agents.run_gated(
        "verify-extract", verify_order,
        lambda: check_verify_report(report_file),
        lambda v: agents.repair_order(
            "verification report", v, f"Fix exactly these and rewrite {report_file}."),
        access_dirs, stage="verification", site=source.source_id, run_dir=run_dir,
        model_override=verify_model,
    )
    if verify_failed:
        raise ExtractionError(
            f"{source.source_id}: independent verifier produced no valid report after "
            f"{agents.MAX_ATTEMPTS} attempts:\n" + "\n".join(f"  - {v}" for v in verify_failed)
        )
    report = json.loads(report_file.read_text(encoding="utf-8"))
    issues = report.get("issues") or []
    if issues:
        findings = [
            f"independent review — {i.get('where', '?')}: {i['problem']}"
            + (f" (evidence: {i['evidence']})" if i.get("evidence") else "")
            for i in issues
        ]
        repair_attempts, repair_failed = agents.run_gated(
            "extract", build_repair_order(output_file, findings),
            lambda: check_extract(output_file, source.text, client_config),
            lambda v: build_repair_order(output_file, v),
            access_dirs, stage="extraction", site=f"{source.source_id}:verified-repair",
            run_dir=run_dir,
        )
        attempts = attempts + repair_attempts
        if repair_failed:
            raise ExtractionError(
                f"{source.source_id}: repair after independent review failed the gates:\n"
                + "\n".join(f"  - {v}" for v in repair_failed)
            )
        extract = json.loads(output_file.read_text(encoding="utf-8"))

    return {
        "source_id": source.source_id,
        "output_file": str(output_file),
        "attempts": attempts,
        "verification": {
            "report_file": str(report_file),
            "model": verify_model or "agent-default",
            "risk_classes": risks,
            "issue_count": len(issues),
            "attempts": verify_attempts,
        },
        "item_count": sum(len(extract.get(f) or []) for f in gates.BRIEF_FIELDS),
        "open_question_count": len(extract.get("open_questions") or []),
        "extraction_note_count": len(extract.get("extraction_notes") or []),
    }
