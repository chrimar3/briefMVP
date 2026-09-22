"""Pilot documents stay executable and consistent: documented commands run, cited files exist."""

import re
import shlex

from pipeline import agency_edit, revisions


def _sh_blocks(text):
    return re.findall(r"```sh\n(.*?)```", text, flags=re.S)


def test_campaign_editing_deliverable_example_runs_as_documented(tmp_path, repo_root):
    """Regression: the documented --dependency used free text, which validation rejects."""
    from test_agency_operations import make_review_run
    run = make_review_run(tmp_path)
    text = (repo_root / "docs" / "pilot" / "CAMPAIGN_EDITING.md").read_text(encoding="utf-8")
    block = next(b for b in _sh_blocks(text) if "agency_edit deliverable" in b)
    commands = [c for c in block.replace("\\\n", " ").splitlines() if c.strip()]
    assert len(commands) == 2
    for command in commands:
        argv = shlex.split(command.replace("RUN", str(run)))
        assert argv[:3] == ["python", "-m", "pipeline.agency_edit"]
        assert agency_edit.main(argv[3:]) == 0, command
    rows = {r["id"]: r for r in revisions.load(run / "agency_inputs.json")["deliverables"]}
    assert rows["synthetic-story"]["dependencies"] == ["synthetic-artwork"]


def test_pilot_pack_cross_references_resolve(repo_root):
    pilot = repo_root / "docs" / "pilot"
    for name in ("PILOT_RUNBOOK.md", "ROLES.md", "GO_LIVE_DECISIONS.md", "INCIDENT_RECOVERY.md", "DATA_PROTECTION.md",
                 "SCORECARD.md", "OPERATING_TERMS.md", "CREATIVE_DELIVERY.md", "BRIEF_CHAMPION_RUNBOOK.md"):
        text = (pilot / name).read_text(encoding="utf-8")
        for ref in set(re.findall(r"`([A-Z_]+\.md)`", text)):
            assert any((d / ref).is_file() for d in (pilot, repo_root / "docs", repo_root)), f"{name} cites missing {ref}"
        for ref in set(re.findall(r"`((?:pipeline|eval|runs|fixtures|config|schema)/[\w./-]+)`", text)):
            path = repo_root / ref.rstrip("/")
            if "<" in ref or "*" in ref or ref in ("runs/routing-validate-01",):  # cited as not committed
                continue
            assert path.exists(), f"{name} cites missing {ref}"


def test_every_go_live_id_cited_in_the_pack_is_defined(repo_root):
    pilot = repo_root / "docs" / "pilot"
    sheet = (pilot / "GO_LIVE_DECISIONS.md").read_text(encoding="utf-8")
    defined = set(re.findall(r"^\| ([DRT]-\d+) \|", sheet, flags=re.M))
    assert {"D-01", "D-07", "R-6", "T-01"} <= defined
    for path in pilot.glob("*.md"):
        for ref in set(re.findall(r"\b([DRT]-\d{1,2})\b", path.read_text(encoding="utf-8"))):
            assert ref in defined, f"{path.name} cites undefined {ref}"


def test_legal_judgements_are_marked_for_confirmation(repo_root):
    text = (repo_root / "docs" / "pilot" / "DATA_PROTECTION.md").read_text(encoding="utf-8")
    assert text.count("OWNER/DPO TO CONFIRM") >= 8
    for heading in ("Lawful basis", "DPIA", "Retention schedule", "Data-subject rights", "Art. 28",
                    "Purpose limitation", "Special-category", "minimisation"):
        assert heading in text, heading
