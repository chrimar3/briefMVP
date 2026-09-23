"""Design audit F8 — the work-order skeleton is a convention, enforced once, here.

Six builders produce the model-stage work orders. Their distinctive prose is spec — prompt
surface the tiers validated byte-for-byte — so it is deliberately NOT routed through a shared
assembler (which would either change those bytes or reduce to an f-string doing no work; see
runs/design_audit_report.md). The skeleton every order must carry is instead checked in one
place: the header naming the stage and PRD step, the INPUT block, the answer-key prohibition,
the OUTPUT contract with an exact path, and the one-line reply contract.
"""

import re
from pathlib import Path

import pytest
from conftest import bind_declaration

from pipeline import (agents, approval, creative, extraction, gates, replay, stage_classify, stage_fidelity, stage_render,
                      stage_synthesis, stages)

SRC = gates.SourceDoc("t", "transcript", "2026-01-01", Path("/x/t.md"), "text")
RFP = gates.SourceDoc("r", "rfp", "2026-01-01", Path("/x/r.md"), "text")
CONFIG = {"client_id": "c", "sensitivity_tier": "S1"}
CLASSIFICATION = {"project_type": "advertising_creative", "classification_confidence": "high",
                  "sensitivity_tier": "S1"}

ORDERS = {
    "extract": lambda: extraction.build_work_order(
        SRC, Path("/o/e.json"), "p", CONFIG, Path("/g.json")),
    "verify-extract": lambda: extraction.build_verify_order(
        SRC, Path("/o/e.json"), Path("/o/e.verify.json"), Path("/g.json")),
    "classify": lambda: stages.build_classification_order(
        [SRC, RFP], Path("/o/c.json"), "p", CONFIG, Path("/g.json")),
    "fidelity-check": lambda: stages.build_fidelity_order(
        SRC, Path("/o/r.json"), Path("/o/a.md"), Path("/g.json")),
    "synthesize": lambda: stages.build_synthesis_order(
        Path("/run"), Path("/o/b.json"), "p", CONFIG, CLASSIFICATION, [SRC, RFP], Path("/g.json")),
    "render": lambda: stages.build_render_order(
        Path("/b.json"), Path("/el.md"), Path("/en.md"), Path("/t.md"), Path("/g.json")),
    "creative-shadow": lambda: creative.build_creative_order(
        Path("/b.json"), Path("/o/cb.md"), Path("/tpl"), Path("/g.json"), Path("/spec.json"), "sonnet"),
}


@pytest.mark.parametrize("name", sorted(ORDERS))
def test_every_work_order_carries_the_shared_skeleton(name):
    order = ORDERS[name]()
    assert re.match(r"[A-Z-]+ WORK ORDER — Brief Builder pipeline step \d", order), \
        f"{name}: order must open by naming itself and its PRD step"
    assert "\nINPUT\n" in order, f"{name}: no INPUT block"
    assert "READ ONLY" in order, f"{name}: no read-scope clause"
    assert "answer_key.json" in order and "off limits" in order, \
        f"{name}: the answer-key prohibition is missing — the exam must be named off limits in every order"
    assert "OUTPUT" in order, f"{name}: no OUTPUT contract"
    assert "exactly th" in order, f"{name}: output path is not pinned ('exactly this path/these paths')"
    assert re.search(r"[Rr]eply with one line", order), f"{name}: no one-line reply contract"


@pytest.mark.parametrize("name", ["extract", "synthesize", "render"])
def test_token_heavy_orders_carry_the_output_discipline_block(name):
    """Cost-audit C1: the three stages whose output ran 4-13x their artifact size carry the
    shared efficiency block — batch reads, compose-in-the-Write-call, silent self-check."""
    order = ORDERS[name]()
    assert "EFFICIENCY" in order
    assert "ONE message, as parallel Read calls" in order
    assert "Do not draft, quote, or echo artifact" in order


# --------------------------------------------------------------------------------------
# r2-W-R — every repair order stands on its own in a fresh session
# --------------------------------------------------------------------------------------
# Every attempt is a new `claude -p` session. A repair order that names only "the same file"
# or "the source_file of your first order" hands the model a task without its inputs (r1
# review: 14/24 extraction repairs succeeded; several second attempts wrote nothing). Each
# repair order must therefore carry every path its stage's work order names.

FINDINGS = [{"where": "budget[0]", "problem": "p", "evidence": "e"}]


def _verified(order):
    return extraction.build_verified_repair_order(Path("/o/e.json"), FINDINGS, Path("/o/e.adj.json"),
                                                  order, Path("/x/t.md"))


#: repair name -> (the work order's name, builder of the repair order from that work order)
REPAIRS = {
    "extract": ("extract", lambda o: extraction.build_repair_order(Path("/o/e.json"), ["v1"], o)),
    "extract (verified repair)": ("extract", _verified),
    "extract (verified repair, second round)": ("extract", lambda o: extraction.build_verified_repair_fix_order(
        Path("/o/e.json"), Path("/o/e.adj.json"), ["v1"], _verified(o))),
    "verify-extract": ("verify-extract", lambda o: extraction.build_verify_repair_order(
        Path("/o/e.verify.json"), ["v1"], o)),
    "classify": ("classify", lambda o: stage_classify.build_classification_repair_order(Path("/o/c.json"), ["v1"], o)),
    "fidelity-check": ("fidelity-check", lambda o: stage_fidelity.build_fidelity_repair_order(
        Path("/o/r.json"), Path("/o/a.md"), ["v1"], o)),
    "synthesize": ("synthesize", lambda o: stage_synthesis.build_synthesis_repair_order(Path("/o/b.json"), ["v1"], o)),
    "render": ("render", lambda o: stage_render.build_render_repair_order(Path("/el.md"), Path("/en.md"), ["v1"], o)),
    "creative-shadow": ("creative-shadow", lambda o: creative.build_creative_repair_order(
        Path("/o/cb.md"), ["v1"], o)),
}

