"""Pipeline step 9 — creative-shadow (Stage 2), in shadow mode. Tier 4.

Stage 1 was extraction; Stage 2 is compression — a single-minded proposition, not a summary.
It runs ONLY on a signed-off brief (DR-8: the human gate stands between the stages so a stage-1
error cannot propagate into creative), and its channel specs come ONLY from the deterministic
spec table (DR-7: dimensions and durations are facts, not creative decisions).

Two deterministic guarantees this module enforces, because a model cannot be trusted to enforce
them on itself:

* **Signed-off input.** `creative_shadow` refuses unless `signoff.status == "signed_off"`.
* **No invented specs.** `check_creative_brief` scans the draft for spec-shaped tokens
  (resolutions like 1080x1920, aspect ratios like 9:16) and fails if any does not appear in the
  spec table byte-for-byte. This is the Tier-4 machine check.

The A/B (`run_ab`) runs the *same* creative-shadow definition twice — sonnet vs opus — on the
identical signed brief, so the only variable is the model. Everything else is held constant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pipeline import agents, gates

MAX_ATTEMPTS = agents.MAX_ATTEMPTS

#: The models the Tier-4 A/B compares, in order. Same input, same skeleton — only the model moves.
AB_MODELS = ("sonnet", "opus")

#: Spec-shaped tokens a creative brief might contain. Anything matching these MUST be a value
#: that exists in the spec table; a match that isn't in the table is a generated (hallucinated)
#: spec, which is exactly what DR-7 exists to prevent.
_SPEC_TOKEN_RES = re.compile(r"\b\d{3,4}\s*[x×]\s*\d{3,4}\b")   # 1080x1920
#: Aspect ratios only — NOT timecodes. A duration like "00:06" (six seconds) is legitimate
#: creative content and is not a spec drawn from the table; matching it would force the model to
#: strip real durations to pass. Aspect ratios in this domain have no leading zeros (9:16, 4:5,
#: 16:9); timecodes do (00:06, 0:30). Requiring both sides to start 1-9 excludes the timecodes
#: while still catching an invented aspect ratio (16:9 when the table only has 9:16).
_SPEC_TOKEN_RATIO = re.compile(r"\b[1-9]\d?\s*:\s*[1-9]\d?\b")   # 9:16, not 00:06


class CreativeError(gates.GateError):
    """The creative stage could not produce an acceptable artifact."""


class NotSignedOff(gates.GateError):
    """Stage 2 was asked to run on a brief the human has not signed (DR-8)."""


def load_spec_table(path: Path = None) -> dict:
    path = Path(path) if path else gates.CONFIG_DIR / "channel_specs.json"
    if not path.is_file():
        raise CreativeError(f"channel spec table not found at {path}")
    table = json.loads(path.read_text(encoding="utf-8"))
    if not (table.get("specs") or []):
        raise CreativeError(f"{path}: spec table has no rows")
    return table


def _allowed_spec_values(spec_table: dict) -> set:
    """Every spec-shaped value the table legitimately contains (resolutions + aspect ratios),
    normalised so `1080 x 1920` and `1080x1920` compare equal."""
    allowed = set()
    for row in spec_table.get("specs") or []:
        for key in ("resolution", "aspect_ratio"):
            value = row.get(key)
            if value:
                allowed.add(_norm_spec(value))
    return allowed


def _norm_spec(token: str) -> str:
    return re.sub(r"\s+", "", token).replace("×", "x").lower()


def require_signed_off(brief: dict) -> None:
    status = (brief.get("signoff") or {}).get("status")
    if status != "signed_off":
        raise NotSignedOff(
            f"creative-shadow runs only on a signed-off brief; signoff.status is {status!r}. "
            f"The human gate stands between the stages by design (PRD DR-8)."
        )


def check_creative_brief(path: Path, spec_table: dict) -> list:
    """Every reason the creative draft is unacceptable. The spec-match rule is the Tier-4 gate."""
    if not path.is_file():
        return [f"no creative brief written at {path}"]
    text = path.read_text(encoding="utf-8")

    violations = []
    if "SHADOW MODE" not in text:
        violations.append("missing the SHADOW MODE banner — every creative draft must declare it is not for delivery")

    allowed = _allowed_spec_values(spec_table)
    for match in _SPEC_TOKEN_RES.findall(text) + _SPEC_TOKEN_RATIO.findall(text):
        if _norm_spec(match) not in allowed:
            violations.append(
                f"spec value {match!r} does not appear in the deterministic spec table — "
                f"channel specs are looked up, never generated (PRD DR-7)"
            )
    return violations


def build_creative_order(brief_file: Path, output_file: Path, template_dir: Path,
                         glossary_path: Path, spec_table_path: Path, model_alias: str) -> str:
    return f"""CREATIVE-SHADOW WORK ORDER — Brief Builder pipeline step 9 (SHADOW MODE).

