"""The deterministic half of SOURCES.md §4–§7: confidence, linkage, rule G, background posture.

`extraction.check_extract` runs these after its schema and citation layers. Each rule is a pure
function of one extract (rule G also reads the source text and, for a fidelity-annotated
transcript, the annotated text) and returns its violations. They are the gate behind four
skill clauses that the stored evidence showed were neither followed nor checked (review round
1: 64 of 379 stored questions carried `linked_items`; garbled items were carried at `high`):

* `rule_confidence_semantics` — one meaning per confidence level (SOURCES.md §4): `implied`
  items are `low`; `conditional` items are never `high`; a `stated` item is `low` only under
  one of the two named overrides (G: it carries a garbled token; M: a mandatory).
* `rule_linked_questions` — every `medium`/`low` item is named, as `<field>[<index>]`, in some
  open question's `linked_items`, and every link names an item that exists.
* `rule_garble` — the structured rule-G note (`garble: «token» at <location> — proposed match
  "<term>"`): its token occurs in the source, every item carrying it is `low`, and every
  fidelity-gate glossary match has a note.
* `rule_background_commitments` — a background document never creates a commitment: its items
  under deliverables, timeline or budget are context, qualifier `implied`.

`garble_notes` and `items_carrying` are shared with the synthesis gate, which checks that a
garbled token stays visible in the brief (SYNTHESIS.md rule 10).
"""

from __future__ import annotations

import re
from typing import Iterator, Optional

from pipeline import gates

#: The rule-G extraction note, one per garbled token (SOURCES.md §7 rule G):
#:   garble: «<token exactly as the source writes it>» at <location> — proposed match "<term>"
#: <term> is a glossary term, or `no-glossary-match`.
GARBLE_NOTE_RE = re.compile(
    r'^\s*garble:\s*«(?P<token>[^»]+)»\s+at\s+(?P<location>.+?)\s+[—–-]+\s+'
    r'proposed match\s+"(?P<match>[^"]*)"',
    re.IGNORECASE,
)
NO_GLOSSARY_MATCH = "no-glossary-match"

#: Fidelity-gate annotations (TRANSCRIPTS.md §3), as they appear in the annotated transcript.
FIDELITY_GLOSSARY_MATCH_RE = re.compile(r'\[FIDELITY:\s*glossary-match\s+"([^"]+)"')
FIDELITY_NO_MATCH_RE = re.compile(r"\[FIDELITY:\s*no-glossary-match")

#: Fields where an item is a commitment the agency plans against (SOURCES.md §5 background row).
COMMITMENT_FIELDS = ("deliverables", "timeline", "budget")

#: The linked_items reference format (SOURCES.md §4): zero-based index into this extract.
ITEM_REF_RE = re.compile(r"^(?P<field>[a-z_]+)\[(?P<index>\d+)\]$")


def _norm(text: str) -> str:
    return gates.normalise_for_match(text or "").casefold()


def garble_notes(extract: dict) -> list:
    """Every structured rule-G note of an extract: [{token, location, match, note}]."""
    notes = []
    for note in extract.get("extraction_notes") or []:
        match = GARBLE_NOTE_RE.match(note or "") if isinstance(note, str) else None
        if match:
            notes.append({"token": match.group("token").strip(),
                          "location": match.group("location").strip(),
                          "match": match.group("match").strip(), "note": note})
    return notes


def items_carrying(extract: dict, token: str) -> Iterator[tuple]:
    """(path, item) for every evidence item whose value or anchor carries `token`."""
    needle = _norm(token)
    if not needle:
        return
    for path, item in gates.extract_items(extract):
        if needle in _norm(item.get("value")) or needle in _norm(item.get("anchor")):
            yield path, item


def _garbled_paths(extract: dict) -> set:
    return {path for note in garble_notes(extract) for path, _ in items_carrying(extract, note["token"])}


def rule_confidence_semantics(extract: dict) -> list:
    """One meaning per confidence level, with the two named overrides (SOURCES.md §4)."""
    violations = []
    garbled = _garbled_paths(extract)
    for fieldname in gates.BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname) or []):
            path = f"{fieldname}[{idx}]"
            qualifier, confidence = item.get("qualifier"), item.get("confidence")
            if qualifier == "implied" and confidence != "low":
                violations.append(
                    f"{path}: qualifier 'implied' with confidence {confidence!r} — an implied item "
                    f"is `low` by definition (SOURCES.md §4 confidence definitions)")
            elif qualifier == "conditional" and confidence == "high":
                violations.append(
                    f"{path}: qualifier 'conditional' with confidence 'high' — speculation, a "
                    f"condition or a retraction is never an explicit commitment: use 'medium' or "
                    f"'low' (SOURCES.md §4)")
            elif (qualifier == "stated" and confidence == "low" and path not in garbled
                  and fieldname != "mandatories"):
                violations.append(
                    f"{path}: a 'stated' item at confidence 'low' — `low` on a stated item is "
                    f"reserved for the two overrides: G (the value carries a garbled token with its "
                    f"`garble:` note) and M (a mandatory). Otherwise use 'medium' for a hedged or "
                    f"vague statement (SOURCES.md §4)")
    return violations


