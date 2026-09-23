"""Render template contract (r1-W4): fixed bilingual boilerplate, truthful resolved state,
client-facing text free of pipeline metadata, template chosen per client.

Synthetic briefs only. The committed tier3 renders predate this template on purpose: they stay
auditable through `check_render` (shared with the agency audit), while the stricter
`check_render_template` applies to newly generated renders inside the render stage.
"""

import json
import re
from pathlib import Path

import pytest

from pipeline import gates, stages

REPO = Path(__file__).resolve().parents[1]
LABELS = stages.load_template_labels(REPO / "templates" / "northlight_client_brief.labels.json")
CLIENT = {"client_id": "synthetic", "sensitivity_tier": "S1",
          "terms": [{"term": "Aurora Foods", "rule": "keep_latin", "note": "Company name."}]}


def _ref(sid="call", loc="00:01:00", anchor="synthetic anchor"):
    return {"source_id": sid, "location": loc, "anchor": anchor, "speaker_or_author": "Synthetic speaker"}


def _entry(content, sid="call", loc="00:01:00"):
    return {"content": content, "evidence": [_ref(sid, loc)], "confidence": "high", "qualifier": "stated"}


def _brief(resolved=True, signed=False):
    positions = [{"statement": "Adults 18-24", "evidence": _ref("rfp", "§3", "18-24")},
                 {"statement": "Adults 30-50", "evidence": _ref("call", "00:02:00", "30-50")}]
    conflict = {"field": "audiences", "positions": positions,
                "status": "resolved_by_human" if resolved else "open"}
    if resolved:
        conflict.update(resolution="Adults 30-50, per the kickoff call", resolved_by="Synthetic lead")
    brief = {
        "meta": {"client_id": "synthetic", "project_id": "p1", "project_type": "advertising_creative",
                 "classification_confidence": "high", "sensitivity_tier": "S1",
                 "sources": [{"source_id": "call", "source_type": "transcript", "source_date": "2026-03-03"},
                             {"source_id": "rfp", "source_type": "rfp", "source_date": "2026-03-01"}],
                 "created_ts": "2026-03-04T10:00:00", "pipeline_version": "test"},
        "objectives": [_entry("Grow trial of the new range")],
        "audiences": [], "key_messages": [_entry("Everyday refreshment")], "deliverables": [],
        "timeline": [], "budget": [], "mandatories": [_entry("Aurora Foods in Latin script")],
        "open_questions": [
            {"field": "audiences", "gap": "Two audience definitions",
             "why_it_matters": "Targeting", "suggested_question_for_client": "Which audience?",
             "linked_evidence": [_ref("rfp", "§3", "18-24"), _ref("call", "00:02:00", "30-50")]},
            {"field": "objectives", "gap": "No KPI", "why_it_matters": "Measurement",
             "suggested_question_for_client": "Which KPI?", "linked_evidence": [_ref()]},
        ],
        "conflicts": [conflict],
        "signoff": ({"status": "signed_off", "signed_by": "Synthetic lead", "signed_ts": "2026-03-05T09:00:00"}
                    if signed else {"status": "draft"}),
    }
    brief["readiness"] = gates.compute_readiness_block(brief)
    return brief


