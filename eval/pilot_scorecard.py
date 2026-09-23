"""Validate and summarize recorded pilot data, and evaluate every SCORECARD.md §4 pass rule.

Missing is never zero and never a pass; examples never count. Each rule reports
pass / fail / insufficient_data per phase (end of week 3 = retro, end of week 4 = live).
Reported-only measures (net team minutes, the retro side-by-side, the agency-steps subset of
review time, the timed baseline check, canonical survival) are summarised under
`pass_rules.reported`; none of them is gated.

    python3 eval/pilot_scorecard.py SCORECARD.csv [--output report.json]
    python3 eval/pilot_scorecard.py --draft DRAFT.md --final FINAL.md
    python3 eval/pilot_scorecard.py --draft-dir PILOT/BRIEF/draft --approved-run RUN

The last form is the survival measure of SCORECARD.md §2: the first draft archived before
review against the renders and brief.json that `agency approve` bound in the run directory.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import json
import math
from collections.abc import Iterable
from pathlib import Path
from statistics import mean, median
from typing import Any, Callable, Optional

METRICS = ("assembly_min", "review_min", "total_attention_min", "operator_min", "strategy_min", "creative_min",
           "production_min", "total_team_min", "survival_en_pct", "survival_el_pct", "el_register_1to5", "ce_total",
           "creative_rework_requests_q1", "client_revision_rounds_q1", "baseline_min", "baseline_timed_min",
           "baseline_team_min", "agency_steps_min", "survival_canonical_pct")
CLASSES = ("oq_real", "oq_duplicate", "oq_answered_in_sources", "oq_not_worth_asking")
#: Retro side-by-side against the brief the agency actually wrote (SCORECARD.md §2): integer
#: counts recorded by the lead after sign-off on retro rows. Reported, never gated.
SIDE_BY_SIDE = ("human_conflicts_missed", "human_gaps_unasked", "draft_facts_missing", "human_facts_unsourced")
#: SCORECARD.md §6: a cell not measured reads `not_recorded`; no cell carries any other text,
#: so 'n/a' or any other placeholder is a data error, never a silent missing value.
MISSING = (None, "", "not_recorded")


def number(row: dict, key: str) -> Optional[float]:
    """A nonnegative finite number, or None when the cell is missing. Anything else is a data error."""
    raw: Any = row.get(key)
    if raw in MISSING:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:  # TypeError: a non-string, non-number cell (e.g. a list)
        raise ValueError(f"{row.get('brief_id', '?')}: {key} must be numeric or not_recorded") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be finite and nonnegative")
    if key.endswith("_pct") and value > 100:
        raise ValueError(f"{key} must be in 0–100")
    if key == "el_register_1to5" and (value not in range(1, 6)):
        raise ValueError("Greek register must be an integer in 1–5")
    if key in SIDE_BY_SIDE and value != int(value):
        raise ValueError(f"{row.get('brief_id', '?')}: {key} must be an integer count")
    return value


def _summarize(rows: list) -> dict[str, Any]:
    pilots: list[dict[str, Any]] = []
    for row in rows:
        if row.get("row_type") == "EXAMPLE":
            continue
        if row.get("row_type") != "PILOT":
            raise ValueError("row_type must be EXAMPLE or PILOT")
        pilots.append(row)
    totals: float = 0
    real: float = 0
    precision_rows = 0
    per_brief: list[dict[str, Any]] = []
    team_fields = ("total_attention_min", "operator_min", "strategy_min", "creative_min", "production_min")
    for row in pilots:
        for total_key, components in (("total_attention_min", ("assembly_min", "review_min")),
                                      ("total_team_min", team_fields)):
            stated = number(row, total_key)
            parts = [number(row, k) for k in components]
            measured_parts = [v for v in parts if v is not None]
            if (stated is not None and len(measured_parts) == len(parts)
                    and not math.isclose(stated, sum(measured_parts))):
                raise ValueError(f"{total_key} does not equal its measured components")
        total = number(row, "oq_total")
        classes = [number(row, k) for k in CLASSES]
        if any(v is not None and v != int(v) for v in [total] + classes):
            raise ValueError("question class counts must be integers")
        precision = None
        if total is not None and all(v is not None for v in classes):
            counts = [v for v in classes if v is not None]  # == classes here; typed without None
            if not math.isclose(total, sum(counts)) or any(v != int(v) for v in [total] + counts):
                raise ValueError("question class counts must be integers summing to oq_total")
            totals += total
            real += counts[0]
            precision_rows += 1
            precision = 100 * counts[0] / total if total else None
        per_brief.append({"brief_id": row.get("brief_id", "not_recorded"),
                          "precision_pct": precision})
        steps, review = number(row, "agency_steps_min"), number(row, "review_min")
        if steps is not None and review is not None and steps > review:
            raise ValueError(f"{row.get('brief_id', '?')}: agency_steps_min is a subset of review_min "
                             "and cannot exceed it")
        for key in SIDE_BY_SIDE:
            number(row, key)
    metrics: dict[str, dict[str, Any]] = {}
    for key in METRICS:
        values = [number(row, key) for row in pilots]
        observed = [v for v in values if v is not None]
        metrics[key] = {"measured": len(observed), "missing": len(values) - len(observed),
                        "mean": mean(observed) if observed else None,
                        "median": median(observed) if observed else None}
    rework: dict[str, int] = {}
    for row in pilots:
        reason = row.get("return_reason", "")
        if reason not in MISSING:
            rework[reason] = rework.get(reason, 0) + 1
    accepted = [row.get("first_handoff_accepted") for row in pilots
                if row.get("first_handoff_accepted") not in MISSING]
    if any(v not in ("yes", "no") for v in accepted):
        raise ValueError("first_handoff_accepted must be yes/no/not_recorded")
    review_stats = metrics["review_min"]
    observed_precision = [r["precision_pct"] for r in per_brief if r["precision_pct"] is not None]
    return {"briefs": len(pilots), "metrics": metrics,
            "question_precision_pct": 100 * real / totals if totals else None,
            "question_precision_per_brief": {
                "values": per_brief, "measured": len(observed_precision),
                "missing": len(pilots) - len(observed_precision),
                "mean": mean(observed_precision) if observed_precision else None,
                "median": median(observed_precision) if observed_precision else None},
            "question_precision_measured_briefs": precision_rows,
            "question_precision_missing_briefs": len(pilots) - precision_rows,
            "review_under_30": (review_stats["median"] < 30
                                if review_stats["median"] is not None and review_stats["missing"] == 0 else None),
            "first_handoff_acceptance_pct": 100 * accepted.count("yes") / len(accepted) if accepted else None,
            "first_handoff_measured": len(accepted), "return_reasons": rework,
            "boundary": "Descriptive measurements, not a pilot go/no-go decision or a cash-savings estimate. "
                        "Baselines and owner approvals remain required."}


PASS, FAIL, INSUFFICIENT = "pass", "fail", "insufficient_data"

#: SCORECARD.md §4: the end-of-week-3 gate set is 2 leads x 3 past projects.
RETRO_SET_SIZE = 6


def _flag(row: dict[str, Any], key: str) -> Optional[bool]:
    """yes/no columns; anything else that is not missing is a data error."""
    value = row.get(key)
    if value in MISSING:
        return None
    if value not in ("yes", "no"):
        raise ValueError(f"{row.get('brief_id', '?')}: {key} must be yes/no/not_recorded")
    return value == "yes"


def _rule(rule_id: str, measure: str, target: str, observed: Any, status: str, n: int,
          note: Optional[str] = None) -> dict[str, Any]:
    rule: dict[str, Any] = {"rule": rule_id, "measure": measure, "target": target, "observed": observed,
                            "status": status, "n": n}
    if note:
        rule["note"] = note
    return rule


def _central(rows: list[dict[str, Any]], key: str, how: str, compare: Callable[[float], bool], target_text: str,
             rule_id: str) -> dict[str, Any]:
    """Median/mean rule: every row must carry a measured value, else insufficient_data."""
    values = [number(row, key) for row in rows]
    if not rows or any(v is None for v in values):
        missing = sum(v is None for v in values)
        return _rule(rule_id, f"{how}({key})", target_text, None, INSUFFICIENT, len(values) - missing,
                     f"{missing} of {len(values)} brief(s) not measured" if rows else "no briefs in this phase")
    measured = [v for v in values if v is not None]  # == values here; typed without None
    observed = median(measured) if how == "median" else mean(measured)
    return _rule(rule_id, f"{how}({key})", target_text, observed, PASS if compare(observed) else FAIL, len(values))


def _precision_rule(rows: list[dict[str, Any]], rule_id: str) -> dict[str, Any]:
    """Per-brief mean (SCORECARD §2). A brief with no questions has no precision: it is
    excluded from the mean and counted in the note, never scored as 100%."""
    measured: list[float] = []
    incomplete, no_questions = 0, 0
    for row in rows:
        total = number(row, "oq_total")
        classes = [number(row, k) for k in CLASSES]
        real = classes[0]
        if total is None or real is None or any(v is None for v in classes):
            incomplete += 1
        elif total == 0:
            no_questions += 1
        else:
            measured.append(100 * real / total)
    note = f"{no_questions} brief(s) with no open questions excluded" if no_questions else None
    if not rows or incomplete or not measured:
        reason = (f"{incomplete} of {len(rows)} brief(s) without a complete question classification" if incomplete
                  else "no brief with open questions" if rows else "no briefs in this phase")
        return _rule(rule_id, "mean(oq_real / oq_total)", "> 80%", None, INSUFFICIENT, len(measured),
                     reason + (f"; {note}" if note else ""))
    observed = mean(measured)
    return _rule(rule_id, "mean(oq_real / oq_total)", "> 80%", observed, PASS if observed > 80 else FAIL,
                 len(measured), note)


def _all_rule(rows: list[dict[str, Any]], key: str, rule_id: str, measure: str, target: str,
              ok: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    values = [row.get(key) for row in rows]
    if not rows or any(v in MISSING for v in values):
        missing = sum(v in MISSING for v in values)
        return _rule(rule_id, measure, target, None, INSUFFICIENT, len(values) - missing,
                     f"{missing} of {len(values)} brief(s) not recorded" if rows else "no briefs in this phase")
    failing = [row.get("brief_id", "?") for row in rows if not ok(row)]
    return _rule(rule_id, measure, target, f"{len(rows) - len(failing)}/{len(rows)}",
                 FAIL if failing else PASS, len(rows), f"failing: {failing}" if failing else None)


def _adoption_rule(pilots: list[dict[str, Any]], live_rows: list[dict[str, Any]]) -> dict[str, Any]:
    lead_ids: set[Any] = {row.get("lead_id") for row in pilots if row.get("lead_id") not in MISSING}
    leads = sorted(lead_ids)
    if not live_rows or not leads:
        return _rule("adoption_2_of_2", "pilot leads with a live brief initiated_by=lead", "2/2", None,
                     INSUFFICIENT, 0, "no live briefs or no lead_id recorded")
    chose_ids: set[Any] = {row.get("lead_id") for row in live_rows if row.get("initiated_by") == "lead"}
    chose = sorted(chose_ids)
    observed = f"{len(chose)}/{len(leads)}"
    status = PASS if len(leads) >= 2 and set(chose) >= set(leads) else FAIL
    note = None if len(leads) >= 2 else "fewer than two pilot leads recorded"
    return _rule("adoption_2_of_2", "pilot leads with a live brief initiated_by=lead", "2/2", observed, status,
                 len(live_rows), note)


def _gate(rules: list[dict[str, Any]]) -> str:
    statuses = [r["status"] for r in rules]
    if FAIL in statuses:
        return FAIL
    return INSUFFICIENT if INSUFFICIENT in statuses else PASS


def _spread(values: list[Optional[float]]) -> dict[str, Any]:
    observed = [v for v in values if v is not None]
    return {"measured": len(observed), "missing": len(values) - len(observed),
            "median": median(observed) if observed else None, "mean": mean(observed) if observed else None,
            "min": min(observed) if observed else None, "max": max(observed) if observed else None}


def _net(rows: list, baseline: str, actual: str) -> dict[str, Any]:
    """Per-brief (baseline - actual) minutes where both are measured; never imputed."""
    values: list[Optional[float]] = []
    for row in rows:
        before, after = number(row, baseline), number(row, actual)
        values.append(None if before is None or after is None else before - after)
    result = _spread(values)
    result["formula"] = f"{baseline} - {actual}, per retro brief"
    result["complete"] = bool(rows) and result["missing"] == 0
    return result


def reported_measures(pilots: list) -> dict[str, Any]:
    """Reported-only measures (SCORECARD.md §2, §3, §5a). None is gated; missing stays missing.

    - net_lead_minutes: baseline_min - total_attention_min on retro rows (the capacity formula's
      per-brief input, account lead only).
    - net_team_minutes: baseline_team_min - total_team_min on retro rows: the same saving net
      of every role the Tier 5-7 layer adds (operator, strategy, creative, production).
    - agency_steps_min: the lead's minutes on audit, triage, exclusions, checklist and
      deliverable rows, a subset of review_min (never added twice).
    - baseline_check: recalled baseline_min against a timed fresh manual brief
      (baseline_timed_min), for the recall-bias threat.
    - retro_side_by_side: the countable comparison with the brief the agency actually wrote.
    - survival_canonical_pct: field-level survival of brief.json, draft against approved.
    """
    retro = [row for row in pilots if row.get("phase") == "retro"]
    side: dict[str, dict[str, Any]] = {}
    for key in SIDE_BY_SIDE:
        values = [number(row, key) for row in retro]
        observed = [v for v in values if v is not None]
        side[key] = {"measured": len(observed), "missing": len(values) - len(observed),
                     "sum": int(sum(observed)) if observed else None,
                     "mean_per_brief": mean(observed) if observed else None}
    steps = _spread([number(row, "agency_steps_min") for row in pilots])
    review = [number(row, "review_min") for row in pilots]
    shares: list[float] = []
    for row, r in zip(pilots, review):
        if not r:
            continue
        steps_min = number(row, "agency_steps_min")
        if steps_min is not None:
            shares.append(100 * steps_min / r)
    steps["share_of_review_pct_median"] = median(shares) if shares else None
    return {
        "net_lead_minutes": _net(retro, "baseline_min", "total_attention_min"),
        "net_team_minutes": _net(retro, "baseline_team_min", "total_team_min"),
        "agency_steps_min": steps,
        "baseline_check": _net(retro, "baseline_min", "baseline_timed_min") | {
            "formula": "baseline_min (recalled) - baseline_timed_min (timed fresh manual brief), per brief"},
        "retro_side_by_side": side,
        "survival_canonical_pct": _spread([number(row, "survival_canonical_pct") for row in pilots]),
    }


def pass_rules(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Evaluate every SCORECARD.md §4 pass rule per phase: pass / fail / insufficient_data.

    Missing is never a pass. Manual-fallback briefs (a brief written by hand after a refusal,
    `manual_fallback=yes`) are counted and reported but excluded from the timing and quality
    rules, because they have no draft; the week-3 set needs six non-fallback retro briefs.
    Immediate-stop events (S2/S3 material, a critical error reaching a client) are incidents,
    not CSV rows: they are recorded in the incident log (docs/pilot/INCIDENT_RECOVERY.md) and
    stop the pilot regardless of this report.
    """
    pilots = [row for row in rows if row.get("row_type") == "PILOT"]
    fallback = [row for row in pilots if _flag(row, "manual_fallback")]
    scored = [row for row in pilots if not _flag(row, "manual_fallback")]
    for row in pilots:
        for key in ("schema_valid", "signed_off", "creative_approved", "creative_released",
                    "creative_withdrawn", "sod_waiver"):
            _flag(row, key)
    by_phase = {"retro": [r for r in scored if r.get("phase") == "retro"],
                "live": [r for r in scored if r.get("phase") == "live"]}
    result: dict[str, Any] = {}
    for phase, group in by_phase.items():
        wk = "end_week_3" if phase == "retro" else "end_week_4"
        rules = [
            _central(group, "assembly_min", "median", lambda v: v <= 20, "<= 20", "assembly_le_20"),
            _central(group, "review_min", "median", lambda v: v < 30, "< 30", "review_under_30"),
            _central(group, "total_attention_min", "median", lambda v: v <= 50, "<= 50", "total_attention_le_50"),
            _precision_rule(group, "question_precision_gt_80"),
            _all_rule(group, "ce_total", "critical_errors_zero", "ce_total per brief", "0 on every brief",
                      lambda row: number(row, "ce_total") == 0),
            _all_rule(group, "schema_valid", "schema_valid_all", "schema_valid", "yes on every brief",
                      lambda row: row.get("schema_valid") == "yes"),
        ]
        if phase == "retro":
            # Survival is reported, not gated, at the end of week 3 (SCORECARD §2).
            size_ok = len(group) >= RETRO_SET_SIZE
            rules.append(_rule("retro_set_complete", "non-fallback retro briefs", f">= {RETRO_SET_SIZE}",
                               len(group), PASS if size_ok else INSUFFICIENT, len(group)))
        else:
            rules += [
                _central(group, "survival_en_pct", "mean", lambda v: v > 70, "> 70%", "survival_en_gt_70"),
                _central(group, "survival_el_pct", "mean", lambda v: v > 70, "> 70%", "survival_el_gt_70"),
                _adoption_rule(pilots, group),
            ]
        result[wk] = {"phase": phase, "gate": _gate(rules), "rules": rules}
    result["reported"] = {
        "manual_fallback_briefs": len(fallback),
        "manual_fallback_share_pct": 100 * len(fallback) / len(pilots) if pilots else None,
        "creative_released": sum(bool(_flag(r, "creative_released")) for r in pilots),
        "creative_withdrawn": sum(bool(_flag(r, "creative_withdrawn")) for r in pilots),
        "sod_waivers": sum(bool(_flag(r, "sod_waiver")) for r in pilots),
        "not_machine_evaluated": ["immediate-stop events (incident log)", "stop-rule decision (sponsor)",
                                  "month-2 onboarding requests (report)"],
        **reported_measures(pilots),
    }
    if result["reported"]["sod_waivers"]:
        result["reported"]["warning"] = ("A separation-of-duties waiver is recorded on a PILOT row; waivers are "
                                         "for synthetic rehearsal only (docs/pilot/ROLES.md).")
    result["boundary"] = ("Rule evaluation against SCORECARD §4 as proposed; targets marked OWNER TO CONFIRM there "
                          "remain proposals. insufficient_data is never a pass.")
    return result


