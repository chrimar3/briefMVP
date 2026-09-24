"""Round-2 live regression cases: output defects in the committed runs/r2-live briefs that the
frozen harness scores as a pass (or, for nl-r3, as its one T1.4 failure).

Each case encodes a machine-checkable entry of runs/r2-live/KNOWN_DEFECTS.md, mirroring
tests/test_regression_northlight.py. Marking rule: a case the stored artifact fails is
xfail(strict=True, raises=AssertionError) naming its KNOWN_DEFECTS id, so the suite stays green
while the defect is on record; a regenerated artifact without the defect XPASSes and fails the
suite — the signal to drop the mark and update KNOWN_DEFECTS.md. Cases the artifacts already
satisfy pass outright (they guard the "no longer occurs" statements). Preconditions use
pytest.fail, so a changed artifact reports as a real failure, never as the expected one.

Reads (read-only): runs/r2-live/<run>/{brief.json, brief_el.md, brief_en.md, extracts/,
fidelity/, run_manifest.json}; the fixtures' sources through eval/supplementary.py. Never reads an
answer key. No model is called; nothing is regenerated or written.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "eval"))
sys.path.insert(0, str(REPO))
import supplementary as sup  # noqa: E402

from pipeline import greek_lint, render_checks  # noqa: E402

LIVE = REPO / "runs" / "r2-live"
DEFECTS = "runs/r2-live/KNOWN_DEFECTS.md"
BRIEFS = ("nl-r1", "nl-r2", "nl-r3", "vo-r2", "vo-r3", "lv-r1")


def _run(run: str) -> Path:
    path = LIVE / run
    if not (path / "brief.json").is_file():
        pytest.fail(f"{path.relative_to(REPO)} has no brief.json — the committed evidence changed")
    return path


def _brief(run: str) -> dict:
    return json.loads((_run(run) / "brief.json").read_text(encoding="utf-8"))


def _render(run: str, lang: str) -> str:
    return (_run(run) / f"brief_{lang}.md").read_text(encoding="utf-8")


def _xfail(run: str, reason: str):
    return pytest.param(run, marks=pytest.mark.xfail(strict=True, raises=AssertionError,
                                                     reason=f"{DEFECTS} {reason}"))


# ---- B1: questions re-ask open conflicts (supplementary S5) ----------------------------------------


@pytest.mark.parametrize("run", [_xfail(r, "B1") for r in BRIEFS])
def test_no_open_question_re_asks_an_open_conflict(run):
    result = sup.check_duplicate_questions(sup.load_run(_run(run)))
    assert result["status"] == "ok", result["items"][:3]


# ---- B2: a spoken hedged budget becomes "80–85" ---------------------------------------------------


@pytest.mark.parametrize("run", [_xfail(r, "B2") for r in ("nl-r1", "nl-r2", "nl-r3")])
def test_spoken_budget_is_never_rendered_as_a_numeral_range(run):
    text = json.dumps(_brief(run).get("open_questions"), ensure_ascii=False)
    assert not re.search(r"\b80\s?[–-]\s?85\b", text)


@pytest.mark.parametrize("run", ["nl-r1", "nl-r2", "nl-r3"])
def test_budget_entries_keep_the_spoken_words(run):
    """Guards the part that is right: entries and conflict positions keep the figure in words."""
    b = _brief(run)
    budget = json.dumps(b.get("budget"), ensure_ascii=False) + json.dumps(
        [c for c in b.get("conflicts") or [] if c.get("field") == "budget"], ensure_ascii=False)
    assert re.search(r"eighty|ογδόντα", budget), "spoken budget figure missing from budget entries"
    assert not re.search(r"\b80\s?[–-]\s?85\b", budget)


# ---- B3 / B4: misfiled deliverables --------------------------------------------------------------


@pytest.mark.parametrize("run", [_xfail(r, "B3") for r in ("vo-r2", "vo-r3")])
def test_no_deliverable_rests_on_the_brand_guidelines_alone(run):
    bad = [i for i, e in enumerate(_brief(run).get("deliverables") or [])
           if {r.get("source_id") for r in e.get("evidence") or []} == {"background_brand_guidelines"}]
    assert not bad, f"deliverables{bad} cite only the brand guidelines"


@pytest.mark.parametrize("run", ["nl-r1", _xfail("nl-r2", "B4"), _xfail("nl-r3", "B4")])
def test_tiktok_first_is_not_filed_as_a_deliverable(run):
    bad = [i for i, e in enumerate(_brief(run).get("deliverables") or [])
           if re.match(r"^(RFP:\s*)?TikTok-first", e.get("content") or "")]
    assert not bad, f"deliverables{bad} state the TikTok-first strategy"


# ---- B5: a stale question -----------------------------------------------------------------------


@pytest.mark.parametrize("run", [_xfail("vo-r2", "B5"), "vo-r3"])
def test_no_question_asks_about_a_date_before_the_brief_was_generated(run):
    b = _brief(run)
    generated = (b.get("meta") or {}).get("generated_ts") or (b.get("meta") or {}).get("created_ts") or ""
    if not generated:
        pytest.fail("brief meta has no generation timestamp")
    months = {"July": 7, "Ιουλίου": 7, "August": 8, "Αυγούστου": 8}
    stale = []
    for q in b.get("open_questions") or []:
        for day, month, year in re.findall(r"\b(\d{1,2}) (July|Ιουλίου|August|Αυγούστου) (\d{4})",
                                           q.get("suggested_question_for_client") or ""):
            if f"{year}-{months[month]:02d}-{int(day):02d}" < generated[:10]:
                stale.append(f"{day} {month} {year}")
    assert not stale, stale


# ---- E1: nl-r3's garble without a glossary proposal (harness T1.4) -----------------------------


def _garble_notes(run: str) -> list:
    extract = json.loads((_run(run) / "extracts" / "transcript_kickoff.json").read_text(encoding="utf-8"))
    return [str(n) for n in extract.get("extraction_notes") or [] if "μπραντ αγουέρνες" in str(n)]


@pytest.mark.parametrize("run", ["nl-r1", "nl-r2", _xfail("nl-r3", "E1")])
def test_garbled_brand_awareness_carries_its_glossary_proposal(run):
    notes = _garble_notes(run)
    if not notes:
        pytest.fail(f"{run}: no extraction note mentions the garbled token")
    assert any("brand awareness" in n for n in notes), notes


def test_nl_r3_root_cause_is_the_fidelity_annotation():
    """The E1 explanation in KNOWN_DEFECTS.md: haiku annotated no-glossary-match, the verifier flagged
    it, the extractor rejected the finding."""
    run = _run("nl-r3")
    annotated = (run / "fidelity" / "transcript_kickoff.annotated.md").read_text(encoding="utf-8")
    assert "μπραντ αγουέρνες [FIDELITY: no-glossary-match]" in annotated
    adjudication = json.loads((run / "verification" / "transcript_kickoff.adjudication.json")
                              .read_text(encoding="utf-8"))
    assert [d["decision"] for d in adjudication["decisions"]] == ["rejected"]
    for other in ("nl-r1", "nl-r2"):
        text = (_run(other) / "fidelity" / "transcript_kickoff.annotated.md").read_text(encoding="utf-8")
        assert 'glossary-match "brand awareness"' in text


# ---- R1: the per-question citation gate on renders made before it merged ------------------------


@pytest.mark.parametrize("run", [_xfail(r, "R1") if r != "nl-r3" else r for r in BRIEFS])
def test_renders_pass_the_per_question_citation_gate(run):
    path = _run(run)
    violations = render_checks.check_render_coverage(path / "brief_el.md", path / "brief_en.md", _brief(run))
    assert not violations, violations[:3]


# ---- R2–R5: Greek and client-facing text ---------------------------------------------------------


@pytest.mark.parametrize("run", [r if r != "lv-r1" else _xfail(r, "R2") for r in BRIEFS])
def test_greek_language_lint_is_clean(run):
    path = _run(run)
    warnings = greek_lint.render_language_warnings(path / "brief_el.md", path / "brief_en.md", _brief(run), {})
    assert not warnings, warnings


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{DEFECTS} R3")
def test_vo_r2_account_lead_takes_the_feminine_article():
    assert "από τον account lead" not in _render("vo-r2", "el")


@pytest.mark.xfail(strict=True, raises=AssertionError, reason=f"{DEFECTS} R4")
def test_vo_r2_inaudible_is_not_rendered_as_imperceptible():
    el = _render("vo-r2", "el")
    assert "ανεπαίσθητο (inaudible)" not in el and "ακουστό κενό" not in el


@pytest.mark.parametrize("run", [r if r != "vo-r2" else _xfail(r, "R5") for r in BRIEFS])
def test_renders_do_not_leak_entry_metadata(run):
    for lang, pattern in (("en", r"\((?:implied|stated|conditional),\s*(?:low|medium|high) confidence\)"),
                          ("el", r"\((?:υπονοούμενο|δηλωμένο),\s*(?:χαμηλή|μέτρια|υψηλή) βεβαιότητα\)")):
        assert not re.search(pattern, _render(run, lang)), lang


# ---- July defects that no longer occur (guards for the table in KNOWN_DEFECTS.md) ---------------


@pytest.mark.parametrize("run", ["nl-r1", "nl-r2", "nl-r3", "vo-r2", "vo-r3"])
def test_garbles_stay_visible_in_content_and_renders(run):
    """tier3 B3 no longer occurs: supplementary S3 is ok (lv-r1's S3 flags are a scorer false positive,
    see KNOWN_DEFECTS.md)."""
    assert sup.check_garble_visibility(sup.load_run(_run(run)))["status"] == "ok"


@pytest.mark.parametrize("run", BRIEFS)
def test_no_decade_range_hedge_drift(run):
    """tier3 B7 no longer occurs (supplementary S9)."""
    assert sup.check_hedge_drift(sup.load_run(_run(run)))["status"] == "ok"


@pytest.mark.parametrize("run", BRIEFS)
def test_no_temporal_deixis_or_july_calques(run):
    """tier3 R4 and R7 no longer occur."""
    el, en = _render(run, "el"), _render(run, "en")
    assert not re.search(r"(?<!\w)σήμερα(?!\w)", el) and not re.search(r"\btoday\b", en, re.IGNORECASE)
    for calque in ("επικεφαλής λογαριασμού", "διαμερίζεται", "Client Brief [EL]"):
        assert calque not in el


@pytest.mark.parametrize("run", BRIEFS)
def test_pipeline_metadata_sits_in_the_internal_block(run):
    """tier3 R2 mostly fixed: tier and readiness appear only after the 'not for the client' heading."""
    for lang, heading, marker in (("el", "Εσωτερικά στοιχεία", "Επίπεδο ευαισθησίας"),
                                  ("en", "Internal", "Sensitivity tier")):
        text = _render(run, lang)
        assert heading in text and text.index(marker) > text.index(heading), lang


@pytest.mark.parametrize("run", ["nl-r1", "nl-r3"])
def test_metro_retraction_survives_as_an_internal_conflict(run):
    """tier3 E2 no longer occurs."""
    extract = json.loads((_run(run) / "extracts" / "transcript_kickoff.json").read_text(encoding="utf-8"))
    assert any("μετρό" in json.dumps(c, ensure_ascii=False) for c in extract.get("internal_conflicts") or [])
