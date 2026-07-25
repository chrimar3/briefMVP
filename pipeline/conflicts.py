"""Pipeline step 5 — cross-source conflict detection (the deterministic half).

PRD §5 calls this step "deterministic + LLM assist", and the split matters. Deciding whether
"Gen Z, 18–24" and "25 to 40, urban professionals" are the same claim needs judgment. Deciding
*which field/source combinations are worth looking at* does not — it is grouping, and grouping
by model would be an expensive way to be non-reproducible.

So this module does the grouping with high recall and no opinions: for every briefable field
where two or more sources contributed evidence, it emits a candidate block with every item and
its provenance. Synthesis adjudicates (SYNTHESIS.md rule 4) and may add conflicts this pass did
not propose. Neither stage may *resolve* one — that is the account lead's call, by design
(PRD DR-10).
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline import gates


def _item_ref(source_id: str, item: dict) -> dict:
    """One position in a candidate, carrying its evidence verbatim."""
    return {
        "source_id": source_id,
        "value": item.get("value", ""),
        "location": item.get("location", ""),
        "anchor": item.get("anchor", ""),
        "speaker_or_author": item.get("speaker_or_author", ""),
        "qualifier": item.get("qualifier", ""),
        "confidence": item.get("confidence", ""),
    }


def find_conflict_candidates(extracts: dict) -> list:
    """Fields where more than one source spoke. High recall on purpose.

    A candidate is not a conflict. Two sources agreeing on the budget produce a candidate too —
    cheap to emit, and the alternative (a deterministic rule that tries to tell agreement from
    contradiction across languages and hedges) is exactly the judgment this pipeline routes to a
    model on purpose.
    """
    candidates = []
    for fieldname in gates.BRIEF_FIELDS:
        by_source = {
            source_id: [_item_ref(source_id, item) for item in (extract.get(fieldname) or [])]
            for source_id, extract in sorted(extracts.items())
        }
        contributing = {sid: items for sid, items in by_source.items() if items}
        if len(contributing) < 2:
            continue
        candidates.append(
            {
                "field": fieldname,
                "sources": sorted(contributing),
                "positions": [item for items in contributing.values() for item in items],
            }
        )
    return candidates


def collect_internal_conflicts(extracts: dict) -> list:
    """Same-source contradictions the extraction stage already found (SOURCES.md rule 3).

    Carried forward rather than re-derived: the extractor saw the retraction in context and
    labelled it; re-deciding that downstream would be second-guessing better evidence.
    """
    collected = []
    for source_id, extract in sorted(extracts.items()):
        for conflict in extract.get("internal_conflicts") or []:
            # Provenance last so it wins: the extract schema forbids a `source_id` key inside a
            # conflict today, but the pipeline's label must not be silently overridable if that
            # ever changes.
            collected.append({**conflict, "source_id": source_id})
    return collected


def run_conflict_pass(extracts: dict, run_dir: Path) -> dict:
    """Write the conflict-pass artifact synthesis will consume."""
    payload = {
        "cross_source_candidates": find_conflict_candidates(extracts),
        "internal_conflicts": collect_internal_conflicts(extracts),
        "note": (
            "Candidates are fields where 2+ sources contributed evidence. They are NOT conflicts. "
            "Synthesis decides which are genuine contradictions and emits conflicts[] with both "
            "positions and status 'open'. No stage may resolve a conflict (PRD DR-10)."
        ),
    }
    path = Path(run_dir) / "conflict_candidates.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "output_file": str(path),
        "candidate_count": len(payload["cross_source_candidates"]),
        "candidate_fields": [c["field"] for c in payload["cross_source_candidates"]],
        "internal_conflict_count": len(payload["internal_conflicts"]),
    }
