"""Tests for eval/supplementary.py — the report-only scorer for the frozen harness's blind spots.

Synthetic runs exercise each check both ways; the committed evidence (runs/tier3, voreas-prep-0x)
pins the findings recorded in docs/EVAL_RECORD.md §5. Nothing here reads an answer key.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import supplementary as sup  # noqa: E402

SOURCE = """---
source_id: kickoff
source_type: transcript
source_date: 2026-01-10
---
[00:01:00] ANA: Θέλουμε το μπράντ λιφτ να ανέβει.
[00:02:00] ANA: Maybe a pop-up thing, don't quote me on it.
[00:03:00] ANA: Το budget είναι κάπου στα σαράντα.
"""
GUIDE = """---
source_id: guide
source_type: background
source_date: 2026-01-01
---
- Avoid "neon rave" clichés.
"""


def _entry(content, source_id, location, anchor, qualifier="stated", confidence="high"):
    return {"content": content, "qualifier": qualifier, "confidence": confidence,
            "evidence": [{"source_id": source_id, "location": location, "anchor": anchor}]}


def _brief(**overrides):
    brief = {"meta": {"client_id": "demo"}, "objectives": [], "audiences": [], "key_messages": [],
             "deliverables": [], "timeline": [], "budget": [], "mandatories": [], "open_questions": [],
             "conflicts": [], "signoff": {"status": "draft"}}
    brief.update(overrides)
    return brief


def _make(tmp_path, brief, extracts=None, renders=None, creative=None, annotated=None, glossary=None):
    project = tmp_path / "project"
    project.mkdir(parents=True)
    (project / "data_declaration.json").write_text('{"data_class": "synthetic"}', encoding="utf-8")
    (project / "kickoff.md").write_text(SOURCE, encoding="utf-8")
    (project / "guide.md").write_text(GUIDE, encoding="utf-8")
    (project / "answer_key.json").write_text('{"never": "read"}', encoding="utf-8")
    if glossary is not None:
        (project / "client_demo.json").write_text(json.dumps(glossary), encoding="utf-8")
    run = tmp_path / "run"
    (run / "extracts").mkdir(parents=True)
    (run / "run_manifest.json").write_text(json.dumps({"project_dir": str(project)}), encoding="utf-8")
    (run / "brief.json").write_text(json.dumps(brief, ensure_ascii=False), encoding="utf-8")
    for sid, ex in (extracts or {}).items():
        (run / "extracts" / f"{sid}.json").write_text(json.dumps(ex, ensure_ascii=False), encoding="utf-8")
    for lang, text in (renders or {}).items():
        (run / f"brief_{lang}.md").write_text(text, encoding="utf-8")
    if creative:
        (run / "creative").mkdir()
        for name, text in creative.items():
            (run / "creative" / name).write_text(text, encoding="utf-8")
    if annotated:
        (run / "fidelity").mkdir()
        for sid, text in annotated.items():
            (run / "fidelity" / f"{sid}.annotated.md").write_text(text, encoding="utf-8")
    return run


def _result(run, check):
    return next(r for r in sup.score(run)["results"] if r["check"].startswith(check))


def test_never_reads_an_answer_key(tmp_path, monkeypatch):
    run = _make(tmp_path, _brief())
    real = Path.read_text

    def guarded(self, *a, **k):
        assert self.name != "answer_key.json", "supplementary.py opened an answer key"
        return real(self, *a, **k)

    monkeypatch.setattr(Path, "read_text", guarded)
    sup.score(run)


def test_s1_flags_a_dropped_speculative_item_and_vacuity(tmp_path):
    extract = {"deliverables": [{"value": "pop-up", "qualifier": "conditional", "location": "[00:02:00]",
                                 "anchor": "Maybe a pop-up thing"}]}
    run = _make(tmp_path, _brief(), extracts={"kickoff": extract})
    assert _result(run, "S1")["status"] == "flag"
    kept = _brief(deliverables=[_entry("A pop-up, speculative", "kickoff", "[00:02:00]",
                                       "Maybe a pop-up thing", qualifier="conditional")])
    run2 = _make(tmp_path / "b", kept, extracts={"kickoff": extract})
    assert _result(run2, "S1")["status"] == "ok"
    run3 = _make(tmp_path / "c", _brief(), extracts={"kickoff": {"objectives": []}})
    assert _result(run3, "S1")["status"] == "vacuous"


def test_s1_flags_a_de_hedged_speculative_item(tmp_path):
    extract = {"deliverables": [{"value": "pop-up", "qualifier": "conditional", "location": "[00:02:00]",
                                 "anchor": "Maybe a pop-up thing"}]}
    brief = _brief(deliverables=[_entry("A pop-up", "kickoff", "[00:02:00]", "Maybe a pop-up thing")])
    result = _result(_make(tmp_path, brief, extracts={"kickoff": extract}), "S1")
    assert result["status"] == "flag" and "without the conditional qualifier" in result["items"][0]


def test_s2_flags_questions_left_open_after_a_resolution(tmp_path):
    brief = _brief(conflicts=[{"field": "budget", "status": "resolved_by_human", "positions": []}],
                   open_questions=[{"field": "budget", "gap": "Budget figures unreconciled"},
                                   {"field": "timeline", "gap": "No milestones"}])
    result = _result(_make(tmp_path, brief), "S2")
    assert result["status"] == "flag" and len(result["items"]) == 1


def test_s3_flags_a_garble_resolved_silently(tmp_path):
    annotated = SOURCE.replace("μπράντ λιφτ", 'μπράντ λιφτ [FIDELITY: glossary-match "brand lift", confidence high]')
    extract = {"extraction_notes": ["[00:01:00] Token 'μπράντ λιφτ' flagged, glossary match 'brand lift'."]}
    brief = _brief(objectives=[_entry("Grow brand lift", "kickoff", "[00:01:00]", "Θέλουμε το μπράντ λιφτ")])
    run = _make(tmp_path, brief, extracts={"kickoff": extract}, annotated={"kickoff": annotated},
                renders={"en": "Grow brand lift", "el": "brand lift"})
    result = _result(run, "S3")
    assert result["status"] == "flag"
    assert result["tokens"]["kickoff"][0] == {"token": "μπράντ λιφτ", "proposal": "brand lift",
                                              "basis": "quoted in an extraction note"}
    visible = _brief(objectives=[_entry("Grow brand lift (ASR: «μπράντ λιφτ»)", "kickoff", "[00:01:00]",
                                        "Θέλουμε το μπράντ λιφτ")])
    run2 = _make(tmp_path / "b", visible, extracts={"kickoff": extract}, annotated={"kickoff": annotated},
                 renders={"en": "brand lift (ASR: «μπράντ λιφτ»)", "el": "«μπράντ λιφτ»"})
    assert _result(run2, "S3")["status"] == "ok"


def test_s4_flags_a_clause_borrowed_from_another_source(tmp_path):
    brief = _brief(key_messages=[_entry("Premium, not a neon-rave feel", "kickoff", "[00:01:00]",
                                        "Θέλουμε το μπράντ λιφτ")])
    result = _result(_make(tmp_path, brief), "S4")
    assert result["status"] == "flag" and "found only in guide" in result["items"][0]


def test_s4_ignores_an_english_compound_that_translates_the_source(tmp_path):
    brief = _brief(objectives=[_entry("Brand-lift growth", "kickoff", "[00:01:00]", "Θέλουμε το μπράντ λιφτ")])
    assert _result(_make(tmp_path, brief), "S4")["status"] == "ok"


def test_s5_flags_near_duplicate_questions_and_conflict_re_asks(tmp_path):
    q = {"field": "budget", "gap": "The production budget figure has no confirmed currency or unit",
         "suggested_question_for_client": "Which currency and unit apply to the production budget figure?"}
    brief = _brief(open_questions=[q, dict(q)])
    assert _result(_make(tmp_path, brief), "S5")["status"] == "flag"
    conflict = {"field": "budget", "status": "open", "positions": [
        {"statement": "forty", "evidence": {"source_id": "kickoff", "location": "[00:03:00]",
                                             "anchor": "κάπου στα σαράντα"}}]}
    reask = _brief(conflicts=[conflict], open_questions=[
        {"field": "budget", "gap": "Which budget?", "linked_evidence": [
            {"source_id": "kickoff", "location": "[00:03:00]", "anchor": "κάπου στα σαράντα"}]}])
    result = _result(_make(tmp_path / "b", reask), "S5")
    assert result["status"] == "flag" and "re-asks open conflicts[0]" in result["items"][0]


def test_s6_flags_currency_the_brief_never_stated(tmp_path):
    brief = _brief(open_questions=[{"field": "budget", "gap": "RFP states €50,000 including media"}])
    creative = {"creative_brief_x.md": "> CREATIVE DRAFT — not approved\nBudget: around forty (€40–45k); RFP €50,000.\n"}
    result = _result(_make(tmp_path, brief, creative=creative), "S6")
    assert result["status"] == "flag"
    assert [i.split(": ", 1)[1] for i in result["items"]] == ["'€40–45k' — no such amount in the brief"]


def test_s7_checks_duration_and_file_type_byte_for_byte(tmp_path):
    table = {"specs": [{"id": "vid", "channel": "C", "format": "F", "aspect_ratio": "9:16",
                        "resolution": "1080x1920", "duration": "9-60s", "file_type": "MP4"}]}
    good = "> CREATIVE DRAFT\n| video | 9:16, 1080x1920, 9-60s, MP4 `[spec: vid]` |\n"
    bad = "> CREATIVE DRAFT\n| video | 9:16, 1080x1920, 9–60s, MOV `[spec: vid]` |\n"
    run = sup.load_run(_make(tmp_path, _brief(), creative={"creative_brief_a.md": good}))
    assert sup.check_creative_spec_tokens(run, table)["status"] == "ok"
    run2 = sup.load_run(_make(tmp_path / "b", _brief(), creative={"creative_brief_a.md": bad}))
    result = sup.check_creative_spec_tokens(run2, table)
    assert result["status"] == "flag" and len(result["items"]) == 2
    assert "'9–60s'" in result["items"][0] and "'MOV'" in result["items"][1]


def test_s8_uses_the_project_glossary_and_reports_vacuity(tmp_path):
    glossary = {"client_id": "demo", "terms": [{"term": "Nova Drink", "rule": "keep_latin"}]}
    brief = _brief(objectives=[_entry("Launch Nova Drink", "kickoff", "[00:01:00]", "Θέλουμε")])
    run = _make(tmp_path, brief, renders={"en": "Nova Drink", "el": "Νόβα Ντρινκ"}, glossary=glossary)
    result = _result(run, "S8")
    assert result["status"] == "flag" and "brief_el.md" in result["items"][0]
    run2 = _make(tmp_path / "b", _brief(), renders={"en": "", "el": ""}, glossary=glossary)
    assert _result(run2, "S8")["status"] == "vacuous"


def test_s9_flags_decade_range_drift(tmp_path):
    brief = _brief(conflicts=[{"field": "budget", "status": "open", "resolution": None, "positions": [
        {"statement": "somewhere in the forties", "evidence": {}}]}])
    assert _result(_make(tmp_path, brief), "S9")["status"] == "flag"


# --------------------------------------------------------------------------------------
# The committed evidence — the findings docs/EVAL_RECORD.md §5 records
# --------------------------------------------------------------------------------------


def test_tier3_findings(repo_root):
    report = {r["check"].split()[0]: r for r in sup.score(repo_root / "runs" / "tier3")["results"]}
    assert report["S2"]["status"] == "flag" and len(report["S2"]["items"]) == 3
    assert report["S3"]["status"] == "flag"
    assert {g["token"] for g in report["S3"]["tokens"]["transcript_kickoff"]} == {"μπραντ αγουέρνες", "κι βίζουαλ"}
    assert any("beach-party" in i for i in report["S4"]["items"])
    assert any("€80–85k" in i for i in report["S6"]["items"])
    assert [i for i in report["S7"]["items"]] and "9–60s" in report["S7"]["items"][0]
    assert report["S8"]["status"] == "ok"
    assert report["S9"]["status"] == "flag"


def test_voreas_findings(repo_root):
    for run, dupes in (("voreas-prep-02", 6), ("voreas-prep-03", 4)):
        report = {r["check"].split()[0]: r for r in sup.score(repo_root / "runs" / run)["results"]}
        assert len([i for i in report["S5"]["items"] if "re-asks open conflicts" in i]) == dupes
        assert any("μπραντ αγουέρνες" in i and "no brief entry or conflict" in i for i in report["S3"]["items"])
        assert report["S8"]["status"] == "ok" and "client_voreas.json" in report["S8"]["detail"]