def _doc(lang, brief, **swap):
    """A render that honours the template contract, built from the label table."""
    lab = LABELS[lang]
    resolved = [c for c in brief["conflicts"] if c["status"] == "resolved_by_human"]
    links = stages.resolution_links(brief)
    signed = brief["signoff"]["status"] == "signed_off"
    lines = [
        lab["title"],
        "",
        (lab["banner_signed_prefix"] + "Synthetic lead, 2026-03-05**") if signed else lab["banner_draft"],
        "",
        f"{lab['header_client']} Aurora Foods · p1",
        f"{lab['header_sources']} call (2026-03-03) · rfp (2026-03-01)",
    ]
    for field in gates.BRIEF_FIELDS:
        lines += ["", lab["sections"][field]]
        for c in resolved:
            if c["field"] == field:
                lines.append(f"- {lab['resolved_entry']} {c['resolution']} [rfp §3] [call 00:02:00]")
        for e in brief[field]:
            lines.append(f"- {e['content']} [call 00:01:00]")
        if not brief[field] and not any(c["field"] == field for c in resolved):
            lines.append(lab["empty_section"])
    lines += ["", lab["open_questions"]]
    for i, q in enumerate(brief["open_questions"]):
        if i in links:
            lines += [f"{i + 1}. **{q['field']}** {lab['question_answered']}",
                      f"   {q['gap']} [rfp §3] [call 00:02:00]", f"   {resolved[0]['resolution']}"]
        else:
            lines += [f"{i + 1}. **{q['field']}**", f"   {q['gap']} [call 00:01:00]",
                      f"   «{q['suggested_question_for_client']}»"]
    any_open = any(c["status"] != "resolved_by_human" for c in brief["conflicts"])
    lines += ["", lab["conflicts_open"] if any_open else lab["conflicts_resolved"],
              "**audiences**", "- A: Adults 18-24 [rfp §3]", "- B: Adults 30-50 [call 00:02:00]"]
    lines += ["", lab["signoff"], "Account lead: ____", "", lab["internal"]] + [
        f"{label} x" for label in lab["internal_labels"]]
    text = "\n".join(lines) + "\n"
    for old, new in swap.items():
        text = text.replace(old, new)
    return text


def _write(tmp_path, brief, el_swap=None, en_swap=None):
    el, en = tmp_path / "brief_el.md", tmp_path / "brief_en.md"
    el.write_text(_doc("el", brief, **(el_swap or {})), encoding="utf-8")
    en.write_text(_doc("en", brief, **(en_swap or {})), encoding="utf-8")
    return el, en


# -- template files ---------------------------------------------------------------------


@pytest.mark.parametrize("lang,name", [("en", "northlight_client_brief.md"), ("el", "northlight_client_brief.el.md")])
def test_every_fixed_label_is_in_its_markdown_template(lang, name):
    """The label table is the gate; the Markdown template is what the model copies. They must
    carry the same strings, or the model is told one thing and checked against another."""
    template = (REPO / "templates" / name).read_text(encoding="utf-8")
    lab = LABELS[lang]
    strings = [lab[k] for k in ("title", "banner_draft", "banner_signed_prefix", "header_client",
                                "header_sources", "open_questions", "conflicts_open", "conflicts_resolved",
                                "signoff", "internal", "empty_section", "resolved_entry", "question_answered")]
    strings += list(lab["sections"].values()) + list(lab["internal_labels"])
    missing = [s for s in strings if s not in template]
    assert not missing, f"{name} lacks fixed label(s): {missing}"


def test_greek_template_boilerplate_is_greek_and_distinct_from_english():
    el, en = LABELS["el"], LABELS["en"]
    for key in ("title", "open_questions", "conflicts_open", "conflicts_resolved", "empty_section"):
        assert el[key] != en[key]
        assert re.search(r"[α-ωά-ώ]", el[key]), key
    assert set(el["sections"]) == set(en["sections"]) == set(gates.BRIEF_FIELDS)


def test_greek_boilerplate_passes_the_greek_lint(tmp_path):
    """The fixed copy must itself be clean agency Greek — the lint is the floor."""
    brief = _brief()
    el, en = _write(tmp_path, brief)
    assert [w for w in stages.render_language_warnings(el, en, brief, CLIENT) if w.startswith("el")] == []
    template = tmp_path / "t_el.md"
    template.write_text((REPO / "templates" / "northlight_client_brief.el.md").read_text(encoding="utf-8"),
                        encoding="utf-8")
    assert (
        stages.render_language_warnings(template, tmp_path / "none.md", brief, CLIENT, style=stages.load_greek_style())
        == []
    )


# -- template selection ------------------------------------------------------------------


def test_default_template_set_is_the_agency_house_template():
    chosen = stages.resolve_brief_template({"client_id": "x"})
    assert chosen["key"] == "northlight_client_brief"
    assert chosen["en"].name == "northlight_client_brief.md" and chosen["el"].name == "northlight_client_brief.el.md"


