"""Pipeline step 6 — synthesis.

`synthesize` never populates `readiness`; the runner computes it (SYNTHESIS.md rule 8).

The gate `check_synthesis` is a fixed sequence of named rules (`SYNTHESIS_RULES`), each a pure
function of the brief and the extracts that returns its violations. The sequence order is the
order violations are reported in, and it is part of the repair loop's contract.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional

from pipeline import PIPELINE_VERSION, agents, clock, gates, quality, records
from pipeline.money import money_figures
from pipeline.stage_common import stage_failure


def build_synthesis_order(run_dir: Path, output_file: Path, project_id: str, client_config: dict,
                          classification: dict, sources, glossary_path: Path) -> str:
    """The synthesis work order: extracts in, one canonical brief out, meta values fixed."""
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
    created_ts                = {clock.timestamp('seconds')}
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


# --------------------------------------------------------------------------------------
# The synthesis gate's rules, in reporting order
# --------------------------------------------------------------------------------------


def rule_runner_owned_fields(brief: dict, extracts: dict) -> list:
    """Readiness is the runner's (SYNTHESIS.md rule 8) and sign-off is a human's (PRD DR-8)."""
    violations = []
    if "readiness" in brief:
        violations.append(
            "brief contains a `readiness` block — that field is computed by the runner, "
            "not by the model (SYNTHESIS.md rule 8). Remove it."
        )
    if (brief.get("signoff") or {}).get("status") != "draft":
        violations.append("signoff.status must be 'draft' — sign-off is a human act (PRD DR-8)")
    return violations


def rule_entry_evidence(brief: dict, extracts: dict) -> list:
    """Every field entry carries evidence, and every ref has a location and an anchor."""
    violations = []
    for fieldname in gates.BRIEF_FIELDS:
        for idx, entry in enumerate(brief.get(fieldname) or []):
            refs = entry.get("evidence") or []
            if not refs:
                violations.append(f"{fieldname}[{idx}]: no evidence — every claim traces to an extract item")
            for ref_idx, ref in enumerate(refs):
                if not (ref.get("location") or "").strip() or not (ref.get("anchor") or "").strip():
                    violations.append(f"{fieldname}[{idx}].evidence[{ref_idx}]: empty location or anchor")
    return violations


def rule_conflict_structure(brief: dict, extracts: dict) -> list:
    """A conflict has at least two positions and is emitted 'open' (resolution is human-only, DR-10)."""
    violations = []
    for idx, conflict in enumerate(brief.get("conflicts") or []):
        if len(conflict.get("positions") or []) < 2:
            violations.append(f"conflicts[{idx}]: needs at least two positions")
        if conflict.get("status") != "open":
            violations.append(
                f"conflicts[{idx}]: status {conflict.get('status')!r} — synthesis emits 'open'; "
                f"resolution is human-only (PRD DR-10)"
            )
    return violations


def rule_conflict_consistency(brief: dict, extracts: dict) -> list:
    """A field carrying an open conflict must not read as settled (SYNTHESIS.md rule 4).

    The comparison is ANCHOR-level — a position counts as "asserted by the field" only when
    some entry's evidence carries that position's exact anchor. Source-level matching was tried
    first and flagged legal briefs: an entry citing a position's *source* for an undisputed
    aspect of the field is not taking sides. Anchor matching is also what a token gesture
    cannot satisfy — an entry with an unrelated anchor from the other side's source leaves the
    missing position missing.
    """
    violations = []
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
    return violations


def rule_superseded_claims(brief: dict, extracts: dict) -> list:
    """A claim its own speaker retracted is `conditional` or absent, never firm (rules 4 & 7).

    When a transcript contradicts itself, the later statement supersedes — a retraction or a
    correction. An entry anchored to the EARLIER side, without the later side's anchor beside it
    and without a `conditional` qualifier, presents a superseded claim as firm. Deterministic
    form of trap X1's lesson (it slipped on 3 of 5 synthesis rolls before this gate). Ordering
    is only trusted where both sides carry parseable [hh:mm:ss] timestamps. A retraction is
    SAME-speaker (adversarial review, probe-verified): a two-speaker disagreement inside one
    source is a dispute — conflict material under rule 4, never demoted by recency. Anchor
    matching is per-source (identical quote text in another source must not collide), and the
    X1 contour applies: an entry citing the retracted side stays `conditional` even when it also
    cites the retraction itself. Known semantic blind spot (shared with the anchor sweep): a
    paraphrased retracted claim re-anchored to an unrelated legitimate anchor is invisible to
    every deterministic check here.
    """
    violations = []
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
    return violations


def _known_anchors(extracts: dict) -> set:
    """Every legitimate source anchor: the 7 brief fields AND each extract's internal_conflicts.

    A within-source contradiction the extractor recorded there (the retracted OOH/metro item is
    the canonical case) is evidence synthesis may surface as a conditional entry or a conflict.
    Omitting internal_conflicts anchors falsely flags a byte-exact copy as "altered", which
    non-deterministically fails synthesis whenever the model carries such an item forward.
    """
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
    return known_anchors


def rule_anchor_integrity(brief: dict, extracts: dict) -> list:
    """Anchors survive assembly untouched: they are what the Greek render re-anchors on (rule 1)."""
    violations = []
    known_anchors = _known_anchors(extracts)
    if not known_anchors:
        return violations

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
    return violations


def rule_currency_discipline(brief: dict, extracts: dict) -> list:
    """A currency-marked figure traces to source evidence that wrote that mark on it (rule 5).

    Applies to entries and open questions. Conflicts are exempt — quoting a disputed figure
    verbatim is their whole job (mirroring the harness trap's own conflict exemption). The
    trace-set is extract item values and anchors, which are citation-verified against the
    source; extract open-question prose is model-authored and deliberately NOT trusted as
    provenance.
    """
    violations = []
    sourced_money = set()
    for extract in extracts.values():
        for _path, item in gates.extract_items(extract):
            sourced_money |= money_figures(item.get("value") or "")
            sourced_money |= money_figures(item.get("anchor") or "")

    def _scan_money(text: str, path: str) -> None:
        for figure in sorted(money_figures(text or "")):
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
    return violations


def rule_schema(brief: dict, extracts: dict) -> list:
    """Schema violations are visible INSIDE the gate, where the repair loop can still act.

    The earlier design validated only after the loop had declared success, so a schema-invalid
    brief (a bad enum, a missing meta key) died with zero repair rounds and a repair log whose
    last attempt read "no violations". The readiness block is runner-owned and injected after
    the gate, so the probe carries the computed block; the real injection and the post-loop
    validation in `synthesize` are unchanged.
    """
    probe = dict(brief)
    probe["readiness"] = gates.compute_readiness_block(brief)
    try:
        gates.validate_brief(probe)
    except gates.SchemaValidationError as exc:
        return list(exc.errors)
    return []


#: A synthesis rule: `(brief, extracts) -> violations`, pure, no I/O.
SynthesisRule = Callable[[dict, dict], list]

#: The synthesis gate, in reporting order.
SYNTHESIS_RULES: tuple[SynthesisRule, ...] = (
    rule_runner_owned_fields,
    rule_entry_evidence,
    rule_conflict_structure,
    rule_conflict_consistency,
    rule_superseded_claims,
    rule_anchor_integrity,
    rule_currency_discipline,
    rule_schema,
)


def check_synthesis(path: Path, extracts: dict) -> list:
    """Gate the brief *before* the readiness block is injected.

    Schema validation happens after injection (the schema requires `readiness`), so this pass
    checks the things synthesis itself is answerable for: shape, evidence, conflict structure,
    and that it did not help itself to the readiness verdict. Each rule is a named function in
    `SYNTHESIS_RULES`; violations are reported in rule order.
    """
    if not path.is_file():
        return [f"no file written at {path}"]
    try:
        brief = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]

    violations = []
    for rule in SYNTHESIS_RULES:
        violations.extend(rule(brief, extracts))
    return violations


def synthesize(run_dir: Path, project_id: str, client_config: dict, classification: dict,
               sources, extracts: dict, glossary_path: Path, access_dirs,
               readiness_policy: Optional[dict] = None) -> dict:
    """Run the synthesize subagent through its gate, inject readiness, validate, write the ledger."""
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
        raise stage_failure("synthesize", failed)

    # The runner owns readiness. Injected here, then the full schema is enforced.
    # `readiness_policy` is only ever non-None under the runner's --demo-profile flag; the
    # production path always computes with the shipped config/readiness_policy.json.
    brief = json.loads(output_file.read_text(encoding="utf-8"))
    brief["readiness"] = gates.compute_readiness_block(brief, readiness_policy)
    output_file.write_text(json.dumps(brief, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    gates.enforce_sensitivity_tier((brief.get("meta") or {}).get("sensitivity_tier"))
    gates.validate_brief(brief)
    records.write_json(Path(run_dir) / "coverage_ledger.json", {
        "boundary": "Evidence-link accounting; human review must confirm meaning and source completeness",
        "records": quality.coverage(brief, extracts),
    })

    return {
        "output_file": str(output_file),
        "entry_count": sum(len(brief.get(f) or []) for f in gates.BRIEF_FIELDS),
        "conflict_count": len(brief.get("conflicts") or []),
        "open_question_count": len(brief.get("open_questions") or []),
        "readiness": brief["readiness"],
        "attempts": attempts,
    }
