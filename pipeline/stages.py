"""Pipeline steps 2, 3, 6 and 7 — the remaining model stages of Stage 1.

Each stage follows the same shape as extraction: the runner builds a work order out of paths
and configuration, the subagent produces an artifact, and a deterministic gate here decides
whether that artifact is acceptable. The subagents' own self-checks are quality aids; these
gates are the contract, because a gate that a model can talk its way past is not a gate.

Stage boundaries worth stating explicitly, because each is a design decision rather than an
implementation detail:

* `classify` reports the sensitivity tier from client config; it never infers one (DR-11).
* `fidelity-check` annotates and never rewrites — verified here by stripping annotations and
  requiring byte-equality with the original (TRANSCRIPTS.md §5).
* `synthesize` never populates `readiness`; the runner computes it (SYNTHESIS.md rule 8).
* `render` produces both languages from one object, and neither from the other (DR-6).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from pipeline import agents, conflicts, diagnostics, gates

#: Single source of truth in agents.py — shared so the two repair loops cannot diverge.
MAX_ATTEMPTS = agents.MAX_ATTEMPTS


class StageError(gates.GateError):
    """A stage did not produce an acceptable artifact."""


class HaltForHuman(gates.GateError):
    """The pipeline stopped and asked, rather than guessing (DR-9, TRANSCRIPTS.md §4).

    Distinct from StageError on purpose: this is the system working as designed, and the run
    manifest should not read as if something broke.
    """


def _run_with_repair(agent: str, order: str, check, repair_prompt, access_dirs,
                     run_dir: Optional[Path] = None) -> tuple:
    """Invoke a subagent, gate its artifact, allow exactly one repair round.

    Each attempt is logged to the durable repair sink before the loop can raise, so a stage that
    gives up still leaves a full record of why (see pipeline/diagnostics.py).
    """
    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = agents.invoke(agent, order, access_dirs)
        violations = check()
        attempts.append({"attempt": attempt, "subagent": result.as_dict(), "violations": violations})
        if run_dir is not None:
            diagnostics.record_attempt(run_dir, agent, agent, attempt, violations, result.as_dict())
        if not violations:
            return attempts, None
        order = repair_prompt(violations)
    return attempts, attempts[-1]["violations"]


def _fail(agent: str, violations: list) -> StageError:
    listed = "\n".join(f"  - {v}" for v in violations)
    return StageError(f"{agent}: no acceptable artifact after {MAX_ATTEMPTS} attempts:\n{listed}")


# ======================================================================================
# Step 2 — classification
# ======================================================================================

CLASSIFICATION_KEYS = ("project_type", "classification_confidence", "sensitivity_tier")
PROJECT_TYPES = ("advertising_creative", "other", "unclassified_ask_human")


def build_classification_order(sources, output_file: Path, project_id: str, client_config: dict,
                               glossary_path: Path) -> str:
    listed = "\n".join(f"    {s.source_id} ({s.source_type}, {s.source_date}): {s.path}" for s in sources)
    return f"""CLASSIFICATION WORK ORDER — Brief Builder pipeline step 2.

Decide the project type. Report the sensitivity tier from client config — never infer it.

INPUT
  project_id      : {project_id}
  client_glossary : {glossary_path}
  sources:
{listed}

READ ONLY the files listed above and the client glossary. Any file named `answer_key.json` is
test apparatus and is off limits.

OUTPUT
  Write one JSON object to exactly this path:
    {output_file}

  Required keys: project_id, client_id, project_type, classification_confidence,
  sensitivity_tier, tier_source, rationale, evidence, question_for_human, halt_reason.

  project_type must be one of: {list(PROJECT_TYPES)}
  classification_confidence must be one of: ["high", "medium", "low"]
  sensitivity_tier must be copied from the client glossary, not judged.

