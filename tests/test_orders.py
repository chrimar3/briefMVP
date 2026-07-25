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

from pipeline import creative, extraction, gates, stages

SRC = gates.SourceDoc("t", "transcript", "2026-01-01", Path("/x/t.md"), "text")
RFP = gates.SourceDoc("r", "rfp", "2026-01-01", Path("/x/r.md"), "text")
CONFIG = {"client_id": "c", "sensitivity_tier": "S1"}
CLASSIFICATION = {"project_type": "advertising_creative", "classification_confidence": "high",
                  "sensitivity_tier": "S1"}

ORDERS = {
    "extract": lambda: extraction.build_work_order(
        SRC, Path("/o/e.json"), "p", CONFIG, Path("/g.json")),
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
