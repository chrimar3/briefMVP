"""Validate and summarize recorded pilot data. Missing is never zero; examples never count."""
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


def summarize(rows):
    pilots = []
    for row in rows:
        if row.get("row_type") == "EXAMPLE":
            continue
        if row.get("row_type") != "PILOT":
            raise ValueError("row_type must be EXAMPLE or PILOT")
        pilots.append(row)
    totals, real, precision_rows = 0, 0, 0
    team_fields = ("total_attention_min", "operator_min", "strategy_min", "creative_min", "production_min")
    for row in pilots:
        for total, components in (("total_attention_min", ("assembly_min", "review_min")), ("total_team_min", team_fields)):
            stated = number(row, total)
            parts = [number(row, k) for k in components]
            if stated is not None and all(v is not None for v in parts) and not math.isclose(stated, sum(parts)):
                raise ValueError(f"{total} does not equal its measured components")
        total = number(row, "oq_total")
        classes = [number(row, k) for k in CLASSES]
        if total is not None and all(v is not None for v in classes):
            if not math.isclose(total, sum(classes)) or any(v != int(v) for v in [total] + classes):
                raise ValueError("question class counts must be integers summing to oq_total")
            totals += total
            real += classes[0]
            precision_rows += 1
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
    return {"briefs": len(pilots), "metrics": metrics, "question_precision_pct": 100 * real / totals if totals else None,
            "question_precision_measured_briefs": precision_rows, "question_precision_missing_briefs": len(pilots) - precision_rows,
            "review_under_30": review["median"] < 30 if review["median"] is not None and review["missing"] == 0 else None,
            "first_handoff_acceptance_pct": 100 * accepted.count("yes") / len(accepted) if accepted else None,
            "first_handoff_measured": len(accepted), "return_reasons": rework,
            "boundary": "Descriptive measurements, not a pilot go/no-go decision or a cash-savings estimate. Baselines and owner approvals remain required."}


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
