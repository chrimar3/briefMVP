#!/usr/bin/env python3
"""Derive the offline-replay recording `recordings/northlight_01/` from `runs/tier3`.

`runs/tier3` is the graded evidence pack, but it is the run's FINAL state: after the model
stages, a human resolved the three conflicts and signed the brief off, and the brief was
re-rendered. A Stage-1 replay needs the state the model stages produced BEFORE any human
act, so this script reverses exactly the human layer and nothing else:

* brief.json    — drop the runner-injected `readiness` block (the runner recomputes it),
                  `signoff` back to `{"status": "draft"}`, every conflict back to `open`
                  with its human `resolution` / `resolved_by` removed.
* brief_*.md    — NOT copied. The graded renders predate the current client-brief template
                  (templates/northlight_client_brief*.md), which the render stage now gates
                  with the blocking `check_render_template`. So both renders are generated
                  deterministically from the recording's own brief.json and the template's
                  label table (`render_from_template` below): fixed headings, draft banner,
                  one line per entry with its exact `[source_id location]` tags, numbered
                  open questions, conflicts, internal section last. The entry text is the
                  brief's content verbatim in BOTH files — the Greek file carries Greek
                  boilerplate around untranslated content. These are wiring fixtures that
                  satisfy the gates, not translations and not evidence of render quality.
* verification/ — the graded run predates the independent verifier (step 4b), so one
                  `confirms` report per source is written, marked as synthesised by replay.

* extracts/ + brief.json — brought to the round-2 prompt contract (r2-W-R), which postdates the
                  graded run, so replay exercises today's gates: `round2_extract` turns each
                  free-form rule-G note into the structured `garble:` note, sets confidence by
                  the SOURCES.md §4 definitions and links every medium/low item from an open
                  question (adding a question marked as a replay edit where none fits);
                  `round2_brief` keeps each garbled token visible beside its proposed match at
                  the garbled item's confidence (SYNTHESIS.md rule 10). An extract these edits
                  leave unchanged is copied byte for byte.

Classification and fidelity files are copied byte for byte. The result is a replay fixture,
not evidence: it is never graded and never cited as a model result.

Usage: python3 tools/replay/derive_recording.py [OUT_DIR]   (idempotent; default rewrites the recording)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import extract_rules, gates, quality  # noqa: E402

SOURCE_RUN = REPO_ROOT / "runs" / "tier3"
TARGET = Path(__file__).resolve().parent / "recordings" / "northlight_01"

TEMPLATE = "northlight_client_brief"
TEMPLATES_DIR = REPO_ROOT / "templates"
GLOSSARY = REPO_ROOT / "glossary" / "meltemi.json"

#: Localised values for the internal section and fixed words the label table does not carry.
#: Mirrors the {…} alternatives written in templates/northlight_client_brief(.el).md.
LOCAL = {
    "en": {"project_type": {"advertising_creative": "Advertising creative", "other": "Other",
                            "unclassified_ask_human": "Unclassified — ask the account lead"},
           "readiness": {"ready_for_review": "Ready for review",
                         "thin_input_return_to_client": "⚠ Thin input — return to the client"},
           "gap": "Gap", "why": "Why it matters", "ask": "Suggested question", "field": "Field",
           "status": "status", "open": "open", "position": "Position", "letters": "ABCDEFGH",
           "signoff": "Account lead: ____________  Date: ________  Edits made: "},
    "el": {"project_type": {"advertising_creative": "Δημιουργικό διαφήμισης", "other": "Άλλο",
                            "unclassified_ask_human": "Χωρίς κατηγοριοποίηση — ρωτήστε τον account lead"},
           "readiness": {"ready_for_review": "Έτοιμο για έλεγχο",
                         "thin_input_return_to_client": "⚠ Ελλιπή στοιχεία — επιστροφή στον πελάτη"},
           "gap": "Κενό", "why": "Γιατί έχει σημασία", "ask": "Προτεινόμενη ερώτηση", "field": "Πεδίο",
           "status": "κατάσταση", "open": "ανοιχτή", "position": "Θέση", "letters": "ΑΒΓΔΕΖΗΘ",
           "signoff": "Account lead: ____________  Ημερομηνία: ________  Αλλαγές: "},
}


def tag(ref: dict) -> str:
    """`[source_id location]`; a location written in brackets (`[00:03:41]`) loses one pair,
    exactly as the agency render check reads it (`pipeline.quality.tag_location`)."""
    return f"[{ref.get('source_id', '')} {quality.tag_location(ref.get('location'))}]"


def _client_name(brief: dict, glossary: dict) -> str:
    """The client company as the glossary writes it (a keep_latin term), never the raw id."""
    wanted = (brief.get("meta") or {}).get("client_id", "").replace("_", " ").lower()
    for term in glossary.get("terms") or []:
        if term.get("term", "").lower() == wanted:
            return term["term"]
    raise SystemExit(f"glossary {GLOSSARY} names no company matching client_id {wanted!r}")


def render_from_template(brief: dict, labels: dict, lang: str, glossary: dict) -> str:
    """One draft render of `brief` in the template's fixed `lang` boilerplate (wiring fixture)."""
    lab, loc, meta = labels[lang], LOCAL[lang], brief.get("meta") or {}
    readiness = gates.compute_readiness_block(brief)
    sources = " · ".join(f"{s['source_id']} ({s['source_date']})" for s in meta.get("sources") or [])
    project_label = "**Project:**" if lang == "en" else "**Έργο:**"
    out = [lab["title"], "", lab["banner_draft"], "",
           f"{lab['header_client']} {_client_name(brief, glossary)} · {project_label} {meta.get('project_id')}",
           f"{lab['header_sources']} {sources}", ""]
    for fieldname in gates.BRIEF_FIELDS:
        out.append(lab["sections"][fieldname])
        entries = brief.get(fieldname) or []
        if not entries:
            out.append(lab["empty_section"])
        for entry in entries:
            tags = " ".join(tag(ref) for ref in entry.get("evidence") or [])
            out.append(f"- {entry['content']} {tags}")
        out.append("")
    questions = brief.get("open_questions") or []
    if questions:
        out += [lab["open_questions"], ""]
        for number, question in enumerate(questions, 1):
            tags = " ".join(tag(ref) for ref in question.get("linked_evidence") or [])
            out += [f"{number}. **{question['field']}**",
                    f"   {loc['gap']}: {question['gap']} {tags}",
                    f"   {loc['why']}: {question['why_it_matters']}",
                    f"   {loc['ask']}: «{question['suggested_question_for_client']}»", ""]
    conflicts = brief.get("conflicts") or []
    if conflicts:
        if any(c.get("status") != "open" for c in conflicts):
            raise SystemExit("the recording renders a pre-resolution draft; a conflict is not open")
        out += [lab["conflicts_open"], ""]
        for conflict in conflicts:
            out.append(f"**{loc['field']}: {conflict['field']}** — {loc['status']}: {loc['open']}")
            for letter, position in zip(loc["letters"], conflict.get("positions") or []):
                out.append(f"- {loc['position']} {letter}: {position['statement']} {tag(position['evidence'])}")
            out.append("")
    labels_internal = lab["internal_labels"]
    out += [lab["signoff"], loc["signoff"].rstrip(), "", lab["internal"],
            f"{labels_internal[0]} {loc['project_type'][meta.get('project_type')]} · "
            f"{labels_internal[1]} {meta.get('sensitivity_tier')}",
            f"{labels_internal[2]} {readiness['fields_with_evidence']}/7 · "
            f"{labels_internal[3]} {loc['readiness'][readiness['verdict']]}",
            f"{labels_internal[4]} {meta.get('created_ts')} · {labels_internal[5]} {meta.get('pipeline_version')}"]
    return "\n".join(out) + "\n"