_ABS_PATH_RE = re.compile(r"(?<![\w/])(/[\w./-]+)")


def _order_and_repair(name):
    order = ORDERS[REPAIRS[name][0]]()
    return order, REPAIRS[name][1](order)


@pytest.mark.parametrize("name", sorted(REPAIRS))
def test_every_repair_order_is_self_contained(name):
    order, repair = _order_and_repair(name)
    assert re.match(r"(VERIFIED-)?REPAIR ORDER — ", repair), f"{name}: a repair order names itself"
    paths = set(_ABS_PATH_RE.findall(order))
    assert paths, f"{name}: the work order names no paths?"
    missing = sorted(p for p in paths if p not in repair)
    assert not missing, f"{name}: repair order drops input/output paths of its work order: {missing}"
    assert "answer_key.json" in repair and "off limits" in repair, f"{name}: read scope lost"
    assert re.search(r"[Rr]eply with one line", repair)
    for dangling in ("first order", "your previous order", "the order above"):
        assert dangling not in repair, f"{name}: refers to an order the fresh session never saw"


@pytest.mark.parametrize("name", sorted(n for n in REPAIRS if "verified" not in n))
def test_gate_repair_orders_carry_the_violations_and_restate_the_order_verbatim(name):
    order, repair = _order_and_repair(name)
    assert "  - v1" in repair
    assert order.rstrip() in repair, f"{name}: the original work order is not restated verbatim"
    assert set(replay.output_paths(order)) <= set(replay.output_paths(repair))


def test_an_extract_repair_after_no_file_asks_for_the_full_extraction_not_a_fix():
    order = ORDERS["extract"]()
    repair = extraction.build_repair_order(Path("/o/e.json"), ["no file written at /o/e.json"], order)
    assert "nothing to repair" in repair and "Carry out the original work order" in repair
    assert "Do not re-extract" not in repair and "Read that file" not in repair
    fix = extraction.build_repair_order(Path("/o/e.json"), ["budget[0]: location '[9]' does not occur"], order)
    assert "Read that file" in fix and "nothing to repair" not in fix


def test_verified_repair_names_the_source_literally():
    _order, repair = _order_and_repair("extract (verified repair)")
    assert "the source_file /x/t.md" in repair
    assert "F1: budget[0]: p (source evidence: e)" in repair


def _capture_prompts(monkeypatch):
    """agents.invoke replaced by a fake that records each prompt and writes nothing."""
    prompts = []

    def fake(agent, prompt, access_dirs, timeout_s=agents.DEFAULT_TIMEOUT_S, model_override=None):
        prompts.append(prompt)
        return agents.SubagentResult(agent=agent, ok=True)

    monkeypatch.setattr(agents, "invoke", fake)
    return prompts


def _stage_calls(tmp_path):
    text = "[00:00:01] A: text\n"
    source_file = tmp_path / "t.md"
    source_file.write_text(text, encoding="utf-8")
    src = gates.SourceDoc("t", "transcript", "2026-01-01", source_file, text)
    glossary = tmp_path / "client.json"
    glossary.write_text('{"client_id": "c", "sensitivity_tier": "S1", "terms": []}', encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    brief = {"meta": {"sources": []}, "conflicts": [], "open_questions": [],
             "signoff": {"status": "signed_off"}}
    # The creative stage starts only under a recorded sign-off regime (W-G): this synthetic run
    # records the brief-signoff one, so the stage reaches its model calls.
    bind_declaration(run, tmp_path, "synthetic")
    approval.record_regime(run, approval.BRIEF_SIGNOFF, "Synthetic operator", "work-order wiring test")
    return {
        "classify": lambda: stages.classify([src], run, "p", CONFIG, glossary, []),
        "fidelity-check": lambda: stages.fidelity_check(src, run, glossary, []),
        "synthesize": lambda: stages.synthesize(run, "p", CONFIG, CLASSIFICATION, [src], {}, glossary, []),
        "render": lambda: stages.render(run, brief, glossary, []),
        "creative-shadow": lambda: creative.creative_shadow(run, brief, glossary, [], model_alias="sonnet"),
        "extract": lambda: extraction.extract_source(src, run, "p", CONFIG, glossary, []),
    }


@pytest.mark.parametrize("stage", ["classify", "fidelity-check", "synthesize", "render", "creative-shadow",
                                   "extract"])
def test_each_stage_sends_its_own_work_order_again_inside_the_repair(stage, tmp_path, monkeypatch):
    """Wiring, not just builders: a stage's second prompt restates its first verbatim."""
    prompts = _capture_prompts(monkeypatch)
    with pytest.raises(gates.GateError):
        _stage_calls(tmp_path)[stage]()
    assert len(prompts) == 2
    assert prompts[1].startswith("REPAIR ORDER")
    assert prompts[0].rstrip() in prompts[1]
