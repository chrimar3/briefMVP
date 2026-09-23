"""Evidence coverage, not an assertion of semantic equivalence."""
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any

from pipeline import gates
from pipeline.revisions import digest

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


def render_coverage(brief: Mapping[str, Any], text: str, lang: str) -> list[str]:
    """Check field-level statement counts and sources. Meaning still needs a reviewer."""
    problems: list[str] = []
    sections: dict[str, list[str]] = {}
    current: Any = None
    for line in text.splitlines():
        match = re.match(r"^##\s+([1-7])[.)]?\s", line)
        if match:
            current = gates.BRIEF_FIELDS[int(match.group(1)) - 1]
            sections[current] = []
        elif line.startswith("##"):
            current = None
        elif current and re.match(r"^\s*(?:[-*]|\d+[.)])\s+", line):
            sections[current].append(line)
    for field in gates.BRIEF_FIELDS:
        entries = brief.get(field) or []
        lines = sections.get(field, [])
        if entries and len(lines) < len(entries):
            problems.append(f"{lang}: {field} has {len(entries)} entries but only {len(lines)} statement lines")
        for entry in entries:
            for ref in entry.get("evidence") or []:
                if ref.get("source_id") and not any(ref["source_id"] in line for line in lines):
                    problems.append(f"{lang}: {field} lacks cited source {ref['source_id']}")
    # Question blocks have a numbered, language-independent template contract. A
    # citation elsewhere in the brief does not establish a question's evidence.
    warning_sections = re.split(r"(?m)^##\s+", text)
    blocks: list[str] = []
    for section in warning_sections:
        if section.startswith("⚠"):
            numbered = re.findall(r"(?ms)^\s*\d+[.)]\s+.*?(?=^\s*\d+[.)]\s+|\Z)", section)
            if numbered:
                blocks = numbered
                break
    for i, question in enumerate(brief.get("open_questions") or []):
        block = blocks[i] if i < len(blocks) else ""
        for ref in question.get("linked_evidence") or []:
            tags = re.findall(r"\[([^]]+)\]", block)
            location = tag_location(ref.get("location", ""))
            if not any(ref.get("source_id", "") in tag and location in tag for tag in tags):
                problems.append(f"{lang}: question {i} lacks its linked evidence citation")
    return problems


def tag_location(location: Any) -> str:
    """The location as it sits inside a `[source_id location]` citation tag.

    A transcript location is itself bracketed (`[00:03:41]`); a tag cannot contain `]`, so the
    render writes it without its own brackets (`[kickoff 00:03:41]`, the render order's form).
    One enclosing pair is dropped; every other location is matched exactly as stored.
    """
    location = str(location or "").strip()
    if len(location) > 2 and location.startswith("[") and location.endswith("]"):
        return location[1:-1].strip()
    return location


def field_review_checklist() -> list[str]:
    """The per-field items a language reviewer attests (agency attest)."""
    return ["source_completeness", "el_meaning", "en_meaning", "qualifiers_and_commitments", "brand_voice"]