Produce ONE creative-brief draft from a SIGNED-OFF client brief, for evaluation only. Your
governing rules are the creative-shadow instructions in your agent definition.

INPUT
  signed_brief    : {brief_file}     (signoff.status must be "signed_off"; it is)
  spec_table      : {spec_table_path}
  client_glossary : {glossary_path}
  templates_dir   : {template_dir}

READ ONLY those files. Any file named `answer_key.json` is off limits.

OUTPUT
  Write one Markdown file to exactly this path:
    {output_file}

  First line MUST be the shadow-mode banner (see your rules) — this draft is never delivered.

  Channel specs (dimensions, aspect ratios, durations, file types) come ONLY from the spec
  table, copied byte-for-byte, each tagged with the row id you used, e.g. `[spec: instagram_reel]`.
  Do NOT invent or adjust a spec value. If a needed channel is not in the table, write
  `SPEC NOT IN TABLE — ask traffic/production` and move on. The runner scans your draft for any
  spec-shaped value (like 1080x1920 or 9:16) and fails the run if it is not in the table.

  Every fact about the client, product, audience or constraint traces to the signed brief.
  Unresolved conflicts and open questions travel into your readiness checklist. Conditional and
  retracted items never become commitments.

Reply with one line naming the file written and the single-minded proposition.
"""


def creative_shadow(run_dir: Path, brief: dict, glossary_path: Path, access_dirs,
                    model_alias: str, spec_table_path: Path = None) -> dict:
    """Run the creative-shadow subagent once, on the given model, gated on its artifact."""
    require_signed_off(brief)
    spec_table = load_spec_table(spec_table_path)
    resolved_spec_path = Path(spec_table_path) if spec_table_path else gates.CONFIG_DIR / "channel_specs.json"

    out_dir = Path(run_dir) / "creative"
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / f"creative_brief_{model_alias}.md"
    brief_file = Path(run_dir) / "brief.json"
    template_dir = gates.REPO_ROOT / "templates"

    order = build_creative_order(brief_file, output_file, template_dir, glossary_path,
                                 resolved_spec_path, model_alias)
    attempts = []
    for attempt in range(1, MAX_ATTEMPTS + 1):
        result = agents.invoke("creative-shadow", order, access_dirs, model_override=model_alias)
        violations = check_creative_brief(output_file, spec_table)
        attempts.append({"attempt": attempt, "subagent": result.as_dict(), "violations": violations})
        if not violations:
            return {
                "model_alias": model_alias,
                "output_file": str(output_file),
                "model_ids": result.model_ids,
                "cost_usd": result.cost_usd,
                "usage": result.usage,
                "chars": len(output_file.read_text(encoding="utf-8")),
                "attempts": attempts,
            }
        order = (
            "REPAIR ORDER — your creative draft failed the gate:\n"
            + "\n".join(f"  - {v}" for v in violations)
            + f"\n\nFix exactly these and rewrite {output_file}. Spec values must be copied from "
              f"the spec table byte-for-byte; do not invent them."
        )
    raise CreativeError(
        f"creative-shadow[{model_alias}]: no acceptable draft after {MAX_ATTEMPTS} attempts:\n"
        + "\n".join(f"  - {v}" for v in attempts[-1]["violations"])
    )


def run_ab(run_dir: Path, brief: dict, glossary_path: Path, access_dirs,
           spec_table_path: Path = None) -> list:
    """The Tier-4 A/B: the same signed brief through creative-shadow on sonnet, then opus."""
    require_signed_off(brief)
    return [
        creative_shadow(run_dir, brief, glossary_path, access_dirs, model_alias=m,
                        spec_table_path=spec_table_path)
        for m in AB_MODELS
    ]
