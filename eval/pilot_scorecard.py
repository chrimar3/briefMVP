"""Validate and summarize recorded pilot data, and evaluate every SCORECARD.md §4 pass rule.

Missing is never zero and never a pass; examples never count. Each rule reports
pass / fail / insufficient_data per phase (end of week 3 = retro, end of week 4 = live).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, median

METRICS = ("assembly_min", "review_min", "total_attention_min", "operator_min", "strategy_min", "creative_min", "production_min", "total_team_min",
           "survival_en_pct", "survival_el_pct", "el_register_1to5", "ce_total", "creative_rework_requests_q1", "client_revision_rounds_q1")
CLASSES = ("oq_real", "oq_duplicate", "oq_answered_in_sources", "oq_not_worth_asking")
MISSING = (None, "", "not_recorded", "n/a")


def number(row, key):
    raw = row.get(key)
    if raw in MISSING:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{row.get('brief_id', '?')}: {key} must be numeric or not_recorded")
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{key} must be finite and nonnegative")
    if key.endswith("_pct") and value > 100:
        raise ValueError(f"{key} must be in 0–100")
    if key == "el_register_1to5" and (value not in range(1, 6)):
        raise ValueError("Greek register must be an integer in 1–5")
    return value


def _summarize(rows):
    pilots = []
    for row in rows:
        if row.get("row_type") == "EXAMPLE":
            continue
        if row.get("row_type") != "PILOT":
            raise ValueError("row_type must be EXAMPLE or PILOT")
        pilots.append(row)
    totals, real, precision_rows = 0, 0, 0
    per_brief = []
    team_fields = ("total_attention_min", "operator_min", "strategy_min", "creative_min", "production_min")
    for row in pilots:
        for total, components in (("total_attention_min", ("assembly_min", "review_min")), ("total_team_min", team_fields)):
            stated = number(row, total)
            parts = [number(row, k) for k in components]
            if stated is not None and all(v is not None for v in parts) and not math.isclose(stated, sum(parts)):
                raise ValueError(f"{total} does not equal its measured components")
        total = number(row, "oq_total")
        classes = [number(row, k) for k in CLASSES]
        if any(v is not None and v != int(v) for v in [total] + classes):
            raise ValueError("question class counts must be integers")
        precision = None
        if total is not None and all(v is not None for v in classes):
            if not math.isclose(total, sum(classes)) or any(v != int(v) for v in [total] + classes):
                raise ValueError("question class counts must be integers summing to oq_total")
            totals += total
            real += classes[0]
            precision_rows += 1
            precision = 100 * classes[0] / total if total else None
        per_brief.append({"brief_id": row.get("brief_id", "not_recorded"),
                          "precision_pct": precision})
    metrics = {}
    for key in METRICS:
        values = [number(row, key) for row in pilots]
        observed = [v for v in values if v is not None]
        metrics[key] = {"measured": len(observed), "missing": len(values) - len(observed),
                        "mean": mean(observed) if observed else None, "median": median(observed) if observed else None}
    rework = {}
    for row in pilots:
        reason = row.get("return_reason", "")
        if reason not in MISSING:
            rework[reason] = rework.get(reason, 0) + 1
    accepted = [row.get("first_handoff_accepted") for row in pilots if row.get("first_handoff_accepted") not in MISSING]
    if any(v not in ("yes", "no") for v in accepted):
        raise ValueError("first_handoff_accepted must be yes/no/not_recorded")
    review = metrics["review_min"]
    observed_precision = [r["precision_pct"] for r in per_brief if r["precision_pct"] is not None]
    return {"briefs": len(pilots), "metrics": metrics, "question_precision_pct": 100 * real / totals if totals else None,
            "question_precision_per_brief": {
                "values": per_brief, "measured": len(observed_precision),
                "missing": len(pilots) - len(observed_precision),
                "mean": mean(observed_precision) if observed_precision else None,
                "median": median(observed_precision) if observed_precision else None},
            "question_precision_measured_briefs": precision_rows, "question_precision_missing_briefs": len(pilots) - precision_rows,
            "review_under_30": review["median"] < 30 if review["median"] is not None and review["missing"] == 0 else None,
            "first_handoff_acceptance_pct": 100 * accepted.count("yes") / len(accepted) if accepted else None,
            "first_handoff_measured": len(accepted), "return_reasons": rework,
            "boundary": "Descriptive measurements, not a pilot go/no-go decision or a cash-savings estimate. Baselines and owner approvals remain required."}


PASS, FAIL, INSUFFICIENT = "pass", "fail", "insufficient_data"

#: SCORECARD.md §4: the end-of-week-3 gate set is 2 leads x 3 past projects.
RETRO_SET_SIZE = 6


def _flag(row, key):
    """yes/no columns; anything else that is not missing is a data error."""
    value = row.get(key)
    if value in MISSING:
        return None
    if value not in ("yes", "no"):
        raise ValueError(f"{row.get('brief_id', '?')}: {key} must be yes/no/not_recorded")
    return value == "yes"


def _rule(rule_id, measure, target, observed, status, n, note=None):
    rule = {"rule": rule_id, "measure": measure, "target": target, "observed": observed, "status": status, "n": n}
    if note:
        rule["note"] = note
    return rule


def _central(rows, key, how, compare, target_text, rule_id):
    """Median/mean rule: every row must carry a measured value, else insufficient_data."""
    values = [number(row, key) for row in rows]
    if not rows or any(v is None for v in values):
        missing = sum(v is None for v in values)
        return _rule(rule_id, f"{how}({key})", target_text, None, INSUFFICIENT, len(values) - missing,
                     f"{missing} of {len(values)} brief(s) not measured" if rows else "no briefs in this phase")
    observed = median(values) if how == "median" else mean(values)
    return _rule(rule_id, f"{how}({key})", target_text, observed, PASS if compare(observed) else FAIL, len(values))


def _precision_rule(rows, rule_id):
    """Per-brief mean (SCORECARD §2). A brief with no questions has no precision: it is
    excluded from the mean and counted in the note, never scored as 100%."""
    measured, incomplete, no_questions = [], 0, 0
    for row in rows:
        total = number(row, "oq_total")
        classes = [number(row, k) for k in CLASSES]
        if total is None or any(v is None for v in classes):
            incomplete += 1
        elif total == 0:
            no_questions += 1
        else:
            measured.append(100 * classes[0] / total)
    note = f"{no_questions} brief(s) with no open questions excluded" if no_questions else None
    if not rows or incomplete or not measured:
        reason = (f"{incomplete} of {len(rows)} brief(s) without a complete question classification" if incomplete
                  else "no brief with open questions" if rows else "no briefs in this phase")
        return _rule(rule_id, "mean(oq_real / oq_total)", "> 80%", None, INSUFFICIENT, len(measured),
                     reason + (f"; {note}" if note else ""))
    observed = mean(measured)
    return _rule(rule_id, "mean(oq_real / oq_total)", "> 80%", observed, PASS if observed > 80 else FAIL,
                 len(measured), note)


def _all_rule(rows, key, rule_id, measure, target, ok):
    values = [row.get(key) for row in rows]
    if not rows or any(v in MISSING for v in values):
        missing = sum(v in MISSING for v in values)
        return _rule(rule_id, measure, target, None, INSUFFICIENT, len(values) - missing,
                     f"{missing} of {len(values)} brief(s) not recorded" if rows else "no briefs in this phase")
    failing = [row.get("brief_id", "?") for row in rows if not ok(row)]
    return _rule(rule_id, measure, target, f"{len(rows) - len(failing)}/{len(rows)}",
                 FAIL if failing else PASS, len(rows), f"failing: {failing}" if failing else None)


def _adoption_rule(pilots, live_rows):
    leads = sorted({row.get("lead_id") for row in pilots if row.get("lead_id") not in MISSING})
    if not live_rows or not leads:
        return _rule("adoption_2_of_2", "pilot leads with a live brief initiated_by=lead", "2/2", None,
                     INSUFFICIENT, 0, "no live briefs or no lead_id recorded")
    chose = sorted({row.get("lead_id") for row in live_rows if row.get("initiated_by") == "lead"})
    observed = f"{len(chose)}/{len(leads)}"
    status = PASS if len(leads) >= 2 and set(chose) >= set(leads) else FAIL
    note = None if len(leads) >= 2 else "fewer than two pilot leads recorded"
    return _rule("adoption_2_of_2", "pilot leads with a live brief initiated_by=lead", "2/2", observed, status,
                 len(live_rows), note)


def _gate(rules):
    statuses = [r["status"] for r in rules]
    if FAIL in statuses:
        return FAIL
    return INSUFFICIENT if INSUFFICIENT in statuses else PASS


def pass_rules(rows):
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
    result = {}
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
    }
    if result["reported"]["sod_waivers"]:
        result["reported"]["warning"] = ("A separation-of-duties waiver is recorded on a PILOT row; waivers are "
                                         "for synthetic rehearsal only (docs/pilot/ROLES.md).")
    result["boundary"] = ("Rule evaluation against SCORECARD §4 as proposed; targets marked OWNER TO CONFIRM there "
                          "remain proposals. insufficient_data is never a pass.")
    return result


def summarize(rows):
    rows = list(rows)
    result = _summarize(rows)
    phases = {}
    for row in rows:
        if row.get("row_type") == "PILOT":
            phase = row.get("phase")
            phase = "not_recorded" if phase in MISSING else phase
            phases.setdefault(phase, []).append(row)
    result["by_phase"] = {phase: _summarize(group) for phase, group in phases.items()}
    result["pass_rules"] = pass_rules(rows)
    return result


def survival(draft, final):
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="?")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--draft", type=Path)
    parser.add_argument("--final", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.draft or args.final:
            if not args.draft or not args.final:
                raise ValueError("Both --draft and --final are required")
            result = {"survival_pct": survival(args.draft.read_text(encoding="utf-8"), args.final.read_text(encoding="utf-8"))}
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
