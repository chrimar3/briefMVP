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

from pipeline import PIPELINE_VERSION, agents, gates


class StageError(gates.GateError):
    """A stage did not produce an acceptable artifact."""


class HaltForHuman(gates.GateError):
    """The pipeline stopped and asked, rather than guessing (DR-9, TRANSCRIPTS.md §4).

    Distinct from StageError on purpose: this is the system working as designed, and the run
    manifest should not read as if something broke.
    """


def _fail(agent: str, violations: list) -> StageError:
    listed = "\n".join(f"  - {v}" for v in violations)
    return StageError(f"{agent}: no acceptable artifact after {agents.MAX_ATTEMPTS} attempts:\n{listed}")


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

    attempts, failed = agents.run_gated(
        "classify", order,
        lambda: check_classification(output_file, client_config),
        lambda v: agents.repair_order("classification", v, f"Fix exactly these and rewrite {output_file}."),
        access_dirs, stage="classify", site="classify", run_dir=Path(run_dir),
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
#: correctly-annotated transcript gets rejected for a stray space. The body tolerates one level
#: of nested brackets ("[FIDELITY: glossary-match [key visual]]") — an annotation quoting a
#: bracketed term must strip whole, not leave its own residue. The check this serves is
#: "no character of the transcript was altered", and that still holds exactly.
FIDELITY_ANNOTATION_RE = re.compile(r"\s*\[FIDELITY:(?:[^\[\]]|\[[^\]]*\])*\]")
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
    attempts, failed = agents.run_gated(
        "fidelity-check", order,
        lambda: check_fidelity(report_file, annotated_file, source.text),
        lambda v: agents.repair_order("fidelity output", v, "Fix exactly these and rewrite both files."),
        access_dirs, stage="fidelity-check", site=source.source_id, run_dir=Path(run_dir),
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

#: Currency marks the money gate recognises when ATTACHED TO A FIGURE (€50.000, EUR 50k,
#: 90 €). The word «ευρώ» in prose is deliberately not a mark — asking in words is the
#: CORRECT behavior the gate must never punish (SYNTHESIS.md rule 5). Never extend these
#: with fixture-specific patterns: that would be tuning against the answer key.
_MONEY_PREFIX_RE = re.compile(r"(?:€|\bEUR\b)\s*(\d[\d.,]*)\s*([kK]\b)?")
_MONEY_SUFFIX_RE = re.compile(r"(\d[\d.,]*)\s*([kK])?\s*€")


def _money_figures(text: str) -> set:
    """Canonical integer for every currency-marked figure in `text`.

    Separator-insensitive (€50.000 ≡ €50,000) and k-aware (€50k ≡ €50.000), so a faithful
    reformatting of a sourced figure never trips the gate. Decimal forms (€1,5 εκατ.) are
    out of scope by design — precision over recall; the frozen harness stays the backstop
    for shapes this normaliser does not know.
    """
    found = set()
    for figure, k in _MONEY_PREFIX_RE.findall(text) + _MONEY_SUFFIX_RE.findall(text):
        digits = re.sub(r"[.,]", "", figure)
        if digits.isdigit():
            found.add(int(digits) * (1000 if k else 1))
    return found


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
    pipeline_version          = {PIPELINE_VERSION}
    sources                   = one entry per source above

  OMIT the `readiness` key entirely. The runner computes it deterministically and injects it;
  a model-authored readiness verdict is a defect the harness will catch (SYNTHESIS.md rule 8).

  `signoff` is exactly {{"status": "draft"}}. The agent never signs off (PRD DR-8).

  Conflict candidates are NOT conflicts — they are fields where several sources spoke. Decide
  which are genuine contradictions, emit those as conflicts[] with both positions and their
  evidence, status "open". Never resolve one, never prefer a source, never merge two figures.

  Evidence refs are copied byte-exact from the extracts — anchors are never translated,
  normalised or trimmed. They are the render stage's Greek fidelity anchor.

{agents.OUTPUT_DISCIPLINE}

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

    # Conflict-consistency (SYNTHESIS.md rule 4, machine-checked): a field carrying an open
    # conflict must not read as settled. The comparison is ANCHOR-level — a position counts as
    # "asserted by the field" only when some entry's evidence carries that position's exact
    # anchor. Source-level matching was tried first and flagged legal briefs: an entry citing a
    # position's *source* for an undisputed aspect of the field is not taking sides. Anchor
    # matching is also what a token gesture cannot satisfy — an entry with an unrelated anchor
    # from the other side's source leaves the missing position missing.
    for idx, conflict in enumerate(brief.get("conflicts") or []):
        if conflict.get("status") != "open":
            continue
        if conflict.get("field") not in gates.BRIEF_FIELDS:
            violations.append(
                f"conflicts[{idx}]: field {conflict.get('field')!r} is not one of "
                f"{list(gates.BRIEF_FIELDS)} — a conflict attaches to the exact field it "
                f"disputes (SYNTHESIS.md rule 4); rename the field, do not invent one"
            )
            continue
        entry_anchors = {((ref or {}).get("anchor") or "").strip()
                        for entry in (brief.get(conflict["field"]) or [])
                        for ref in (entry.get("evidence") or [])} - {""}
        anchored = [((p.get("evidence") or {}).get("anchor") or "").strip()
                    for p in (conflict.get("positions") or [])]
        present = [a for a in anchored if a and a in entry_anchors]
        missing = [a for a in anchored if a and a not in entry_anchors]
        if present and missing:
            violations.append(
                f"{conflict['field']}: the field asserts the position anchored "
                f"{present[0][:40]!r} while competing position(s) anchored "
                f"{[a[:40] for a in missing]} appear only inside conflicts[{idx}] — "
                f"resolution by omission (SYNTHESIS.md rule 4). Add an entry stating each "
                f"missing position's claim, copying that position's evidence ref verbatim; "
                f"keep every existing entry."
            )

    # Superseded-within-source (SYNTHESIS.md rules 4 & 7, machine-checked): when a transcript
    # contradicts itself, the later statement supersedes — a retraction or a correction. An
    # entry anchored to the EARLIER side, without the later side's anchor beside it and
    # without a `conditional` qualifier, presents a superseded claim as firm. Deterministic
    # form of trap X1's lesson (it slipped on 3 of 5 synthesis rolls before this gate).
    # Ordering is only trusted where both sides carry parseable [hh:mm:ss] timestamps.
    # A retraction is SAME-speaker (adversarial review, probe-verified): a two-speaker
    # disagreement inside one source is a dispute — conflict material under rule 4, never
    # demoted by recency. Anchor matching is per-source (identical quote text in another
    # source must not collide), and the X1 contour applies: an entry citing the retracted
    # side stays `conditional` even when it also cites the retraction itself. Known semantic
    # blind spot (shared with the anchor sweep): a paraphrased retracted claim re-anchored
    # to an unrelated legitimate anchor is invisible to every deterministic check here.
    for conflict_source_id, extract in (extracts or {}).items():
        for conflict in extract.get("internal_conflicts") or []:
            side_a, side_b = conflict.get("value_a") or {}, conflict.get("value_b") or {}
            speaker_a = (side_a.get("speaker_or_author") or "").strip()
            speaker_b = (side_b.get("speaker_or_author") or "").strip()
            if not speaker_a or speaker_a != speaker_b:
                continue
            loc_a = (side_a.get("location") or "").strip()
            loc_b = (side_b.get("location") or "").strip()
            if loc_a.count(":") != loc_b.count(":"):
                continue  # mixed [mm:ss]/[hh:mm:ss] formats cannot be ordered safely
            secs_a, secs_b = _timestamp_seconds(loc_a), _timestamp_seconds(loc_b)
            if secs_a is None or secs_b is None or secs_a == secs_b:
                continue
            earlier, later = (side_a, side_b) if secs_a < secs_b else (side_b, side_a)
            if (later.get("qualifier") or "") == "conditional":
                # A later HEDGE ("might be revisited, but work with it") qualifies the
                # earlier commitment without superseding it — only a firm statement retracts.
                continue
            earlier_anchor = (earlier.get("anchor") or "").strip()
            fieldname = conflict.get("field")
            if not earlier_anchor or fieldname not in gates.BRIEF_FIELDS:
                # Only the conflict's OWN field is policed — a mandatories no-go recording
                # the withdrawal ("not to be pursued", firm) is legitimate downstream use of
                # a retraction, measured on the stored corpus. The frozen harness X1 remains
                # the backstop for anything an unrecognized field string lets slip here.
                continue
            for idx, entry in enumerate(brief.get(fieldname) or []):
                if entry.get("qualifier") == "conditional":
                    continue
                cites_retracted = any(
                    ((ref or {}).get("anchor") or "").strip() == earlier_anchor
                    and ((ref or {}).get("source_id") or "").strip() == conflict_source_id
                    for ref in (entry.get("evidence") or []))
                if cites_retracted:
                    violations.append(
                        f"{fieldname}[{idx}]: anchored to {earlier_anchor[:40]!r} — a claim "
                        f"its own speaker retracted at {later.get('location')} in "
                        f"{conflict_source_id} — yet qualifier is "
                        f"{entry.get('qualifier')!r}. A retracted claim is `conditional` "
                        f"or absent in its own field, never firm, even when the retraction "
                        f"is cited beside it (SYNTHESIS.md rules 4 & 7): set qualifier to "
                        f"'conditional' and note the retraction in the content."
                    )

    # Anchors must survive assembly untouched: they are what the Greek render re-anchors on.
    # The set of legitimate source anchors spans the 7 brief fields AND each extract's
    # internal_conflicts — a within-source contradiction the extractor recorded there (the
    # retracted OOH/metro item is the canonical case) is evidence synthesis may surface as a
    # conditional entry or a conflict. Omitting internal_conflicts anchors here falsely flags a
    # byte-exact copy as "altered", which non-deterministically fails synthesis whenever the
    # model chooses to carry a retracted/conflicting item forward.
    known_anchors = {
        (item.get("anchor") or "").strip()
        for extract in extracts.values()
        for f in gates.BRIEF_FIELDS
        for item in (extract.get(f) or [])
    }
    for extract in extracts.values():
        for conflict in extract.get("internal_conflicts") or []:
            for side in ("value_a", "value_b"):
                item = conflict.get(side) or {}
                anchor = (item.get("anchor") or "").strip()
                if anchor:
                    known_anchors.add(anchor)
    if known_anchors:
        def _sweep(refs: list, path: str) -> None:
            for ref_idx, ref in enumerate(refs):
                anchor = ((ref or {}).get("anchor") or "").strip()
                if anchor and anchor not in known_anchors:
                    violations.append(
                        f"{path}[{ref_idx}]: anchor {anchor[:40]!r} does not "
                        f"match any extract anchor — refs are copied verbatim (SYNTHESIS.md rule 1)"
                    )

        for fieldname in gates.BRIEF_FIELDS:
            for idx, entry in enumerate(brief.get(fieldname) or []):
                _sweep(entry.get("evidence") or [], f"{fieldname}[{idx}].evidence")
        # Conflict positions and open-question links carry evidence refs too — and the Greek
        # render re-anchors on all of them, so the sweep covers every ref the brief can hold.
        for idx, conflict in enumerate(brief.get("conflicts") or []):
            _sweep([p.get("evidence") for p in (conflict.get("positions") or [])],
                   f"conflicts[{idx}].positions")
        for idx, question in enumerate(brief.get("open_questions") or []):
            _sweep(question.get("linked_evidence") or [], f"open_questions[{idx}].linked_evidence")

    # Currency discipline (SYNTHESIS.md rule 5, machine-checked): a currency-marked figure
    # in an entry or open question must trace to source evidence that wrote that mark on
    # that figure. Conflicts are exempt — quoting a disputed figure verbatim is their whole
    # job (mirroring the harness trap's own conflict exemption). The trace-set is extract
    # item values and anchors, which are citation-verified against the source; extract
    # open-question prose is model-authored and deliberately NOT trusted as provenance.
    sourced_money = set()
    for extract in extracts.values():
        for _path, item in gates._extract_items(extract):
            sourced_money |= _money_figures(item.get("value") or "")
            sourced_money |= _money_figures(item.get("anchor") or "")

    def _scan_money(text: str, path: str) -> None:
        for figure in sorted(_money_figures(text or "")):
            if figure not in sourced_money:
                violations.append(
                    f"{path}: currency-marked figure (≈{figure}) has no source that wrote "
                    f"that mark on it — rewrite the figure in words or drop the unsourced "
                    f"mark; do NOT strip marks that trace to a source (SYNTHESIS.md rule 5)"
                )

    for fieldname in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(brief.get(fieldname) or []):
            _scan_money(entry.get("content"), f"{fieldname}[{idx}].content")
    for idx, question in enumerate(brief.get("open_questions") or []):
        for key in ("gap", "why_it_matters", "suggested_question_for_client"):
            _scan_money(question.get(key), f"open_questions[{idx}].{key}")

    # Schema violations must be visible INSIDE the gate, where the repair loop can still act.
    # The earlier design validated only after the loop had declared success, so a schema-invalid
    # brief (a bad enum, a missing meta key) died with zero repair rounds and a repair log whose
    # last attempt read "no violations". The readiness block is runner-owned and injected after
    # the gate, so the probe carries the computed block; the real injection and the post-loop
    # validation in `synthesize` are unchanged.
    probe = dict(brief)
    probe["readiness"] = gates.compute_readiness_block(brief)
    try:
        gates.validate_brief(probe)
    except gates.SchemaValidationError as exc:
        violations.extend(exc.errors)
    return violations


def synthesize(run_dir: Path, project_id: str, client_config: dict, classification: dict,
               sources, extracts: dict, glossary_path: Path, access_dirs,
               readiness_policy: Optional[dict] = None) -> dict:
    output_file = Path(run_dir) / "brief.json"
    order = build_synthesis_order(run_dir, output_file, project_id, client_config, classification,
                                  sources, glossary_path)

    attempts, failed = agents.run_gated(
        "synthesize", order,
        lambda: check_synthesis(output_file, extracts),
        lambda v: agents.repair_order(
            "brief", v,
            f"Fix exactly these and rewrite {output_file}. Do not drop entries to make "
            f"errors go away, and do not invent evidence to satisfy a check."),
        access_dirs, stage="synthesize", site="synthesize", run_dir=Path(run_dir),
    )
    if failed:
        raise _fail("synthesize", failed)

    # The runner owns readiness. Injected here, then the full schema is enforced.
    # `readiness_policy` is only ever non-None under the runner's --demo-profile flag; the
    # production path always computes with the shipped config/readiness_policy.json.
    brief = json.loads(output_file.read_text(encoding="utf-8"))
    brief["readiness"] = gates.compute_readiness_block(brief, readiness_policy)
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

{agents.OUTPUT_DISCIPLINE}

Reply with one line: the two paths written.
"""


_TIMESTAMP_LOC_RE = re.compile(r"^\[(\d{1,2}):(\d{2})(?::(\d{2}))?\]$")


def _timestamp_seconds(location) -> Optional[int]:
    """Parse a transcript location like '[00:08:34]' to seconds; None for anything else.
    Numeric, not lexicographic — '[9:05]' must order after '[00:08:34]'."""
    match = _TIMESTAMP_LOC_RE.match((location or "").strip())
    if not match:
        return None
    h_or_m, m_or_s, maybe_s = match.groups()
    parts = [int(h_or_m), int(m_or_s)] + ([int(maybe_s)] if maybe_s is not None else [])
    if len(parts) == 2:
        parts = [0] + parts
    return parts[0] * 3600 + parts[1] * 60 + parts[2]


def _digit_runs(text: str) -> set:
    """Digit sequences (≥2 digits) — the translation-invariant number fingerprint used by the
    render no-invention check. Separators are joined ONLY in true thousands grouping
    (1–3 digits then groups of exactly 3: "12,500" → "12500"); anything else splits on the
    separator, so Greek dotted dates ("15.9.2026") yield {"15","2026"} instead of a bogus
    seven-digit "figure" that would flag a faithful render."""
    runs = set()
    for match in re.findall(r"\d(?:[\d.,]*\d)?", text or ""):
        if re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+", match):
            runs.add(re.sub(r"[.,]", "", match))
        else:
            runs.update(part for part in re.split(r"[.,]", match) if len(part) >= 2)
    return runs


def _warning_region(render: str) -> str:
    """The body of every ⚠ section — where open questions and conflicts must land."""
    kept, in_warn = [], False
    for line in render.splitlines():
        if line.strip().startswith("##"):
            in_warn = "⚠" in line
            continue
        if in_warn:
            kept.append(line)
    return "\n".join(kept)


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

        # No-invention (TRANSLATION.md rule 3, machine-checked): rendering adds a language,
        # never content. Free prose can be legitimately rephrased, so this check pins the
        # token classes that survive translation byte-for-byte — protected glossary terms,
        # digit runs, and currency marks — and requires each one appearing in a claim or ⚠
        # line to exist in the brief's CONTENT strings (entries, conflict statements, open
        # questions). The whole-object blob is deliberately not the whitelist: evidence
        # locations and meta dates would launder any small number as a "known" figure.
        # Only citation tags naming a known source are stripped — stripping every bracketed
        # span would let an invented figure hide inside a gloss.
        content_blob = "\n".join(
            [(e.get("content") or "") for f in gates.BRIEF_FIELDS for e in (brief.get(f) or [])]
            + [(p.get("statement") or "") for c in (brief.get("conflicts") or [])
               for p in (c.get("positions") or [])]
            + [(c.get("resolution") or "") for c in (brief.get("conflicts") or [])]
            + [(q.get(k) or "") for q in (brief.get("open_questions") or [])
               for k in ("gap", "why_it_matters", "suggested_question_for_client")]
        )
        claim_text = "\n".join(claim_lines(render)) + "\n" + _warning_region(render)
        bare_claims = CITATION_TAG_RE.sub(
            lambda m: " " if any(sid in m.group(0) for sid in known) else m.group(0), claim_text)
        for term in protected:
            if term.lower() in bare_claims.lower() and term.lower() not in content_blob.lower():
                violations.append(
                    f"{lang}: render claims glossary term {term!r} but no brief content string "
                    f"uses it — a render adds no content the brief does not carry "
                    f"(TRANSLATION.md rule 3)"
                )
        content_digits = _digit_runs(content_blob)
        content_money = _money_figures(content_blob)
        for line in bare_claims.splitlines():
            stripped = line.strip()
            if (not stripped or stripped.startswith(STRUCTURAL_PREFIXES)
                    or re.fullmatch(r"\*\*[^*]+\*\*:?", stripped)):
                # Structural micro-headers ("**OQ-11 — Audiences**") are labels, not claims —
                # their ordinals are render plumbing, exactly like list numbering.
                continue
            body = re.sub(r"^\s*\d{1,3}[.)]\s+", "", line)
            for run in sorted(_digit_runs(body) - content_digits):
                violations.append(
                    f"{lang}: figure {run!r} appears in a render claim but in no brief content "
                    f"string — remove the figure; renders never introduce numbers, in digits "
                    f"or in words (TRANSLATION.md rule 3): {line[:80]!r}"
                )
            for figure in sorted(_money_figures(body) - content_money):
                violations.append(
                    f"{lang}: currency-marked figure (≈{figure}) in a render claim has no such "
                    f"mark in any brief content string — remove the mark or the figure "
                    f"(TRANSLATION.md rule 3): {line[:80]!r}"
                )

        # Language-neutral on purpose. The first version of this check looked for "?" and
        # failed a perfectly good Greek render, because Greek marks a question with ";".
        # The template gives both special sections a "⚠" heading, so that marker is the
        # signal — it survives translation, which is exactly what a bilingual gate needs.
        # Coverage inside the region is checked the same way: open questions are numbered
        # (template contract), so the numbered-item count is translation-invariant; conflict
        # positions carry source_ids, which survive translation character-exact. Both checks
        # are ≥-shaped — a render may elaborate, it may not omit.
        open_qs = brief.get("open_questions") or []
        brief_conflicts = brief.get("conflicts") or []
        if open_qs or brief_conflicts:
            if not any(line.startswith("##") and "⚠" in line for line in render.splitlines()):
                violations.append(
                    f"{lang}: brief has open questions or conflicts but the render has no '⚠' "
                    f"section heading — open questions and conflicts are the product, not an appendix"
                )
            else:
                region = _warning_region(render)
                if open_qs:
                    numbered = len(re.findall(r"^\s*\d{1,3}[.)]\s", region, re.MULTILINE))
                    if numbered < len(open_qs):
                        violations.append(
                            f"{lang}: render numbers {numbered} item(s) in the ⚠ sections but the "
                            f"brief carries {len(open_qs)} open question(s) — every question "
                            f"reaches both renders"
                        )
                for idx, conflict in enumerate(brief_conflicts):
                    for p_idx, position in enumerate(conflict.get("positions") or []):
                        sid = ((position.get("evidence") or {}).get("source_id") or "")
                        if sid and sid not in region:
                            violations.append(
                                f"{lang}: conflicts[{idx}] position {p_idx} cites source {sid!r} "
                                f"but that source never appears in the ⚠ region — both sides of "
                                f"a conflict render with their citations"
                            )
    return violations


def render(run_dir: Path, brief: dict, glossary_path: Path, access_dirs,
           model_override: Optional[str] = None) -> dict:
    """`model_override` swaps the model alias for an A/B experiment (cost-audit C3), exactly
    like the Tier-4 creative A/B — the default path always uses the frontmatter model, and
    adopting a different one is a human routing decision (CLAUDE.md)."""
    out_el = Path(run_dir) / "brief_el.md"
    out_en = Path(run_dir) / "brief_en.md"
    brief_file = Path(run_dir) / "brief.json"
    template_path = gates.REPO_ROOT / "templates" / "northlight_client_brief.md"
    glossary = json.loads(Path(glossary_path).read_text(encoding="utf-8"))

    order = build_render_order(brief_file, out_el, out_en, template_path, glossary_path)
    attempts, failed = agents.run_gated(
        "render", order,
        lambda: check_render(out_el, out_en, brief, glossary),
        lambda v: agents.repair_order(
            "renders", v,
            "Fix exactly these. Do not delete content to silence a check: a missing "
            "entry is a worse failure than an uncited one."),
        access_dirs, stage="render", site="render", run_dir=Path(run_dir),
        model_override=model_override,
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
