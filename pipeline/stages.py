"""Pipeline steps 2, 3, 6 and 7 — the remaining model stages of Stage 1 (a re-export facade).

Each stage follows the same shape as extraction: the runner builds a work order out of paths
and configuration, the subagent produces an artifact, and a deterministic gate decides
whether that artifact is acceptable. The subagents' own self-checks are quality aids; these
gates are the contract, because a gate that a model can talk its way past is not a gate.

Stage boundaries worth stating explicitly, because each is a design decision rather than an
implementation detail:

* `classify` reports the sensitivity tier from client config; it never infers one (DR-11).
* `fidelity-check` annotates and never rewrites — verified by stripping annotations and
  requiring byte-equality with the original (TRANSCRIPTS.md §5).
* `synthesize` never populates `readiness`; the runner computes it (SYNTHESIS.md rule 8).
* `render` produces both languages from one object, and neither from the other (DR-6).

The code lives in one module per stage; this module keeps every name the runner, the agency
layer, the replay tooling and the tests import from `pipeline.stages`:

    stage_common     StageError, HaltForHuman, stage_failure
    stage_classify   step 2 — work order, gate, stage
    stage_fidelity   step 3 — work order, gate, stage
    stage_synthesis  step 6 — work order, the named gate rules (SYNTHESIS_RULES), stage
    stage_render     step 7 — work order, stage
    render_checks    check_render (shared with the agency audit) and its helpers
    render_template  template sets, resolution links, check_render_template
    greek_lint       the non-blocking language lint
    money            money_figures, the one currency normaliser
"""

from __future__ import annotations

from pipeline import PIPELINE_VERSION, agents, gates
from pipeline.greek_lint import GREEK_STYLE_PATH, load_greek_style, render_language_warnings
from pipeline.money import money_figures
from pipeline.render_checks import CITATION_TAG_RE, CLAIM_SECTION_RE, STRUCTURAL_PREFIXES, check_render, claim_lines
from pipeline.render_template import (
    DEFAULT_BRIEF_TEMPLATE,
    TEMPLATES_DIR,
    check_render_template,
    load_template_labels,
    resolution_links,
    resolve_brief_template,
)
from pipeline.stage_classify import (
    CLASSIFICATION_KEYS,
    PROJECT_TYPES,
    build_classification_order,
    check_classification,
    classify,
)
from pipeline.stage_common import HaltForHuman, StageError, stage_failure
from pipeline.stage_fidelity import (
    FIDELITY_ANNOTATION_RE,
    FIDELITY_REPORT_KEYS,
    FIDELITY_SCORES,
    FIDELITY_VERDICTS,
    build_fidelity_order,
    check_fidelity,
    fidelity_check,
)
from pipeline.stage_render import build_render_order, render
from pipeline.stage_synthesis import (
    SYNTHESIS_RULES,
    _timestamp_seconds,
    build_synthesis_order,
    check_synthesis,
    synthesize,
)

__all__ = [
    "PIPELINE_VERSION",
    "agents",
    "gates",
    "GREEK_STYLE_PATH",
    "load_greek_style",
    "render_language_warnings",
    "money_figures",
    "CITATION_TAG_RE",
    "CLAIM_SECTION_RE",
    "STRUCTURAL_PREFIXES",
    "check_render",
    "claim_lines",
    "DEFAULT_BRIEF_TEMPLATE",
    "TEMPLATES_DIR",
    "check_render_template",
    "load_template_labels",
    "resolution_links",
    "resolve_brief_template",
    "CLASSIFICATION_KEYS",
    "PROJECT_TYPES",
    "build_classification_order",
    "check_classification",
    "classify",
    "HaltForHuman",
    "StageError",
    "stage_failure",
    "FIDELITY_ANNOTATION_RE",
    "FIDELITY_REPORT_KEYS",
    "FIDELITY_SCORES",
    "FIDELITY_VERDICTS",
    "build_fidelity_order",
    "check_fidelity",
    "fidelity_check",
    "build_render_order",
    "render",
    "SYNTHESIS_RULES",
    "_timestamp_seconds",
    "build_synthesis_order",
    "check_synthesis",
    "synthesize",
]
