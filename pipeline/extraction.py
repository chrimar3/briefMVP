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
    return {
        "source_id": source.source_id,
        "output_file": str(output_file),
        "attempts": attempts,
        "item_count": sum(len(extract.get(f) or []) for f in gates.BRIEF_FIELDS),
        "open_question_count": len(extract.get("open_questions") or []),
        "extraction_note_count": len(extract.get("extraction_notes") or []),
    }