Reply with one line: the project_type and confidence you wrote.
"""


def check_classification(path: Path, client_config: dict) -> list:
    if not path.is_file():
        return [f"no file written at {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]

    violations = [f"missing key: {k}" for k in CLASSIFICATION_KEYS if k not in payload]
    if violations:
        return violations

    if payload["project_type"] not in PROJECT_TYPES:
        violations.append(f"project_type {payload['project_type']!r} not in {list(PROJECT_TYPES)}")
    if payload["classification_confidence"] not in ("high", "medium", "low"):
        violations.append(f"classification_confidence {payload['classification_confidence']!r} invalid")

    # The tier is client configuration. A classifier that returns a different one has judged it.
    configured = client_config.get("sensitivity_tier")
    if payload["sensitivity_tier"] != configured:
        violations.append(
            f"sensitivity_tier {payload['sensitivity_tier']!r} does not match the client config "
            f"({configured!r}) — the tier is read from onboarding, never inferred (PRD DR-11)"
        )
    if not (payload.get("evidence") or []):
        violations.append("no evidence for the project_type decision — a routing call with no citation is a vibe")
    return violations


def classify(sources, run_dir: Path, project_id: str, client_config: dict, glossary_path: Path,
             access_dirs) -> dict:
    output_file = Path(run_dir) / "classification.json"
    order = build_classification_order(sources, output_file, project_id, client_config, glossary_path)

    attempts, failed = _run_with_repair(
        "classify", order,
        lambda: check_classification(output_file, client_config),
        lambda v: f"REPAIR ORDER — your classification failed the gate:\n" + "\n".join(f"  - {x}" for x in v)
                  + f"\n\nFix exactly these and rewrite {output_file}.",
        access_dirs, run_dir=Path(run_dir),
    )
    if failed:
        raise _fail("classify", failed)

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    if payload.get("halt_reason"):
        raise HaltForHuman(f"classification halted: {payload['halt_reason']}")
    if payload["project_type"] == "unclassified_ask_human":
        raise HaltForHuman(
            "classification confidence too low to route automatically. "
            f"Question for the account lead: {payload.get('question_for_human') or '(none supplied)'}"
        )

    gates.enforce_sensitivity_tier(payload["sensitivity_tier"])
    return {
        "output_file": str(output_file),
        "project_type": payload["project_type"],
        "classification_confidence": payload["classification_confidence"],
        "sensitivity_tier": payload["sensitivity_tier"],
        "attempts": attempts,
    }


# ======================================================================================
# Step 3 — transcript fidelity gate
# ======================================================================================

#: An annotation is inserted *with* its separating whitespace, so the whitespace is part of the
#: insertion and comes out with it. Without the leading `\s*`, an annotation placed before
#: punctuation ("ογδόντα πέντε [FIDELITY: ...], αλλά") strips back to "πέντε , αλλά" and a
#: correctly-annotated transcript gets rejected for a stray space. The check this serves is
#: "no character of the transcript was altered", and that still holds exactly.
FIDELITY_ANNOTATION_RE = re.compile(r"\s*\[FIDELITY:[^\]]*\]")
FIDELITY_REPORT_KEYS = ("source_id", "tokens_flagged", "glossary_matches", "fidelity_score", "verdict")
FIDELITY_VERDICTS = ("pass", "pass_with_flags", "escalate_to_human")


def build_fidelity_order(source, report_file: Path, annotated_file: Path, glossary_path: Path) -> str:
    return f"""FIDELITY WORK ORDER — Brief Builder pipeline step 3.

Score and annotate one transcript. You never rewrite it.

INPUT
  source_file      : {source.path}
  source_id        : {source.source_id}
  client_glossary  : {glossary_path}

READ ONLY those two files. Any file named `answer_key.json` is off limits.

OUTPUT — two files, at exactly these paths:
  report    : {report_file}
  annotated : {annotated_file}

  The annotated transcript must be the original text with `[FIDELITY: ...]` annotations
  INSERTED and nothing else changed. The runner strips every annotation and requires the
  result to equal the original exactly — one altered character fails the run. Do not
  reformat, do not fix spelling, do not normalise whitespace, do not translate.

  The report is the JSON object defined in your instructions; `verdict` must be one of
  {list(FIDELITY_VERDICTS)}.

