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

Classification, fidelity and extract files are copied byte for byte. The result is a
replay fixture, not evidence: it is never graded and never cited as a model result.

Usage: python3 tools/replay/derive_recording.py [OUT_DIR]   (idempotent; default rewrites the recording)
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import gates, quality  # noqa: E402
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
    for folder in ("fidelity", "extracts"):
        shutil.copytree(SOURCE_RUN / folder, out / folder)
    brief = json.loads((SOURCE_RUN / "brief.json").read_text(encoding="utf-8"))
    (out / "brief.json").write_text(
        json.dumps(pre_human_brief(brief), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    draft = pre_human_brief(brief)
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
