"""Pipeline step 2 — classification.

`classify` reports the sensitivity tier from client config; it never infers one (DR-11).
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline import agents, gates
from pipeline.stage_common import HaltForHuman, stage_failure

CLASSIFICATION_KEYS = ("project_type", "classification_confidence", "sensitivity_tier")
PROJECT_TYPES = ("advertising_creative", "other", "unclassified_ask_human")


def build_classification_order(sources, output_file: Path, project_id: str, client_config: dict,
                               glossary_path: Path) -> str:
    """The classification work order: the sources to read and the one JSON object to write."""
    listed = "\n".join(f"    {s.source_id} ({s.source_type}, {s.source_date}): {s.path}" for s in sources)
    return f"""CLASSIFICATION WORK ORDER — Brief Builder pipeline step 2.

Decide the project type. Report the sensitivity tier from client config — never infer it.

INPUT
  project_id      : {project_id}
  client_glossary : {glossary_path}
  sources:
{listed}

READ ONLY the files listed above and the client glossary. Any file named `answer_key.json` is
test apparatus and is off limits.

OUTPUT
  Write one JSON object to exactly this path:
    {output_file}

  Required keys: project_id, client_id, project_type, classification_confidence,
  sensitivity_tier, tier_source, rationale, evidence, question_for_human, halt_reason.

  project_type must be one of: {list(PROJECT_TYPES)}
  classification_confidence must be one of: ["high", "medium", "low"]
  sensitivity_tier must be copied from the client glossary, not judged.

Reply with one line: the project_type and confidence you wrote.
"""


def check_classification(path: Path, client_config: dict) -> list:
    """Gate the classification artifact: keys, enums, the configured tier, evidence, rule 3."""
    if not path.is_file():
        return [f"no file written at {path}"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"not valid JSON: {exc}"]

    violations = [f"missing key: {k}" for k in CLASSIFICATION_KEYS if k not in payload]
    if violations:
        return violations

    if payload["project_type"] not in PROJECT_TYPES:
        violations.append(f"project_type {payload['project_type']!r} not in {list(PROJECT_TYPES)}")
    if payload["classification_confidence"] not in ("high", "medium", "low"):
        violations.append(f"classification_confidence {payload['classification_confidence']!r} invalid")

    # The tier is client configuration. A classifier that returns a different one has judged it.
    configured = client_config.get("sensitivity_tier")
    if payload["sensitivity_tier"] != configured:
        violations.append(
            f"sensitivity_tier {payload['sensitivity_tier']!r} does not match the client config "
            f"({configured!r}) — the tier is read from onboarding, never inferred (PRD DR-11)"
        )
    if not (payload.get("evidence") or []):
        violations.append("no evidence for the project_type decision — a routing call with no citation is a vibe")

    # classify.md rule 3, machine-checked: below the confidence threshold the classifier asks.
    # A low-confidence guess that still routes is exactly the "split the difference" the rule
    # forbids, and the question is what makes the halt actionable for the account lead.
    if payload["classification_confidence"] == "low" and payload["project_type"] != "unclassified_ask_human":
        violations.append(
            f"classification_confidence is 'low' but project_type is {payload['project_type']!r} — "
            f"below the threshold the classifier asks: emit 'unclassified_ask_human' with a "
            f"question_for_human (classify.md rule 3)"
        )
    if payload["project_type"] == "unclassified_ask_human" and not str(payload.get("question_for_human") or "").strip():
        violations.append(
            "project_type is 'unclassified_ask_human' but question_for_human is empty — phrase the "
            "question the account lead should answer (classify.md rule 3)"
        )
    return violations


def classify(sources, run_dir: Path, project_id: str, client_config: dict, glossary_path: Path,
             access_dirs) -> dict:
    """Run the classify subagent through its gate; halt for a human below the confidence threshold."""
    output_file = Path(run_dir) / "classification.json"
    order = build_classification_order(sources, output_file, project_id, client_config, glossary_path)

    attempts, failed = agents.run_gated(
        "classify", order,
        lambda: check_classification(output_file, client_config),
        lambda v: agents.repair_order("classification", v, f"Fix exactly these and rewrite {output_file}."),
        access_dirs, stage="classify", site="classify", run_dir=Path(run_dir),
    )
    if failed:
        raise stage_failure("classify", failed)

    payload = json.loads(output_file.read_text(encoding="utf-8"))
    if payload.get("halt_reason"):
        raise HaltForHuman(f"classification halted: {payload['halt_reason']}")
    if payload["project_type"] == "unclassified_ask_human":
        raise HaltForHuman(
            "classification confidence too low to route automatically. "
            f"Question for the account lead: {payload.get('question_for_human') or '(none supplied)'}"
        )

    gates.enforce_sensitivity_tier(payload["sensitivity_tier"])
    return {
        "output_file": str(output_file),
        "project_type": payload["project_type"],
        "classification_confidence": payload["classification_confidence"],
        "sensitivity_tier": payload["sensitivity_tier"],
        "attempts": attempts,
    }