def pre_human_brief(brief: dict) -> dict:
    """The brief as synthesis wrote it: before readiness injection, resolution and sign-off."""
    brief = json.loads(json.dumps(brief))
    brief.pop("readiness", None)
    brief["signoff"] = {"status": "draft"}
    for conflict in brief.get("conflicts") or []:
        conflict["status"] = "open"
        conflict.pop("resolution", None)
        conflict.pop("resolved_by", None)
    return brief


_OLD_GARBLE_NOTE = re.compile(r"^\[(?P<loc>\d{1,2}:\d{2}(?::\d{2})?)\][^']*Token '(?P<token>[^']+)'")
_REPLAY_MARK = "Replay wiring edit (round-2 extract contract), not model output"


def _proposed_match(annotated: str, token: str) -> str:
    """The fidelity gate's proposal for `token`: the glossary-match annotation right after it."""
    found = re.search(re.escape(token) + r'\s*\[FIDELITY:\s*glossary-match\s+"([^"]+)"', annotated)
    return found.group(1) if found else extract_rules.NO_GLOSSARY_MATCH


def round2_extract(extract: dict, annotated: str = "") -> dict:
    """The graded extract brought to the round-2 contract (SOURCES.md §4, §7 rule G).

    Mechanical, documented edits only — the graded run predates the contract, and replay must
    exercise today's gates (pipeline/extract_rules.py): (1) each free-form rule-G note becomes
    the structured `garble:` note, token and location from the note, proposed match from the
    fidelity annotation; (2) confidence follows the §4 definitions: an item carrying a garbled
    token or qualified `implied` is `low`, a `conditional` one is never `high`, a `stated` `low`
    outside the overrides is `medium`; (3) every medium/low item is linked from the first open
    question of its field, or from a question added for it and marked as a replay edit.
    """
    extract = json.loads(json.dumps(extract))
    notes = []
    for note in extract.get("extraction_notes") or []:
        old = _OLD_GARBLE_NOTE.match(note)
        if old and "garble:" not in note:
            token = old.group("token")
            notes.append(f"garble: «{token}» at [{old.group('loc')}] — proposed match "
                         f"\"{_proposed_match(annotated, token)}\" ({_REPLAY_MARK})")
        else:
            notes.append(note)
    extract["extraction_notes"] = notes
    garbled = {path: note for note in extract_rules.garble_notes(extract)
               for path, _ in extract_rules.items_carrying(extract, note["token"])}
    for fieldname in gates.BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname) or []):
            path = f"{fieldname}[{idx}]"
            if path in garbled or item.get("qualifier") == "implied":
                item["confidence"] = "low"
            elif item.get("qualifier") == "conditional" and item.get("confidence") == "high":
                item["confidence"] = "medium"
            elif (item.get("qualifier") == "stated" and item.get("confidence") == "low"
                  and fieldname != "mandatories"):
                item["confidence"] = "medium"
    questions = extract.setdefault("open_questions", [])
    linked = {ref for q in questions for ref in q.get("linked_items") or []}
    for fieldname in gates.BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname) or []):
            path = f"{fieldname}[{idx}]"
            if item.get("confidence") not in ("medium", "low") or path in linked:
                continue
            note = garbled.get(path)
            host = None if note else next((q for q in questions if q.get("field") == fieldname), None)
            if host is None:
                ask = (f"By «{note['token']}», do you mean \"{note['match']}\"?" if note
                       else f"Can you confirm this {fieldname} point as stated?")
                host = {"field": fieldname, "gap": f"{_REPLAY_MARK}: confidence {item['confidence']}.",
                        "why_it_matters": "A medium or low item is confirmed before it is relied on.",
                        "suggested_question_for_client": ask, "linked_items": []}
                questions.append(host)
            host.setdefault("linked_items", []).append(path)
            linked.add(path)
    return extract


