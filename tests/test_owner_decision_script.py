"""The owner's part-1 decision script for runs/r2-live/nl-r1, rehearsed on a temporary copy.

`runs/r2-live/nl-r1/owner_decisions_part1.sh` is prepared for the owner (Christos Maragkoudakis)
to run himself. This test never touches the real run: it copies it to a temp dir, applies the
three owner-approved conflict resolutions there (the owner records them on the real run with
`agency resolve`; conflicts he has already resolved are left as they are), runs the script
against the copy, and checks that the audit then blocks only on what part 1 is not meant to
clear — the bilingual attestation and the render blockers the orchestrator's re-render fixes.

Human-decision commands run here only inside pytest temp dirs (r2 PLAN rule 9). Skipped when the
live run is absent (it is ignored by git; clean checkouts and CI do not have it).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from pipeline import agency

REPO = Path(__file__).resolve().parents[1]
LIVE = REPO / "runs" / "r2-live" / "nl-r1"
SCRIPT = LIVE / "owner_decisions_part1.sh"
ACTOR = "Christos Maragkoudakis"

#: The owner-approved resolution texts, by conflict index (audiences, timeline, budget).
RESOLUTIONS = {
    0: "Primary audience: 25-40 urban professionals, per the CMO at kickoff [00:03:41]; the RFP's Gen Z 18-24 is "
       "superseded. Ask the client whether TikTok-first still fits this audience.",
    1: "Launch 15 September 2026, per the board decision in Dimitris's email of 14 July, which supersedes the RFP's "
       "first week of October.",
    2: "Production budget around eighty, units and currency to be confirmed with the CFO, excluding media; the RFP's "
       "90.000 including media is not reconciled and goes back to the client.",
}

LANGUAGE_REVIEW = "Current source-completeness, bilingual meaning, qualifiers and brand-voice human review required"
RENDER_BLOCKER = re.compile(r"^(?:(?:el|en): |no (?:el|en) render at )")
RENDER_CITATION = re.compile(r"^(?:el|en): question \d+ lacks its linked evidence citation$")

pytestmark = pytest.mark.skipif(not (LIVE / "brief.json").is_file() or not SCRIPT.is_file(),
                                reason="runs/r2-live/nl-r1 (live run, git-ignored) is not present")


def _copy(tmp_path: Path) -> Path:
    run = tmp_path / "nl-r1"
    shutil.copytree(LIVE, run, symlinks=True)
    return run


def _resolve_open_conflicts(run: Path) -> None:
    """Apply the owner-approved texts to the conflicts still open in the copy."""
    brief = json.loads((run / "brief.json").read_text(encoding="utf-8"))
    for index, conflict in enumerate(brief["conflicts"]):
        if conflict.get("status") != "resolved_by_human":
            agency.resolve(run, index, ACTOR, RESOLUTIONS[index])


def _restore_current_renders(run: Path) -> None:
    """`agency resolve` archives the renders until the orchestrator re-renders; put the latest
    archived ones back so the audit sees the render text as it currently reads."""
    for lang in ("el", "en"):
        target = run / f"brief_{lang}.md"
        if target.exists():
            continue
        archived = sorted((run / "history").glob(f"*/brief_{lang}.md"))
        if archived:
            shutil.copy2(archived[-1], target)


def _run_script(run: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(SCRIPT), str(run)], capture_output=True, text=True, timeout=600)


def test_part_one_leaves_only_the_language_review_and_render_blockers(tmp_path):
    run = _copy(tmp_path)
    _resolve_open_conflicts(run)
    result = _run_script(run)
    assert result.returncode == 0, result.stderr + result.stdout
    _restore_current_renders(run)

    blockers = agency.audit(run, persist=False)["blockers"]
    others = [b for b in blockers if b != LANGUAGE_REVIEW and not RENDER_BLOCKER.match(b)]
    assert others == [], "part 1 should clear these:\n" + "\n".join(others)
    assert LANGUAGE_REVIEW in blockers                      # part 2: a named bilingual reviewer attests
    render = [b for b in blockers if RENDER_BLOCKER.match(b)]
    assert render and all(RENDER_CITATION.match(b) for b in render), render


def test_part_one_records_what_it_says_it_records(tmp_path):
    run = _copy(tmp_path)
    _resolve_open_conflicts(run)
    assert _run_script(run).returncode == 0

    triage = json.loads((run / "clarifications.json").read_text(encoding="utf-8"))
    assert len(triage) == 17 and {d["actor"] for d in triage.values()} == {ACTOR}
    statuses = sorted(d["status"] for d in triage.values())
    assert statuses.count("duplicate") == 3 and statuses.count("not_worth_asking") == 1
    assert all(d["priority"] == "nonblocking" and d["evidence"].strip() for d in triage.values())

    exclusions = json.loads((run / "coverage_decisions.json").read_text(encoding="utf-8"))
    assert set(exclusions) == {"5767ac568d35a72da201", "2c0483441abf06863030"}

    inputs = json.loads((run / "agency_inputs.json").read_text(encoding="utf-8"))
    assert inputs["campaign_profile"] == "paid_campaign"
    assert all(row["actor"] == ACTOR and row["evidence"] for row in inputs["checklist"].values())
    assert [row["id"] for row in inputs["deliverables"]] == ["kv-master-01"]
    # Nothing the sources do not give is presented as a client fact.
    unsupported = ("landing_page", "tracking_owner", "conversion_and_kpi")
    assert all(inputs["checklist"][k]["value"].startswith("To confirm with client") for k in unsupported)


def test_the_guard_refuses_before_recording_anything_while_a_conflict_is_open(tmp_path):
    run = _copy(tmp_path)
    brief_path = run / "brief.json"
    brief = json.loads(brief_path.read_text(encoding="utf-8"))
    brief["conflicts"][2]["status"] = "open"                  # the guard reads only this file
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8")
    before = {p.name: p.stat().st_mtime_ns for p in run.iterdir() if p.is_file()}

    result = _run_script(run)
    assert result.returncode != 0
    assert "STOP" in result.stderr and "still open" in result.stderr
    after = {p.name: p.stat().st_mtime_ns for p in run.iterdir() if p.is_file()}
    assert after == before