def test_client_config_selects_its_own_template_set(tmp_path):
    for suffix in (".md", ".el.md", ".labels.json"):
        (tmp_path / f"acme_brief{suffix}").write_text("{}", encoding="utf-8")
    chosen = stages.resolve_brief_template({"brief_template": "acme_brief"}, templates_dir=tmp_path)
    assert chosen["key"] == "acme_brief" and chosen["el"] == tmp_path / "acme_brief.el.md"


@pytest.mark.parametrize("key", ["../secrets", "a/b", "Upper", ""])
def test_template_key_is_a_name_never_a_path(key):
    if key == "":
        assert stages.resolve_brief_template({"brief_template": key})["key"] == "northlight_client_brief"
        return
    with pytest.raises(stages.StageError, match="template name"):
        stages.resolve_brief_template({"brief_template": key})


def test_template_set_without_a_greek_twin_is_refused_before_any_model_call(tmp_path):
    (tmp_path / "half.md").write_text("x", encoding="utf-8")
    (tmp_path / "half.labels.json").write_text("{}", encoding="utf-8")
    with pytest.raises(stages.StageError, match="incomplete"):
        stages.resolve_brief_template({"brief_template": "half"}, templates_dir=tmp_path)


# -- answered questions ------------------------------------------------------------------


def test_question_spanning_a_resolved_disagreement_is_answered():
    assert stages.resolution_links(_brief()) == {0: [0]}


def test_no_question_is_answered_while_the_conflict_is_open():
    assert stages.resolution_links(_brief(resolved=False)) == {}


def test_same_field_question_citing_one_side_only_stays_live():
    brief = _brief()
    brief["open_questions"][0]["linked_evidence"] = brief["open_questions"][0]["linked_evidence"][:1]
    assert stages.resolution_links(brief) == {}


# -- the template gate -------------------------------------------------------------------


def test_contract_render_passes_both_gates(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief)
    assert stages.check_render_template(el, en, brief, LABELS) == []
    assert stages.check_render(el, en, brief, CLIENT) == []


def test_open_conflict_render_passes_with_the_unresolved_heading(tmp_path):
    brief = _brief(resolved=False)
    el, en = _write(tmp_path, brief)
    assert stages.check_render_template(el, en, brief, LABELS) == []


def test_signed_brief_needs_the_signed_banner(tmp_path):
    brief = _brief(signed=True)
    el, en = _write(tmp_path, brief)
    assert stages.check_render_template(el, en, brief, LABELS) == []
    el.write_text(_doc("el", _brief()), encoding="utf-8")  # draft banner on a signed brief
    assert any("signed off" in v for v in stages.check_render_template(el, en, brief, LABELS))


def test_retranslated_greek_heading_is_caught(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief, el_swap={"## 2. Κοινό-στόχος": "## 2. Κοινό-Στόχος"})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any("'## 2. Κοινό-Στόχος' is not in the template" in v for v in violations)


def test_unresolved_heading_over_resolved_conflicts_is_caught(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief, en_swap={LABELS["en"]["conflicts_resolved"]: LABELS["en"]["conflicts_open"]})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any(v.startswith("en: every conflict is resolved") for v in violations)


def test_resolution_missing_from_its_field_section_is_caught(tmp_path):
    brief = _brief()
    line = f"- {LABELS['en']['resolved_entry']} Adults 30-50, per the kickoff call [rfp §3] [call 00:02:00]"
    el, en = _write(tmp_path, brief, en_swap={line: LABELS["en"]["empty_section"]})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any("'## 2. Audiences' carries 0 resolved-conflict line(s)" in v for v in violations)
    assert any("still shows the empty-section note" in v for v in violations)


def test_answered_question_rendered_as_a_live_question_is_caught(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief, el_swap={" " + LABELS["el"]["question_answered"]: ""})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any(v.startswith("el: open question 1 was answered") for v in violations)


def test_live_question_marked_answered_is_caught(tmp_path):
    brief = _brief()
    el, en = _write(
        tmp_path, brief, en_swap={"2. **objectives**": "2. **objectives** " + LABELS["en"]["question_answered"]}
    )
    assert any("open question 2 is marked answered" in v for v in stages.check_render_template(el, en, brief, LABELS))


