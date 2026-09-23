"""Layering: the Stage-1 pipeline does not depend on the Tier 5–8 agency operations.

Stage 1 (input contract, stages, gates, review pages) must stay runnable and reviewable without
the agency tooling. Two edges are documented exceptions:

* `stage_synthesis -> quality` — the synthesis step writes the evidence-coverage ledger;
* `runner -> approval` — the runner prepares a run for the approval workflow (`approval.prepare_run`).

Stage 2 (`creative`) and the review shelf (`publish`) consult the approval policy before they
act on a signed brief, so each may import `approval` and nothing else from Tier 5–8.
Every pipeline module must be classified here, so a new module is placed deliberately.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parents[1] / "pipeline"

STAGE_1 = {
    "agents", "conflicts", "data_policy", "diagnostics", "docview", "extract_rules", "extraction", "gates", "greek_lint",
    "intake",
    "money", "prescreen", "render_checks", "render_template", "replay", "review", "run_review", "runner", "share",
    "stage_classify", "stage_common", "stage_fidelity", "stage_render", "stage_synthesis", "stages",
}
STAGE_2_AND_SHELF = {"creative", "publish"}
TIER_5_8 = {
    "agency", "agency_edit", "approval", "clarifications", "client_pack", "delivery", "effort", "handover",
    "operations", "quality", "question_exchange", "release_control", "retention", "spec_catalog",
}
#: Leaf utilities any layer may use (they import no policy; see tests/test_records_clock.py).
SHARED = {"__init__", "clock", "records", "revisions"}

ALLOWED_TIER_5_8_IMPORTS = {
    "stage_synthesis": {"quality"},
    "runner": {"approval"},
    "creative": {"approval"},
    "publish": {"approval"},
}


def pipeline_imports(path: Path) -> set[str]:
    """Every `pipeline` module a file imports, at any depth (function-local imports included)."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom) and node.module == "pipeline":
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("pipeline."):
            found.add(node.module.split(".", 1)[1].split(".", 1)[0])
        elif isinstance(node, ast.Import):
            found.update(a.name.split(".")[1] for a in node.names if a.name.startswith("pipeline."))
    return found


def test_every_pipeline_module_is_classified():
    modules = {p.stem for p in PIPELINE.glob("*.py")}
    classified = STAGE_1 | STAGE_2_AND_SHELF | TIER_5_8 | SHARED
    assert modules - classified == set(), "classify the new module in tests/test_layering.py"
    assert classified - modules == set(), "a classified module no longer exists"
    groups = [STAGE_1, STAGE_2_AND_SHELF, TIER_5_8, SHARED]
    assert sum(len(g) for g in groups) == len(classified), "a module is in two layers"


@pytest.mark.parametrize("module", sorted(STAGE_1 | STAGE_2_AND_SHELF))
def test_stage_modules_import_no_agency_operations(module):
    reached = pipeline_imports(PIPELINE / f"{module}.py") & TIER_5_8
    allowed = ALLOWED_TIER_5_8_IMPORTS.get(module, set())
    assert reached <= allowed, f"{module} imports Tier 5–8 module(s) {sorted(reached - allowed)}"


@pytest.mark.parametrize("module", sorted(SHARED - {"__init__"}))
def test_shared_utilities_import_only_shared_utilities(module):
    assert pipeline_imports(PIPELINE / f"{module}.py") <= SHARED


def test_documented_exceptions_are_still_used():
    """An exception that is no longer needed is removed from the list rather than kept as a loophole."""
    for module, allowed in ALLOWED_TIER_5_8_IMPORTS.items():
        assert allowed <= pipeline_imports(PIPELINE / f"{module}.py"), f"{module} no longer needs {allowed}"