Reply with one line: tokens flagged and the verdict.
"""


def check_fidelity(report_file: Path, annotated_file: Path, original: str) -> list:
    violations = []
    if not annotated_file.is_file():
        violations.append(f"no annotated transcript at {annotated_file}")
    else:
        stripped = FIDELITY_ANNOTATION_RE.sub("", annotated_file.read_text(encoding="utf-8"))
        if " ".join(stripped.split()) != " ".join(original.split()):
            violations.append(
                "annotated transcript differs from the original by more than [FIDELITY: ...] "
                "insertions — this stage annotates, it never repairs (TRANSCRIPTS.md §3)"
            )

    if not report_file.is_file():
        violations.append(f"no fidelity report at {report_file}")
        return violations
    try:
        report = json.loads(report_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        violations.append(f"report is not valid JSON: {exc}")
        return violations

    violations.extend(f"report missing key: {k}" for k in FIDELITY_REPORT_KEYS if k not in report)
    if report.get("verdict") not in FIDELITY_VERDICTS:
        violations.append(f"verdict {report.get('verdict')!r} not in {list(FIDELITY_VERDICTS)}")
    return violations


def fidelity_check(source, run_dir: Path, glossary_path: Path, access_dirs) -> dict:
    out_dir = Path(run_dir) / "fidelity"
    out_dir.mkdir(parents=True, exist_ok=True)
    report_file = out_dir / f"{source.source_id}.report.json"
    annotated_file = out_dir / f"{source.source_id}.annotated.md"

    order = build_fidelity_order(source, report_file, annotated_file, glossary_path)
    attempts, failed = _run_with_repair(
        "fidelity-check", order,
        lambda: check_fidelity(report_file, annotated_file, source.text),
        lambda v: "REPAIR ORDER — your fidelity output failed the gate:\n"
                  + "\n".join(f"  - {x}" for x in v)
                  + "\n\nFix exactly these and rewrite both files.",
        access_dirs, run_dir=Path(run_dir),
    )
    if failed:
        raise _fail("fidelity-check", failed)

    report = json.loads(report_file.read_text(encoding="utf-8"))
    if report["verdict"] == "escalate_to_human":
        raise HaltForHuman(
            f"transcript {source.source_id} scored {report.get('fidelity_score')!r} — "
            f"escalated to human. Silent consumption of a bad transcript poisons every "
            f"downstream citation (PRD DR-12); the run continues only by explicit human choice."
        )
    return {
        "source_id": source.source_id,
        "report_file": str(report_file),
        "annotated_file": str(annotated_file),
        "verdict": report["verdict"],
        "fidelity_score": report.get("fidelity_score"),
        "tokens_flagged": report.get("tokens_flagged"),
        "attempts": attempts,
    }


# ======================================================================================
# Step 6 — synthesis
# ======================================================================================


def build_synthesis_order(run_dir: Path, output_file: Path, project_id: str, client_config: dict,
                          classification: dict, sources, glossary_path: Path) -> str:
    listed = "\n".join(f"    {s.source_id} ({s.source_type}, {s.source_date})" for s in sources)
    return f"""SYNTHESIS WORK ORDER — Brief Builder pipeline step 6.

Assemble the canonical brief from the validated extracts. Your governing rules are the
SYNTHESIS.md content in your agent definition.

INPUT
  extracts_dir       : {run_dir / 'extracts'}   (one JSON per source — read all of them)
  conflict_candidates: {run_dir / 'conflict_candidates.json'}
  client_glossary    : {glossary_path}
  output_contract    : {gates.SCHEMA_DIR / 'brief_schema.json'}
  sources:
{listed}

READ ONLY those files. Do NOT read the raw source documents — you assemble over extracts
(PRD DR-2). Any file named `answer_key.json` is off limits.

OUTPUT
  Write one JSON object to exactly this path:
    {output_file}

  meta — use these values verbatim:
    project_id                = {project_id}
    client_id                 = {client_config['client_id']}
    project_type              = {classification['project_type']}
    classification_confidence = {classification['classification_confidence']}
    sensitivity_tier          = {classification['sensitivity_tier']}
    created_ts                = {datetime.now().isoformat(timespec='seconds')}
    pipeline_version          = {gates.REPO_ROOT.name}-stage1
    sources                   = one entry per source above

  OMIT the `readiness` key entirely. The runner computes it deterministically and injects it;
  a model-authored readiness verdict is a defect the harness will catch (SYNTHESIS.md rule 8).

  `signoff` is exactly {{"status": "draft"}}. The agent never signs off (PRD DR-8).

  Conflict candidates are NOT conflicts — they are fields where several sources spoke. Decide
  which are genuine contradictions, emit those as conflicts[] with both positions and their
  evidence, status "open". Never resolve one, never prefer a source, never merge two figures.

  Evidence refs are copied byte-exact from the extracts — anchors are never translated,
  normalised or trimmed. They are the render stage's Greek fidelity anchor.

