"""Pilot documents stay executable and consistent: documented commands run, cited files exist."""

import re
import shlex

import pytest

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
                 "SCORECARD.md", "OPERATING_TERMS.md", "CREATIVE_DELIVERY.md", "BRIEF_CHAMPION_RUNBOOK.md",
                 "PILOT_INVESTMENT.md", "PILOT_REPORT_TEMPLATE.md", "ACCOUNT_LEAD_CARD.md", "GLOSSARY_BUILDING.md"):
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


# -- round 2 (W-P) ---------------------------------------------------------------------------

def _pilot(repo_root, name):
    return (repo_root / "docs" / "pilot" / name).read_text(encoding="utf-8")


def test_pilot_docs_cite_other_files_by_phrase_not_line_number(repo_root):
    """Line numbers in other files drift (round-1 finding: OPERATING_TERMS cited lines that had moved)."""
    line_ref = re.compile(r"\blines? \d+\b|`[\w./-]+\.(?:py|md|json|log|svg|html|csv)` \d+(?![\d-])")
    for path in (repo_root / "docs" / "pilot").glob("*.md"):
        hits = line_ref.findall(path.read_text(encoding="utf-8"))
        assert not hits, f"{path.name} cites line numbers: {hits}"


def test_runbook_routes_every_runner_exit_code_and_outcome(repo_root):
    from pipeline import runner
    table = _pilot(repo_root, "PILOT_RUNBOOK.md")
    rows = re.findall(r"^\| (\d) \| (.+?) \|", table, flags=re.M)
    codes = {int(code) for code, _ in rows}
    exits = {getattr(runner, name) for name in dir(runner) if name.startswith("EXIT_")}
    assert exits <= codes, f"exit codes missing from the runbook table: {sorted(exits - codes)}"
    source = (repo_root / "pipeline" / "runner.py").read_text(encoding="utf-8")
    outcomes = set(re.findall(r'_write_manifest\("(\w+)"', source)) | set(re.findall(r'return "(\w+)", EXIT_', source))
    listed = " ".join(outcome for _, outcome in rows)
    missing = sorted(o for o in outcomes if f"`{o}`" not in listed)
    assert not missing, f"runner outcomes with no route in PILOT_RUNBOOK.md: {missing}"


def test_go_live_sheet_carries_the_cost_ceiling_and_owned_fallbacks(repo_root):
    sheet = _pilot(repo_root, "GO_LIVE_DECISIONS.md")
    rows = {m.group(1): m.group(0) for m in re.finditer(r"^\| ([DRT]-\d+) \|.*$", sheet, flags=re.M)}
    assert "No start" in rows["D-27"] and "Before week 1" in rows["D-27"]
    for ref in ("T-03", "D-06"):
        assert "Fallback" in rows[ref] or "fallback" in rows[ref], ref
    assert "Before week 1" in rows["D-16"]
    assert {"T-07", "T-08", "D-28"} <= set(rows)


def test_investment_worksheet_adds_up_and_roles_quote_it(repo_root):
    text = _pilot(repo_root, "PILOT_INVESTMENT.md")
    section = text.split("## 1.")[1].split("## 2.")[0]
    ranges = re.findall(r"^\|[^\n]*\| \*{0,2}(\d+\.\d) – (\d+\.\d) h[^|\n]*\*{0,2} \|$", section, flags=re.M)
    *roles, total = [(float(a), float(b)) for a, b in ranges]
    assert len(roles) == 9
    assert sum(a for a, _ in roles) == pytest.approx(total[0], abs=0.15)
    assert sum(b for _, b in roles) == pytest.approx(total[1], abs=0.15)
    quoted = re.findall(r"\| (\d+(?:\.\d)?) – (\d+(?:\.\d)?) h", _pilot(repo_root, "ROLES.md"))
    assert len(quoted) == 9
    assert sorted((float(a), float(b)) for a, b in quoted) == sorted(roles)


def test_data_protection_pack_has_the_greek_and_art_30_items(repo_root):
    text = _pilot(repo_root, "DATA_PROTECTION.md")
    for needle in ("Art. 30", "Decision 65/2018", "Law 4624/2019 Art. 27", "--no-session-persistence",
                   "pipeline/prescreen.py", "screened_by", "processor_ref", "dpia_ref", "Classify"):
        assert needle in text, needle


def test_front_door_headline_says_review_ready_draft(repo_root):
    page = (repo_root / "START_HERE.html").read_text(encoding="utf-8")
    headline = re.search(r'<p class="mast-sub">(.*?)</p>', page, flags=re.S).group(1)
    assert "review-ready draft" in headline and "client-ready" not in headline