def rule_linked_questions(extract: dict) -> list:
    """Every medium/low item is linked from an open question; every link resolves (SOURCES.md §4)."""
    violations = []
    linked = set()
    for q_idx, question in enumerate(extract.get("open_questions") or []):
        for ref in question.get("linked_items") or []:
            match = ITEM_REF_RE.match(str(ref).strip())
            items = extract.get(match.group("field")) if match else None
            if (not match or match.group("field") not in gates.BRIEF_FIELDS
                    or not isinstance(items, list) or int(match.group("index")) >= len(items)):
                violations.append(
                    f"open_questions[{q_idx}].linked_items: {str(ref)[:40]!r} names no item of this "
                    f"extract — a link is '<field>[<index>]', zero-based, e.g. 'budget[0]' "
                    f"(SOURCES.md §4)")
            else:
                linked.add(f"{match.group('field')}[{int(match.group('index'))}]")
    for fieldname in gates.BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname) or []):
            path = f"{fieldname}[{idx}]"
            if item.get("confidence") in ("medium", "low") and path not in linked:
                violations.append(
                    f"{path}: confidence {item.get('confidence')!r} but no open question links it — "
                    f"every medium or low item is named in some open_questions[].linked_items as "
                    f"'{path}' (SOURCES.md §4, self-check 3)")
    return violations


def rule_garble(extract: dict, source_text: str = "", annotated_text: str = "") -> list:
    """Rule G as data: notes quote real tokens, garbled items are `low`, every flag has a note."""
    violations = []
    notes = garble_notes(extract)
    haystack = _norm(source_text) if source_text else ""
    for note in notes:
        if haystack and _norm(note["token"]) not in haystack:
            violations.append(
                f"extraction note {note['note'][:60]!r}: the token «{note['token'][:40]}» does not "
                f"occur in the source — a garble note copies the token exactly as the source "
                f"writes it (SOURCES.md §7 rule G)")
        for path, item in items_carrying(extract, note["token"]):
            if item.get("confidence") != "low":
                violations.append(
                    f"{path}: carries the garbled token «{note['token'][:40]}» at confidence "
                    f"{item.get('confidence')!r} — an item that carries a rule-G token is `low` "
                    f"(SOURCES.md §4 override G, §7 rule G)")
    if annotated_text:
        proposed = {n["match"].casefold() for n in notes}
        for term in dict.fromkeys(FIDELITY_GLOSSARY_MATCH_RE.findall(annotated_text)):
            if term.strip().casefold() not in proposed:
                violations.append(
                    f"the fidelity gate flagged a token with glossary match \"{term}\" but no "
                    f"extraction note carries it — write one note per flagged token: "
                    f"garble: «<token as written>» at <location> — proposed match \"{term}\" "
                    f"(SOURCES.md §7 rule G)")
        if FIDELITY_NO_MATCH_RE.search(annotated_text) and NO_GLOSSARY_MATCH not in proposed:
            violations.append(
                f"the fidelity gate flagged a token with no glossary match but no extraction note "
                f"carries it — write: garble: «<token as written>» at <location> — proposed match "
                f"\"{NO_GLOSSARY_MATCH}\" (SOURCES.md §7 rule G)")
    return violations


def rule_background_commitments(extract: dict, source_type: Optional[str] = None) -> list:
    """A background document never creates a commitment on its own (SOURCES.md §5)."""
    source_type = source_type or (extract.get("meta") or {}).get("source_type")
    if source_type != "background":
        return []
    violations = []
    for fieldname in COMMITMENT_FIELDS:
        for idx, item in enumerate(extract.get(fieldname) or []):
            if item.get("qualifier") != "implied":
                violations.append(
                    f"{fieldname}[{idx}]: a background document's {fieldname} item with qualifier "
                    f"{item.get('qualifier')!r} — background is context, never a commitment: an item "
                    f"it yields under deliverables, timeline or budget is 'implied' (hence `low`, "
                    f"with a linked question on whether it applies) (SOURCES.md §5)")
    return violations


def check_extract_rules(extract: dict, source_text: str = "", annotated_text: str = "",
                        source_type: Optional[str] = None) -> list:
    """All four rule families, in reporting order."""
    return (rule_confidence_semantics(extract)
            + rule_linked_questions(extract)
            + rule_garble(extract, source_text, annotated_text)
            + rule_background_commitments(extract, source_type))