Reply with one line: entry count, conflict count, open-question count.
"""


def check_synthesis(path: Path, extracts: dict) -> list:
    """Gate the brief *before* the readiness block is injected.

    Schema validation happens after injection (the schema requires `readiness`), so this pass
    checks the things synthesis itself is answerable for: shape, evidence, conflict structure,
    and that it did not help itself to the readiness verdict.
    """
    if not path.is_file():
        return [f"no file written at {path}"]
    try:
        brief = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]

    violations = []
    if "readiness" in brief:
        violations.append(
            "brief contains a `readiness` block — that field is computed by the runner, "
            "not by the model (SYNTHESIS.md rule 8). Remove it."
        )
    if (brief.get("signoff") or {}).get("status") != "draft":
        violations.append("signoff.status must be 'draft' — sign-off is a human act (PRD DR-8)")

    for fieldname in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(brief.get(fieldname) or []):
            refs = entry.get("evidence") or []
            if not refs:
                violations.append(f"{fieldname}[{idx}]: no evidence — every claim traces to an extract item")
            for ref_idx, ref in enumerate(refs):
                if not (ref.get("location") or "").strip() or not (ref.get("anchor") or "").strip():
                    violations.append(f"{fieldname}[{idx}].evidence[{ref_idx}]: empty location or anchor")

    for idx, conflict in enumerate(brief.get("conflicts") or []):
        if len(conflict.get("positions") or []) < 2:
            violations.append(f"conflicts[{idx}]: needs at least two positions")
        if conflict.get("status") != "open":
            violations.append(
                f"conflicts[{idx}]: status {conflict.get('status')!r} — synthesis emits 'open'; "
                f"resolution is human-only (PRD DR-10)"
            )

    # Anchors must survive assembly untouched: they are what the Greek render re-anchors on.
    known_anchors = {
        (item.get("anchor") or "").strip()
        for extract in extracts.values()
        for f in gates.BRIEF_FIELDS
        for item in (extract.get(f) or [])
    }
    if known_anchors:
        for fieldname in gates.BRIEF_FIELDS:
            for idx, entry in enumerate(brief.get(fieldname) or []):
                for ref_idx, ref in enumerate(entry.get("evidence") or []):
                    anchor = (ref.get("anchor") or "").strip()
                    if anchor and anchor not in known_anchors:
                        violations.append(
                            f"{fieldname}[{idx}].evidence[{ref_idx}]: anchor {anchor[:40]!r} does not "
                            f"match any extract anchor — refs are copied verbatim (SYNTHESIS.md rule 1)"
                        )
    return violations


def synthesize(run_dir: Path, project_id: str, client_config: dict, classification: dict,
               sources, extracts: dict, glossary_path: Path, access_dirs) -> dict:
    output_file = Path(run_dir) / "brief.json"
    order = build_synthesis_order(run_dir, output_file, project_id, client_config, classification,
                                  sources, glossary_path)

    attempts, failed = _run_with_repair(
        "synthesize", order,
        lambda: check_synthesis(output_file, extracts),
        lambda v: "REPAIR ORDER — your brief failed the gate:\n" + "\n".join(f"  - {x}" for x in v)
                  + f"\n\nFix exactly these and rewrite {output_file}. Do not drop entries to make "
                    f"errors go away, and do not invent evidence to satisfy a check.",
        access_dirs, run_dir=Path(run_dir),
    )
    if failed:
        raise _fail("synthesize", failed)

    # The runner owns readiness. Injected here, then the full schema is enforced.
    brief = json.loads(output_file.read_text(encoding="utf-8"))
    brief["readiness"] = gates.compute_readiness_block(brief)
    output_file.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.enforce_sensitivity_tier((brief.get("meta") or {}).get("sensitivity_tier"))
    gates.validate_brief(brief)

    return {
        "output_file": str(output_file),
        "entry_count": sum(len(brief.get(f) or []) for f in gates.BRIEF_FIELDS),
        "conflict_count": len(brief.get("conflicts") or []),
        "open_question_count": len(brief.get("open_questions") or []),
        "readiness": brief["readiness"],
        "attempts": attempts,
    }


# ======================================================================================
# Step 7 — bilingual render
# ======================================================================================

CITATION_TAG_RE = re.compile(r"\[([^\]]+)\]")
CLAIM_SECTION_RE = re.compile(r"^##\s+(\d)\.")
STRUCTURAL_PREFIXES = ("#", ">", "|", "---", "**Client:**", "**Input coverage:**", "**Sources used:**")

#: Mirrors the frozen harness's T2.4 rule. Deliberately a second implementation: the runner
#: gates the artifact, the harness grades it independently, and an independent grader that
#: shares its subject's code is not independent.
def claim_lines(render: str) -> list:
    lines, in_claim_section = [], False
    for raw in render.splitlines():
        line = raw.strip()
        if line.startswith("##"):
            in_claim_section = bool(CLAIM_SECTION_RE.match(line))
            continue
        if not in_claim_section or not line or line.startswith(STRUCTURAL_PREFIXES):
            continue
        lines.append(line)
    return lines


def build_render_order(brief_file: Path, out_el: Path, out_en: Path, template_path: Path,
                       glossary_path: Path) -> str:
    return f"""RENDER WORK ORDER — Brief Builder pipeline step 7.