def summarize(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Descriptive summary of the PILOT rows (overall and per phase) plus every §4 pass rule."""
    row_list = list(rows)
    result = _summarize(row_list)
    phases: dict[str, list[dict[str, Any]]] = {}
    for row in row_list:
        if row.get("row_type") == "PILOT":
            phase: Any = row.get("phase")
            phase = "not_recorded" if phase in MISSING else phase
            phases.setdefault(phase, []).append(row)
    result["by_phase"] = {phase: _summarize(group) for phase, group in phases.items()}
    result["pass_rules"] = pass_rules(row_list)
    return result


def survival(draft: str, final: str) -> int:
    """Exact character Levenshtein score in O(min(n,m)) memory; no extra dependency."""
    if not draft:
        raise ValueError("Empty draft cannot be scored")
    a, b = (draft, final) if len(draft) >= len(final) else (final, draft)
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (x != y)))
        previous = current
    return round(max(0, 100 * (1 - previous[-1] / len(draft))))


#: Fields of brief.json whose entry text a reader sees; evidence and metadata are excluded so
#: citation churn and sign-off stamps are not counted as edits.
_CANONICAL_ENTRY_FIELDS = ("objectives", "audiences", "key_messages", "deliverables", "timeline", "budget",
                           "mandatories")


def canonical_text(brief: dict) -> str:
    """The reader-facing text of a brief object, one line per entry, in schema field order."""
    lines: list[str] = []
    for field in _CANONICAL_ENTRY_FIELDS:
        for entry in brief.get(field) or []:
            lines.append(f"{field}: {entry.get('content', '')}")
    for question in brief.get("open_questions") or []:
        lines.append(f"question/{question.get('field', '')}: {question.get('gap', '')} | "
                     f"{question.get('suggested_question_for_client', '')}")
    for conflict in brief.get("conflicts") or []:
        positions = " / ".join(p.get("statement", "") for p in conflict.get("positions") or [])
        lines.append(f"conflict/{conflict.get('field', '')}: {positions} | {conflict.get('status', '')} | "
                     f"{conflict.get('resolution', '')}")
    return "\n".join(lines)


def _require_current_approval(run: Path) -> None:
    try:  # the approval-binding policy may live in pipeline.approval (round 2) or pipeline.revisions
        policy = importlib.import_module("pipeline.approval")
    except ImportError:
        policy = importlib.import_module("pipeline.revisions")
    policy.require_current_approval(run)


def survival_bundle(draft_dir: Path, approved_run: Path, check_approval: bool = True) -> dict[str, int]:
    """Survival per SCORECARD.md §2: the archived first draft against what `agency approve` bound.

    `draft_dir` holds the copies taken before review (`brief_en.md`, `brief_el.md`,
    `brief.json`); `approved_run` is the run directory whose approval is current. The
    approval is checked first, so a number is never produced for an unapproved or stale
    revision. Returns integer percentages for EN, EL and the canonical object.
    """
    draft_dir, approved_run = Path(draft_dir), Path(approved_run)
    if check_approval:
        _require_current_approval(approved_run)
    result: dict[str, int] = {}
    for lang in ("en", "el"):
        draft, final = draft_dir / f"brief_{lang}.md", approved_run / f"brief_{lang}.md"
        result[f"survival_{lang}_pct"] = survival(draft.read_text(encoding="utf-8"),
                                                  final.read_text(encoding="utf-8"))
    draft_brief = json.loads((draft_dir / "brief.json").read_text(encoding="utf-8"))
    final_brief = json.loads((approved_run / "brief.json").read_text(encoding="utf-8"))
    result["survival_canonical_pct"] = survival(canonical_text(draft_brief), canonical_text(final_brief))
    return result


def main(argv: Optional[list[str]] = None) -> int:
    """CLI: summarize a scorecard CSV, or compute survival for one brief."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("csv", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--final", type=Path)
    parser.add_argument("--draft-dir", type=Path,
                        help="Archived first-draft copies (brief_en.md, brief_el.md, brief.json)")
    parser.add_argument("--approved-run", type=Path, help="Run directory whose `agency approve` is current")
    args = parser.parse_args(argv)
    try:
        if args.draft_dir or args.approved_run:
            if not args.draft_dir or not args.approved_run:
                raise ValueError("Both --draft-dir and --approved-run are required")
            result = survival_bundle(args.draft_dir, args.approved_run)
        elif args.draft or args.final:
            if not args.draft or not args.final:
                raise ValueError("Both --draft and --final are required")
            result = {"survival_pct": survival(args.draft.read_text(encoding="utf-8"),
                                               args.final.read_text(encoding="utf-8"))}
        else:
            if not args.csv:
                raise ValueError("Provide a scorecard CSV")
            with args.csv.open(encoding="utf-8", newline="") as handle:
                result = summarize(list(csv.DictReader(handle)))
        text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, f"scorecard: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
