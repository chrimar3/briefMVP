"""Northlight regression cases: output defects in the graded tier3 evidence the frozen harness
scores as a pass.

runs/tier3 is the graded run (17/17, runs/tier3/harness_report.json). The round-0 output panel
(tools/project_review/rounds/r0/out/o1_*, o2_*, o3_*) found content defects in its brief, renders
and creative drafts that eval/harness.py does not measure; each was re-verified against the
committed artifacts and recorded in runs/tier3/KNOWN_DEFECTS.md (brief, renders) and
runs/tier3/creative/KNOWN_DEFECTS.md (creative drafts). This file encodes the machine-checkable
ones, mirroring tests/test_regression_voreas.py.

Marking rule. A case the stored artifact fails is xfail(strict=True, raises=AssertionError) with
the KNOWN_DEFECTS id it encodes, so the suite stays green while the defect is on record. When the
artifact is regenerated without the defect the XPASS fails the suite — the signal to drop the mark
and update KNOWN_DEFECTS.md. Cases the artifact already satisfies pass outright. Preconditions use
pytest.fail so a changed artifact reports as a real failure, never as the expected one.

Reads (read-only): runs/tier3/{brief.json, brief_el.md, brief_en.md, extracts/*.json,
fidelity/*.annotated.md, creative/creative_brief_*.md}; fixtures/northlight_01 sources. Never
reads fixtures/northlight_01/answer_key.json. No model is called; nothing is regenerated.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "eval"))
import supplementary as sup  # noqa: E402

RUN = REPO / "runs" / "tier3"
FIXTURE = REPO / "fixtures" / "northlight_01"
BRIEF_DEFECTS = "runs/tier3/KNOWN_DEFECTS.md"
CREATIVE_DEFECTS = "runs/tier3/creative/KNOWN_DEFECTS.md"


def _need(path: Path) -> Path:
    if not path.exists():
        pytest.skip(f"{path.relative_to(REPO)} is not present")
    return path


def _brief() -> dict:
    return json.loads(_need(RUN / "brief.json").read_text(encoding="utf-8"))


def _render(lang: str) -> str:
    return _need(RUN / f"brief_{lang}.md").read_text(encoding="utf-8")


def _extract(source_id: str) -> dict:
    return json.loads(_need(RUN / "extracts" / f"{source_id}.json").read_text(encoding="utf-8"))


def _draft(model: str) -> str:
    return _need(RUN / "creative" / f"creative_brief_{model}.md").read_text(encoding="utf-8")


def _run() -> dict:
    _need(RUN / "brief.json")
    return sup.load_run(RUN)


def _lines_with(text: str, needle: str) -> list:
    return [n for n, line in enumerate(text.splitlines(), 1) if needle in line]


def _xfail(value, reason: str):
    values = value if isinstance(value, tuple) else (value,)
    return pytest.param(*values, id="-".join(str(v) for v in values)[:40],
                        marks=pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason))


def _xfail_case(reason: str):
    return pytest.mark.xfail(strict=True, raises=AssertionError, reason=reason)


# --------------------------------------------------------------------------------------
# Brief (runs/tier3/brief.json) and extracts
# --------------------------------------------------------------------------------------


@_xfail_case(f"{BRIEF_DEFECTS} B1: open questions 1, 2 and 8 still ask the client to settle the "
             f"audience, budget and launch date the account lead resolved at sign-off")
def test_signed_off_brief_asks_nothing_a_resolution_answered():
    brief = _brief()
    if (brief.get("signoff") or {}).get("status") != "signed_off":
        pytest.fail("precondition: runs/tier3/brief.json is signed off")
    result = sup.check_stale_questions(_run())
    assert not result["items"], "\n".join(result["items"])


@_xfail_case(f"{BRIEF_DEFECTS} B2: audiences and budget carry no entry after their conflicts were "
             f"resolved; the resolved values live only inside conflicts[]")
def test_resolved_conflict_values_reach_their_fields():
    brief = _brief()
    resolved = [c["field"] for c in brief["conflicts"] if c.get("status") == "resolved_by_human"]
    if not resolved:
        pytest.fail("precondition: the brief carries human-resolved conflicts")
    empty = [f for f in resolved if not brief.get(f)]
    assert not empty, f"resolved fields with no entry: {empty}"


@_xfail_case(f"{BRIEF_DEFECTS} B3: objectives[2] and key_messages[3] say 'brand awareness' / 'key "
             f"visual'; the ASR tokens survive only inside evidence anchors (harness T3.3 greps anchors)")
def test_garbled_tokens_stay_visible_in_brief_content():
    result = sup.check_garble_visibility(_run())
    if not result.get("tokens"):
        pytest.fail("precondition: the fidelity annotations flag garbled tokens")
    content_items = [i for i in result["items"] if "content drops" in i]
    assert not content_items, "\n".join(content_items)


@_xfail_case(f"{BRIEF_DEFECTS} B3: neither render shows «μπραντ αγουέρνες» or «κι βίζουαλ» or any "
             f"ASR flag")
def test_garbled_tokens_stay_visible_in_renders():
    result = sup.check_garble_visibility(_run())
    render_items = [i for i in result["items"] if i.startswith("brief_")]
    assert not render_items, "\n".join(render_items)


@_xfail_case(f"{BRIEF_DEFECTS} B4: transcript extract objectives[0] and key_messages[2] carry the "
             f"garbled tokens at confidence high; SOURCES.md rule G says low")
def test_garble_carrying_extract_items_are_low_confidence():
    extract = _extract("transcript_kickoff")
    tokens = ("μπραντ αγουέρνες", "κι βίζουαλ")
    carriers = [(f, i, it) for f in ("objectives", "audiences", "key_messages", "deliverables", "timeline",
                                     "budget", "mandatories")
                for i, it in enumerate(extract.get(f) or [])
                if any(t in (it.get("value") or "") + (it.get("anchor") or "") for t in tokens)]
    if not carriers:
        pytest.fail("precondition: some extract item carries a garbled token")
    wrong = [f"{f}[{i}] confidence={it.get('confidence')}" for f, i, it in carriers if it.get("confidence") != "low"]
    assert not wrong, wrong


@_xfail_case(f"{BRIEF_DEFECTS} B5: key_messages[3] adds 'not a generic beach-party feel' from "
             f"background_brand_guidelines while citing only transcript_kickoff [00:06:02]")
def test_entry_content_stays_within_its_cited_sources():
    result = sup.check_citation_content(_run())
    borrowed = [i for i in result["items"] if (" compound " in i or " quote " in i) and "found only in" in i]
    assert not borrowed, "\n".join(borrowed)


@_xfail_case(f"{BRIEF_DEFECTS} B6: deliverables[0] (brief approval) and deliverables[1] (a revised "
             f"plan Northlight will send) are agency process steps, not campaign deliverables")
def test_agency_process_steps_are_not_deliverables():
    process = re.compile(r"\bapproval of the brief\b|\bwill send\b", re.IGNORECASE)
    hits = [f"deliverables[{i}]: {e['content'][:70]}" for i, e in enumerate(_brief()["deliverables"])
            if process.search(e.get("content") or "")]
    assert not hits, hits


@_xfail_case(f"{BRIEF_DEFECTS} B7: conflicts[1] and its resolution say 'in the eighties' (a range, "
             f"80–89); SYNTHESIS.md rule 2 renders «κάπου στα ογδόντα» as 'around eighty (units unstated)'")
def test_spoken_budget_keeps_its_canonical_hedge():
    anchor_line = next((line for line in (FIXTURE / "transcript_kickoff.md").read_text(encoding="utf-8").splitlines()
                        if line.startswith("[00:14:32]")), "")
    if "κάπου στα ογδόντα" not in anchor_line:
        pytest.fail("precondition: the source line holds the spoken figure")
    run = _run()
    run["creative"] = {}
    result = sup.check_hedge_drift(run)
    assert not result["items"], "\n".join(result["items"])


@_xfail_case(f"{BRIEF_DEFECTS} R4: suggested question 2 says 'today it was said' / 'σήμερα "
             f"ειπώθηκε' in a brief dated two weeks after the kickoff")
def test_client_questions_carry_no_call_day_deixis():
    deixis = re.compile(r"\btoday\b|\bσήμερα\b|\bχθες\b|\byesterday\b", re.IGNORECASE)
    hits = [f"open_questions[{i}]" for i, q in enumerate(_brief()["open_questions"])
            if deixis.search(q.get("suggested_question_for_client") or "")]
    assert not hits, hits


# --------------------------------------------------------------------------------------
# Renders (runs/tier3/brief_el.md, brief_en.md)
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("lang, heading", [
    _xfail(("en", "Unresolved Conflicts"), f"{BRIEF_DEFECTS} R1: EN:92 heads three resolved conflicts"),
    _xfail(("el", "Ανεπίλυτες Συγκρούσεις"), f"{BRIEF_DEFECTS} R1: EL:92 heads three resolved conflicts"),
])
def test_conflict_heading_matches_conflict_status(lang, heading):
    if any(c.get("status") == "open" for c in _brief()["conflicts"]):
        pytest.fail("precondition: every conflict in runs/tier3 is resolved")
    assert heading not in _render(lang), f"brief_{lang}.md:{_lines_with(_render(lang), heading)}"


@pytest.mark.parametrize("lang", [
    _xfail("en", f"{BRIEF_DEFECTS} R2: EN header shows sensitivity tier, readiness verdict, coverage "
                 f"count and pipeline id in a client-facing brief"),
    _xfail("el", f"{BRIEF_DEFECTS} R2: EL header shows the same internal metadata"),
])
def test_client_render_carries_no_internal_pipeline_metadata(lang):
    markers = {"en": ("Sensitivity tier", "Verdict:", "Pipeline:"),
               "el": ("Επίπεδο ευαισθησίας", "Αξιολόγηση:", "Pipeline:")}[lang]
    text = _render(lang)
    found = [m for m in markers if m in text]
    assert not found, found


#: R3 — Greek grammar defects in brief_el.md, verified line by line (KNOWN_DEFECTS.md R3 table).
GREEK_DEFECTS = [
    ("της προσώπου", 54, "article gender: του προσώπου"),
    ("Ποιό", 66, "monosyllable takes no accent: Ποιο"),
    ("τη κατηγορία", 68, "final ν before κ: την κατηγορία"),
    ("και που ακριβώς", 78, "interrogative: πού"),
    ("τη τελική", 86, "final ν before τ: την τελική"),
    ("το κοινό-στόχος ως", 95, "accusative: το κοινό-στόχο"),
    ("σύμφωνα με τον CFO", 103, "Anna is the CFO: την CFO"),
    ("Ο προϋπολογισμός media διαχειρίζεται", 103, "deponent verb makes the budget the agent"),
    ("αντικρούσεις", 115, "rebuttals; conflicts = συγκρούσεις/αντιφάσεις"),
]


@pytest.mark.parametrize("bad", [
    _xfail(bad, f"{BRIEF_DEFECTS} R3: brief_el.md:{line} {why}") for bad, line, why in GREEK_DEFECTS
])
def test_greek_render_is_free_of_the_documented_grammar_errors(bad):
    if bad == "σύμφωνα με τον CFO":
        participants = (FIXTURE / "transcript_kickoff.md").read_text(encoding="utf-8").splitlines()[2]
        if "ANNA (Meltemi, CFO)" not in participants:
            pytest.fail("precondition: the transcript names Anna as the CFO")
    text = _render("el")
    assert bad not in text, f"brief_el.md:{_lines_with(text, bad)} {bad!r}"


FINAL_NU = re.compile(r"(?<!\w)τη (?=[αεηιουωάέήίόύώκπτξψ]|μπ|ντ|γκ|τσ|τζ)")
ACCENTED_MONOSYLLABLE = re.compile(r"(?<!\w)(?:[Ππ]οιό|[Ππ]ιό)(?!\w)")


@_xfail_case(f"{BRIEF_DEFECTS} R3: generic lint — 'τη' before a vowel or κ/π/τ (lines 68, 86) and an "
             f"accented monosyllable (line 66)")
def test_greek_render_passes_a_final_nu_and_accent_lint():
    hits = []
    for n, line in enumerate(_render("el").splitlines(), 1):
        hits += [f"{n}: {m.group(0)!r}" for m in FINAL_NU.finditer(line)]
        hits += [f"{n}: {m.group(0)!r}" for m in ACCENTED_MONOSYLLABLE.finditer(line)]
    assert not hits, hits


def test_english_render_passes_the_same_lint_trivially():
    """Control: the lint is Greek-specific and has no hits on the English render."""
    text = _render("en")
    assert not FINAL_NU.search(text) and not ACCENTED_MONOSYLLABLE.search(text)


@_xfail_case(f"{BRIEF_DEFECTS} E1: transcript extract key_messages[0] value says 'natural "
             f"ingredients' for the source's «φυσικά υλικά» (SOURCES.md rule 5: never translate)")
def test_extract_values_keep_the_source_language():
    item = _extract("transcript_kickoff")["key_messages"][0]
    if "φυσικά υλικά" not in (item.get("anchor") or ""):
        pytest.fail("precondition: key_messages[0] is anchored on «φυσικά υλικά»")
    assert "natural ingredients" not in (item.get("value") or "")


@_xfail_case(f"{BRIEF_DEFECTS} E2: the metro OOH idea and its retraction ([00:08:15]/[00:08:34]) were "
             f"removed by a repair; only an extraction note records it")
def test_within_source_retraction_is_recorded_in_the_extract():
    extract = _extract("transcript_kickoff")
    fields = ("objectives", "audiences", "key_messages", "deliverables", "timeline", "budget", "mandatories")
    locations = [it.get("location") or "" for f in fields for it in extract.get(f) or []]
    locations += [json.dumps(c, ensure_ascii=False) for c in extract.get("internal_conflicts") or []]
    assert any("00:08:15" in loc or "00:08:34" in loc for loc in locations)


# --------------------------------------------------------------------------------------
# Creative drafts (runs/tier3/creative/creative_brief_{sonnet,opus}.md)
# --------------------------------------------------------------------------------------


def _creative_items(check, model: str) -> list:
    run = _run()
    run["creative"] = {k: v for k, v in run["creative"].items() if k == f"creative_brief_{model}.md"}
    if not run["creative"]:
        pytest.fail(f"precondition: creative_brief_{model}.md carries a draft banner")
    return check(run)["items"]


@pytest.mark.parametrize("model", [
    _xfail("sonnet", f"{CREATIVE_DEFECTS} C1: sonnet:64 and :69 print '(€80–85k)' for a figure the brief "
                     f"records with no unit or currency"),
    _xfail("opus", f"{CREATIVE_DEFECTS} C7: opus:96 reformats the RFP's €90,000 as '€90k'"),
])
def test_creative_amounts_trace_to_the_brief(model):
    items = _creative_items(sup.check_creative_currency, model)
    assert not items, "\n".join(items)


@pytest.mark.parametrize("model", [
    _xfail("sonnet", f"{CREATIVE_DEFECTS} C5: sonnet:52 writes '9–60s' (U+2013) where the table row has "
                     f"'9-60s'"),
    pytest.param("opus", id="opus"),
])
def test_creative_spec_tokens_are_byte_identical_to_the_table(model):
    items = _creative_items(sup.check_creative_spec_tokens, model)
    assert not items, "\n".join(items)


@pytest.mark.parametrize("model, claim", [
    _xfail(("sonnet", "new to Greece"), f"{CREATIVE_DEFECTS} C2: sonnet:9 — the source says new to the "
                                        f"company («καινούργια κατηγορία για εμάς»)"),
    _xfail(("opus", "Greek-made"), f"{CREATIVE_DEFECTS} C3: opus:11 — a place-of-manufacture claim no "
                                   f"source makes («ελληνικό brand»)"),
])
def test_creative_market_and_origin_claims_trace_to_the_brief(model, claim):
    if claim.lower() in sup.brief_text(_brief()).lower():
        pytest.fail(f"precondition: {claim!r} is absent from the brief")
    text = _draft(model)
    assert claim not in text, f"creative_brief_{model}.md:{_lines_with(text, claim)}"


@pytest.mark.parametrize("model", [
    _xfail("opus", f"{CREATIVE_DEFECTS} C4: opus:73 calls the hedged TikTok dance 'retracted'; the "
                   f"retraction in the source is the metro OOH idea"),
    pytest.param("sonnet", id="sonnet"),
])
def test_speculative_idea_is_not_called_retracted(model):
    dance = [e for e in _brief()["deliverables"] if "TikTok dance" in (e.get("content") or "")]
    if not dance or dance[0].get("qualifier") != "conditional":
        pytest.fail("precondition: the brief carries the TikTok dance as conditional")
    lines = [line for line in _draft(model).splitlines() if "TikTok dance" in line and "retract" in line.lower()]
    assert not lines, lines


@pytest.mark.parametrize("model", [
    _xfail("opus", f"{CREATIVE_DEFECTS} C6: opus:5 says 'Reviewed by a creative lead' — written by the "
                   f"model at generation time, before any human review"),
    pytest.param("sonnet", id="sonnet"),
])
def test_draft_claims_no_human_review(model):
    claim = re.compile(r"\breviewed by (?:a|the) creative lead\b", re.IGNORECASE)
    text = _draft(model)
    assert not claim.search(text), f"creative_brief_{model}.md:{_lines_with(text, 'Reviewed by')}"