Produce both language documents from ONE object. Your governing rules are the TRANSLATION.md
content in your agent definition.

INPUT
  brief           : {brief_file}
  template        : {template_path}
  client_glossary : {glossary_path}

READ ONLY those three files. Do NOT read the source documents or the extracts — everything you
may say is already in the brief. Any file named `answer_key.json` is off limits.

OUTPUT — two files, at exactly these paths:
  greek   : {out_el}
  english : {out_en}

  Both follow the template section-for-section, including the Open Questions and Unresolved
  Conflicts sections. Open questions and conflicts are the product, not an appendix.

  A section with no entries still renders, with its note in BLOCKQUOTE form
  (`> No confirmed entries — see Open Questions.`). The blockquote marks it as structure
  rather than a claim, so it is not read as uncited prose. Never invent an entry to fill a
  section and never delete a section.

  Every claim line in sections 1–7 ends with at least one citation tag of the form
  `[<source_id> <location>]`, with source_id copied exactly from the brief's meta.sources —
  e.g. `[transcript_kickoff 00:14:32]`. One entry renders as one line; a claim line without a
  resolvable tag fails the run. Multiple supporting sources render as multiple tags.

  Glossary terms are character-exact in BOTH documents. Numbers render verbatim as they appear
  in `content` — no conversion, no totalling, no currency inference.

Reply with one line: the two paths written.
"""


def check_render(out_el: Path, out_en: Path, brief: dict, glossary: dict) -> list:
    violations = []
    for lang, path in (("el", out_el), ("en", out_en)):
        if not path.is_file():
            violations.append(f"no {lang} render at {path}")
    if violations:
        return violations

    known = {s["source_id"] for s in (brief.get("meta") or {}).get("sources") or []}
    brief_blob = json.dumps(brief, ensure_ascii=False)
    protected = [t["term"] for t in (glossary.get("terms") or [])
                 if t.get("rule") == "keep_latin" and t.get("term")]

    for lang, path in (("el", out_el), ("en", out_en)):
        render = path.read_text(encoding="utf-8")

        for line in claim_lines(render):
            tags = CITATION_TAG_RE.findall(line)
            if not tags:
                violations.append(f"{lang}: claim line with no citation tag — {line[:80]!r}")
            elif not any(any(sid in tag for sid in known) for tag in tags):
                violations.append(f"{lang}: citation tag names no known source — {line[:80]!r}")

        for term in protected:
            if term in brief_blob and term not in render:
                violations.append(f"{lang}: glossary term {term!r} is in the brief but missing from the render")

        # Language-neutral on purpose. The first version of this check looked for "?" and
        # failed a perfectly good Greek render, because Greek marks a question with ";".
        # The template gives both special sections a "⚠" heading, so that marker is the
        # signal — it survives translation, which is exactly what a bilingual gate needs.
        if brief.get("open_questions") and not any(
            line.startswith("##") and "⚠" in line for line in render.splitlines()
        ):
            violations.append(
                f"{lang}: brief has open questions but the render has no '⚠' section heading — "
                f"open questions and conflicts are the product, not an appendix"
            )
    return violations


def render(run_dir: Path, brief: dict, glossary_path: Path, access_dirs) -> dict:
    out_el = Path(run_dir) / "brief_el.md"
    out_en = Path(run_dir) / "brief_en.md"
    brief_file = Path(run_dir) / "brief.json"
    template_path = gates.REPO_ROOT / "templates" / "northlight_client_brief.md"
    glossary = json.loads(Path(glossary_path).read_text(encoding="utf-8"))

    order = build_render_order(brief_file, out_el, out_en, template_path, glossary_path)
    attempts, failed = _run_with_repair(
        "render", order,
        lambda: check_render(out_el, out_en, brief, glossary),
        lambda v: "REPAIR ORDER — your renders failed the gate:\n" + "\n".join(f"  - {x}" for x in v)
                  + "\n\nFix exactly these. Do not delete content to silence a check: a missing "
                    "entry is a worse failure than an uncited one.",
        access_dirs, run_dir=Path(run_dir),
    )
    if failed:
        raise _fail("render", failed)

    return {
        "el_file": str(out_el),
        "en_file": str(out_en),
        "el_chars": len(out_el.read_text(encoding="utf-8")),
        "en_chars": len(out_en.read_text(encoding="utf-8")),
        "attempts": attempts,
    }