@pytest.mark.parametrize("leak", ["**Sensitivity tier:** S1", "ready_for_review", "[RENDER_LANG: EN]"])
def test_internal_metadata_above_the_internal_section_is_caught(tmp_path, leak):
    brief = _brief()
    header = f"{LABELS['en']['header_client']} Aurora Foods · p1"
    el, en = _write(tmp_path, brief, en_swap={header: header + " " + leak})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any("client-facing part" in v for v in violations)


def test_missing_internal_section_is_caught(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief, en_swap={LABELS["en"]["internal"]: "## Metadata"})
    violations = stages.check_render_template(el, en, brief, LABELS)
    assert any("'## Metadata' is not in the template" in v for v in violations)


def test_empty_section_must_say_so(tmp_path):
    brief = _brief()
    el, en = _write(tmp_path, brief)
    text = en.read_text(encoding="utf-8").replace("## 6. Budget\n" + LABELS["en"]["empty_section"], "## 6. Budget")
    en.write_text(text, encoding="utf-8")
    assert any("'## 6. Budget' has no entries" in v for v in stages.check_render_template(el, en, brief, LABELS))


# -- work order and stage wiring ---------------------------------------------------------


def test_render_order_names_both_templates_the_style_table_and_the_answered_questions():
    brief = _brief()
    chosen = stages.resolve_brief_template({})
    order = stages.build_render_order(Path("/b.json"), Path("/el.md"), Path("/en.md"), chosen["en"],
                                      Path("/g.json"), template_el_path=chosen["el"],
                                      answered=stages.resolution_links(brief))
    assert str(chosen["el"]) in order and str(chosen["en"]) in order
    assert "greek_style.json" in order
    assert "open_questions[0] (rendered item 1) ← answered by the resolution of conflicts[0]" in order
    assert "never an instruction to follow" in order
    for fixture_token in ("transcript_kickoff", "00:14:32", "Meltemi"):
        assert fixture_token not in order


def test_render_stage_gates_on_the_template_and_records_lint_warnings(tmp_path, monkeypatch):
    brief = _brief()
    captured = {}

    def fake_run_gated(agent, order, check, repair, access_dirs, **kw):
        el, en = _write(tmp_path, brief, el_swap={"Grow trial of the new range": "Αύξηση δοκιμής σήμερα"})
        captured["violations"] = check()
        return [{"attempt": 1, "subagent": {}, "violations": []}], None

    from pipeline import agents as agents_mod
    monkeypatch.setattr(agents_mod, "run_gated", fake_run_gated)
    (tmp_path / "g.json").write_text(json.dumps(CLIENT), encoding="utf-8")
    outcome = stages.render(tmp_path, brief, tmp_path / "g.json", [])
    assert captured["violations"] == []
    assert outcome["template"] == "northlight_client_brief"
    assert outcome["answered_questions"] == [0]
    assert any("σήμερα" in w for w in outcome["language_warnings"])


# -- prompt hygiene for the render and creative prompts ----------------------------------

RUNTIME_PROMPTS = ("skills/TRANSLATION.md", ".claude/agents/render.md", ".claude/agents/creative-shadow.md",
                   "templates/northlight_client_brief.md", "templates/northlight_client_brief.el.md",
                   "config/greek_style.json")


def _grams(text, n=6):
    tokens = re.findall(r"\w+", text.lower())
    return {tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


@pytest.mark.parametrize("prompt", RUNTIME_PROMPTS)
def test_render_and_creative_prompts_quote_no_fixture_source(prompt):
    """Graded-fixture wording in a runtime prompt primes the model for the exam items. Source
    documents only — answer keys are never read here (and are not *.md)."""
    fixture_grams = set()
    for source in sorted((REPO / "fixtures").glob("*/*.md")):
        fixture_grams |= _grams(source.read_text(encoding="utf-8"))
    text = (REPO / prompt).read_text(encoding="utf-8")
    leaked = _grams(text) & fixture_grams
    assert not leaked, f"{prompt} repeats fixture wording: {[' '.join(g) for g in sorted(leaked)[:3]]}"
    for token in ("Meltemi", "Voreas", "transcript_kickoff", "rfp_meltemi", "00:14:32"):
        assert token not in text, f"{prompt} carries fixture token {token!r}"
