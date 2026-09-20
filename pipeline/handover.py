"""Structured brief handover; traffic-owned specs, never invented platform values."""
from __future__ import annotations

from datetime import date
import re
from pipeline.quality import destinations, ref_key


def validate(rows, spec_table, brief):
    problems = []
    specs = {r["id"]: r for r in spec_table.get("specs", [])}
    refs = {ref_key(ref) for _, _, evidence in destinations(brief) for ref in evidence}
    ids = set()
    for i, row in enumerate(rows):
        prefix = f"deliverable {i}"
        for key in ("id", "spec_id", "owner", "approval_owner", "deadline"):
            if not str(row.get(key, "")).strip():
                problems.append(f"{prefix}: missing {key}")
        if row.get("id") in ids:
            problems.append(f"{prefix}: duplicate id")
        ids.add(row.get("id"))
        if type(row.get("quantity")) is not int or row["quantity"] < 1:
            problems.append(f"{prefix}: quantity must be a positive integer")
        if not isinstance(row.get("languages"), list) or not row["languages"] or not all(isinstance(v, str) and v.strip() for v in row["languages"]):
            problems.append(f"{prefix}: languages required")
        if not isinstance(row.get("dependencies"), list):
            problems.append(f"{prefix}: explicit dependencies list required (empty if none)")
        try:
            date.fromisoformat(row.get("deadline", ""))
        except (ValueError, TypeError):
            problems.append(f"{prefix}: deadline must be an ISO date")
        if not row.get("evidence") or any(ref_key(r) not in refs for r in row.get("evidence", [])):
            problems.append(f"{prefix}: evidence must refer to the canonical brief")
        spec = specs.get(row.get("spec_id"))
        if spec is None:
            problems.append(f"{prefix}: spec_id not in traffic table")
            continue
        for key in ("resolution", "aspect_ratio", "format", "file_type"):
            if row.get(key) != spec.get(key):
                problems.append(f"{prefix}: {key} must match selected spec row")
        bounds = spec.get("duration_seconds")
        if bounds is None and spec.get("duration") not in (None, "n/a"):
            interval = re.fullmatch(r"(\d+)-(\d+)s", spec["duration"])
            maximum = re.fullmatch(r"up to (\d+)s", spec["duration"])
            if interval:
                bounds = {"min": int(interval[1]), "max": int(interval[2])}
            elif maximum:
                bounds = {"min": 0, "max": int(maximum[1])}
            else:
                problems.append(f"{prefix}: unrecognized duration contract; ask traffic")
        if spec.get("duration") == "n/a" and row.get("duration_seconds") is not None:
            problems.append(f"{prefix}: duration must be absent for a static deliverable")
        if bounds is not None:
            duration = row.get("duration_seconds")
            if type(duration) not in (int, float) or not bounds["min"] <= duration <= bounds["max"]:
                problems.append(f"{prefix}: duration outside selected spec range")
    problems.extend(validate_dependencies(rows))
    return problems


def validate_dependencies(rows):
    """Traffic dependencies are deliverable IDs, with predecessors due no later."""
    problems, graph = [], {}
    dates = {r.get('id'): r.get('deadline') for r in rows if isinstance(r.get('id'), str)}
    for row in rows:
        key, dependencies = row.get('id'), row.get('dependencies')
        if not isinstance(key, str) or not isinstance(dependencies, list):
            continue
        graph[key] = []
        seen = set()
        for dep in dependencies:
            if not isinstance(dep, str) or dep not in dates:
                problems.append(f'{key}: dependency must name an existing deliverable')
                continue
            if dep in seen:
                problems.append(f'{key}: duplicate dependency {dep}')
            seen.add(dep)
            if dep == key:
                problems.append(f'{key}: self dependency')
            graph[key].append(dep)
            try:
                if date.fromisoformat(dates[dep]) > date.fromisoformat(row['deadline']):
                    problems.append(f'{key}: dependency {dep} is due after this deliverable')
            except (ValueError, TypeError):
                pass  # Ordinary row validation reports malformed dates.
    # Kahn's algorithm avoids recursion limits on large production matrices.
    pending = {key: set(values) for key, values in graph.items()}
    while pending:
        ready = {key for key, values in pending.items() if not values}
        if not ready:
            problems.append('Deliverable dependency cycle: ' + ', '.join(sorted(pending)))
            break
        pending = {key: values - ready for key, values in pending.items() if key not in ready}
    return problems
