#!/usr/bin/env python3
"""Derive the offline-replay recording `recordings/northlight_01/` from `runs/tier3`.

`runs/tier3` is the graded evidence pack, but it is the run's FINAL state: after the model
stages, a human resolved the three conflicts and signed the brief off, and the brief was
re-rendered. A Stage-1 replay needs the state the model stages produced BEFORE any human
act, so this script reverses exactly the human layer and nothing else:

* brief.json    — drop the runner-injected `readiness` block (the runner recomputes it),
                  `signoff` back to `{"status": "draft"}`, every conflict back to `open`
                  with its human `resolution` / `resolved_by` removed.
* brief_*.md    — the sign-off banner and the sign-off line back to the draft wording the
                  model uses for an unsigned brief (taken verbatim from the draft renders in
                  runs/voreas-prep-03), conflict status back to open, and the human
                  "Resolution" / "Resolved by" lines removed. No other line is touched.
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
SOURCE_RUN = REPO_ROOT / "runs" / "tier3"
TARGET = Path(__file__).resolve().parent / "recordings" / "northlight_01"

#: Per render: banner (signed prefix -> draft banner), conflict status (signed -> open), the
#: human-only line prefixes to drop, and the sign-off line (prefix -> unsigned draft line).
RENDER_EDITS = {
    "brief_en.md": {
        "banner": ("> **SIGNED OFF", "> **DRAFT — pending account-lead sign-off**"),
        "status": ("— status: resolved by human", "— status: open"),
        "human_lines": ("- Resolution:", "- Resolved by:"),
        "signoff": ("Account lead:",
                    "Account lead: ____________  Date: ________  Edits made: none — initial draft render."),
    },
    "brief_el.md": {
        "banner": ("> **ΥΠΟΓΕΓΡΑΜΜΕΝΟ", "> **DRAFT — εκκρεμεί έγκριση account lead**"),
        "status": ("— κατάσταση: επιλύθηκε από άνθρωπο", "— κατάσταση: ανοιχτή"),
        "human_lines": ("- Επίλυση:", "- Επιλύθηκε από:"),
        "signoff": ("Account lead:",
                    "Account lead: ____________  Ημερομηνία: ________  Αλλαγές: καμία — αρχικό draft render."),
    },
}


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


def pre_signoff_render(text: str, edits: dict) -> str:
    """Reverse the human layer in one render; fail loudly if the render is not as expected."""
    banner_prefix, draft_banner = edits["banner"]
    signed_status, open_status = edits["status"]
    signoff_prefix, draft_signoff = edits["signoff"]
    out, counts = [], {"banner": 0, "signoff": 0}
    for line in text.splitlines():
        if line.startswith(banner_prefix):
            out.append(draft_banner)
            counts["banner"] += 1
        elif line.startswith(edits["human_lines"]):
            continue
        elif line.startswith(signoff_prefix):
            out.append(draft_signoff)
            counts["signoff"] += 1
        else:
            out.append(line.replace(signed_status, open_status))
    if counts != {"banner": 1, "signoff": 1}:
        raise SystemExit(f"unexpected render shape, edits applied: {counts}")
    return "\n".join(out) + "\n"


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
    for name, edits in RENDER_EDITS.items():
        text = (SOURCE_RUN / name).read_text(encoding="utf-8")
        (out / name).write_text(pre_signoff_render(text, edits), encoding="utf-8")
    verification = out / "verification"
    verification.mkdir()
    for extract in sorted((out / "extracts").glob("*.json")):
        report = {"source_id": extract.stem, "verdict": "confirms", "issues": [],
                  "note": "Synthesised for offline replay: no model reviewed this extract."}
        (verification / f"{extract.stem}.verify.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
