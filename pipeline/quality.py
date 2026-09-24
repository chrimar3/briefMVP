"""Evidence coverage, not an assertion of semantic equivalence."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any

from pipeline import gates
from pipeline.render_checks import render_coverage, tag_location
from pipeline.revisions import digest

__all__ = ["RefKey", "coverage", "destinations", "field_review_checklist", "ref_key", "render_coverage",
           "tag_location"]

#: (source_id, location, anchor) — the identity of one evidence reference.
RefKey = tuple[str, str, str]


def ref_key(ref: Mapping[str, Any]) -> RefKey:
    """The (source_id, location, anchor) identity of an evidence reference, stripped."""
    source_id, location, anchor = (str(ref.get(k, "")).strip() for k in ("source_id", "location", "anchor"))
    return source_id, location, anchor


def destinations(brief: Mapping[str, Any]) -> Iterator[tuple[Any, str, list[dict[str, Any]]]]:
    """Every place in the brief that can carry evidence: (field, locator such as `goals[0]`, evidence refs)."""
    for field in gates.BRIEF_FIELDS:
        for i, entry in enumerate(brief.get(field) or []):
            yield field, f"{field}[{i}]", entry.get("evidence") or []
    for i, item in enumerate(brief.get("open_questions") or []):
        yield item.get("field"), f"open_questions[{i}]", item.get("linked_evidence") or []
    for i, item in enumerate(brief.get("conflicts") or []):
        yield item.get("field"), f"conflicts[{i}]", [p.get("evidence") or {} for p in item.get("positions") or []]


def coverage(brief: Mapping[str, Any], extracts: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One record per extracted item: its evidence and the brief locations that cite that same evidence."""
    targets = list(destinations(brief))
    records: list[dict[str, Any]] = []
    for source_id, extract in sorted(extracts.items()):
        items = [(field, item) for field in gates.BRIEF_FIELDS for item in extract.get(field) or []]
        items += [(c.get("field"), c[side]) for c in extract.get("internal_conflicts") or []
                  for side in ("value_a", "value_b") if c.get(side)]
        for field, item in items:
            ref = {"source_id": source_id, "location": item.get("location", ""), "anchor": item.get("anchor", "")}
            record = {"field": field, "value": item.get("value", ""), "evidence": ref}
            record["id"] = digest(record)[:20]
            record["destinations"] = [name for dest_field, name, refs in targets
                                      if dest_field == field and ref_key(ref) in {ref_key(r) for r in refs}]
            records.append(record)
    return records


def field_review_checklist() -> list[str]:
    """The per-field items a language reviewer attests (agency attest)."""
    return ["source_completeness", "el_meaning", "en_meaning", "qualifiers_and_commitments", "brand_voice"]