def round2_brief(brief: dict, extracts: dict) -> dict:
    """The recording's brief brought to SYNTHESIS.md rule 10 (garble carry-through): every entry
    or conflict position citing a garbled item shows the as-heard token beside its proposed
    match, and an entry takes the garbled item's confidence. Mechanical, documented edits."""
    brief = json.loads(json.dumps(brief))
    flagged = {}
    for source_id, extract in extracts.items():
        for note in extract_rules.garble_notes(extract):
            for _path, item in extract_rules.items_carrying(extract, note["token"]):
                flagged.setdefault((source_id, item["anchor"].strip()), []).append((note, item))

    def _carry(text: str, refs: list) -> tuple:
        lowest = None
        for ref in refs:
            for note, item in flagged.get((ref.get("source_id"), (ref.get("anchor") or "").strip()), []):
                if f"«{note['token']}»" not in text:
                    text += f" (heard as «{note['token']}»; proposed match \"{note['match']}\", unconfirmed)"
                lowest = item["confidence"]
        return text, lowest

    for fieldname in gates.BRIEF_FIELDS:
        for entry in brief.get(fieldname) or []:
            entry["content"], lowest = _carry(entry["content"], entry.get("evidence") or [])
            if lowest:
                entry["confidence"] = lowest
    for conflict in brief.get("conflicts") or []:
        for position in conflict.get("positions") or []:
            position["statement"], _ = _carry(position["statement"], [position.get("evidence") or {}])
    return brief


def main(argv: Optional[list] = None) -> int:
    """Rebuild the recording (default TARGET; an alternative output folder may be given)."""
    argv = sys.argv[1:] if argv is None else argv
    target = Path(argv[0]).resolve() if argv else TARGET
    derive(target)
    print(f"recording written to {target}")
    return 0


def derive(target: Path) -> None:
    """Write the pre-sign-off recording derived from SOURCE_RUN into `target`."""
    out = Path(target)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(SOURCE_RUN / "classification.json", out / "classification.json")
    shutil.copytree(SOURCE_RUN / "fidelity", out / "fidelity")
    (out / "extracts").mkdir()
    extracts = {}
    for path in sorted((SOURCE_RUN / "extracts").glob("*.json")):
        original = json.loads(path.read_text(encoding="utf-8"))
        annotated_file = SOURCE_RUN / "fidelity" / f"{path.stem}.annotated.md"
        annotated = annotated_file.read_text(encoding="utf-8") if annotated_file.is_file() else ""
        extracts[path.stem] = round2_extract(original, annotated)
        if extracts[path.stem] == original:
            shutil.copy2(path, out / "extracts" / path.name)  # untouched: byte for byte
        else:
            (out / "extracts" / path.name).write_text(
                json.dumps(extracts[path.stem], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    brief = json.loads((SOURCE_RUN / "brief.json").read_text(encoding="utf-8"))
    draft = round2_brief(pre_human_brief(brief), extracts)
    (out / "brief.json").write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    labels = json.loads((TEMPLATES_DIR / f"{TEMPLATE}.labels.json").read_text(encoding="utf-8"))
    glossary = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    for lang in ("en", "el"):
        (out / f"brief_{lang}.md").write_text(render_from_template(draft, labels, lang, glossary),
                                              encoding="utf-8")
    verification = out / "verification"
    verification.mkdir()
    for extract in sorted((out / "extracts").glob("*.json")):
        report = {"source_id": extract.stem, "verdict": "confirms", "issues": [],
                  "note": "Synthesised for offline replay: no model reviewed this extract."}
        (verification / f"{extract.stem}.verify.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
