"""Deterministic gates for the Brief Builder pipeline.

Nothing in this module calls a model. Every function here is a pure decision over
text or JSON, which is the point: the readiness verdict, the schema verdict and the
readiness block are the parts of the system a reviewer must be able to reproduce by
hand. If a value in here ever depends on a model, the "deterministic core" claim in
the PRD stops being true.

Two rules this module encodes structurally rather than by convention:

* The answer key is harness-only. `discover_sources` reads `*.md` and explicitly
  skips `HARNESS_ONLY_FILES`, so a pipeline run cannot see the exam.
* Sensitivity scope is enforced in code *and* in `brief_schema.json` (PRD DR-11);
  S2/S3 cannot be represented, let alone processed.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_DIR = REPO_ROOT / "schema"

# --------------------------------------------------------------------------------------
# POLICY — agency-tunable thresholds.
#
# These are judgment calls, deliberately gathered in one block instead of scattered
# through the logic, so that changing agency policy is a diff a non-programmer can read.
# They are NOT tuned against the fixture answer key; they encode what the PRD says a
# briefable project needs.
# --------------------------------------------------------------------------------------

#: The readiness gate refuses without these source types (PRD §5 step 1).
#: The RFP is the one source that states what the client believes they are buying;
#: without it there is no claim to check the conversation against.
REQUIRED_SOURCE_TYPES = ("rfp",)

#: ...and at least one of these, so no brief ever rests on a single source.
#: `background` is deliberately excluded: context creates no commitments (SOURCES.md §5).
CORROBORATING_SOURCE_TYPES = ("transcript", "email_thread")

#: A briefable project has *some* budget and *some* timeline signal somewhere.
#: Generic domain vocabulary, GR + EN — never fixture strings.
BUDGET_SIGNAL_PATTERNS = (
    r"budget",
    r"προϋπολογισμ",
    r"€",
    r"\beur\b",
    r"κόστο",
    r"media spend",
)
TIMELINE_SIGNAL_PATTERNS = (
    r"timeline",
    r"launch",
    r"deadline",
    r"χρονοδιάγραμμα",
    r"προθεσμ",
    r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b",
    r"\b(?:Ιανουαρ|Φεβρουαρ|Μαρτ|Απριλ|Μα[ΐι]|Ιουν|Ιουλ|Αυγούστ|Σεπτεμβρ|Οκτωβρ|Νοεμβρ|Δεκεμβρ)",
    r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\b",
)

#: The 7 briefable fields. The readiness block counts coverage across exactly these.
BRIEF_FIELDS = (
    "objectives",
    "audiences",
    "key_messages",
    "deliverables",
    "timeline",
    "budget",
    "mandatories",
)

#: A draft with fewer evidenced fields than this is thin input, not a brief.
READINESS_MIN_FIELDS_WITH_EVIDENCE = 5

#: ...and a draft where more than this share of entries rest on implication is thin too.
READINESS_MAX_LOW_CONFIDENCE_SHARE = 0.4

#: Decimal places for `low_confidence_share`. The harness recomputes this block and
#: compares values, so the rounding rule has to be part of the contract, not incidental.
READINESS_SHARE_PRECISION = 4

#: v1 serves S0–S1 only (PRD §3, DR-11).
PERMITTED_SENSITIVITY_TIERS = ("S0", "S1")

#: Never opened by a pipeline run. The exam does not get to see itself being taken.
HARNESS_ONLY_FILES = ("answer_key.json",)

VALID_SOURCE_TYPES = ("transcript", "rfp", "email_thread", "background")


# --------------------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------------------


class GateError(Exception):
    """Base class for every deterministic refusal."""


class InputContractError(GateError):
    """A file in the Input folder does not declare itself per the source header contract."""


class SchemaValidationError(GateError):
    """A model-produced artifact failed its schema. The run stops; nothing is patched."""

    def __init__(self, schema_name: str, errors: Sequence[str]):
        self.schema_name = schema_name
        self.errors = list(errors)
        detail = "\n".join(f"  - {e}" for e in self.errors)
        super().__init__(f"{schema_name}: {len(self.errors)} validation error(s)\n{detail}")


class ScopeError(GateError):
    """The project falls outside the MVP's declared scope (sensitivity tier)."""


# --------------------------------------------------------------------------------------
# Input contract
# --------------------------------------------------------------------------------------

#: Every source declares itself on a header line, e.g.
#:   source_id: rfp_meltemi · source_type: rfp · source_date: 2026-06-28
#: This is the whole input contract. The runner works on any folder that honours it —
#: nothing about the fixture is baked into this module.
_HEADER_KEYS = ("source_id", "source_type", "source_date")
_HEADER_SCAN_LINES = 12
_HEADER_FIELD_RE = re.compile(r"(source_id|source_type|source_date)\s*:\s*([^·|\n]+)")


@dataclass(frozen=True)
class SourceDoc:
    """One declared source document from the Input folder."""

    source_id: str
    source_type: str
    source_date: str
    path: Path
    text: str

    def as_meta(self) -> dict:
        """The `meta.sources[]` shape of `brief_schema.json`."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "source_date": self.source_date,
        }


def parse_source_header(text: str, path: Path) -> dict:
    """Pull the self-declaration header out of a source document.

    Raises InputContractError rather than guessing: a file that will not say what it is
    does not get read into a brief.
    """
    head = "\n".join(text.splitlines()[:_HEADER_SCAN_LINES])
    found = {k: v.strip() for k, v in _HEADER_FIELD_RE.findall(head)}
    missing = [k for k in _HEADER_KEYS if k not in found or not found[k]]
    if missing:
        raise InputContractError(
            f"{path.name}: source header missing {missing}. "
            f"Every input file must declare `source_id: … · source_type: … · source_date: …` "
            f"within its first {_HEADER_SCAN_LINES} lines."
        )
    if found["source_type"] not in VALID_SOURCE_TYPES:
        raise InputContractError(
            f"{path.name}: source_type '{found['source_type']}' is not one of {list(VALID_SOURCE_TYPES)}."
        )
    return found


def discover_sources(project_dir: Path) -> list[SourceDoc]:
    """Read every declared source in an Input folder, in stable order.

    Only `*.md` is read, and `HARNESS_ONLY_FILES` is skipped explicitly — the answer key
    is structurally unreachable from a pipeline run, not merely un-referenced.
    """
    project_dir = Path(project_dir)
    if not project_dir.is_dir():
        raise InputContractError(f"{project_dir} is not a directory.")

    sources: list[SourceDoc] = []
    for path in sorted(project_dir.glob("*.md")):
        if path.name in HARNESS_ONLY_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        header = parse_source_header(text, path)
        sources.append(
            SourceDoc(
                source_id=header["source_id"],
                source_type=header["source_type"],
                source_date=header["source_date"],
                path=path,
                text=text,
            )
        )

    if not sources:
        raise InputContractError(f"{project_dir}: no source documents found.")

    ids = [s.source_id for s in sources]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise InputContractError(f"{project_dir}: duplicate source_id(s) {duplicates}.")
    return sources


# --------------------------------------------------------------------------------------
# Step 1 — input readiness gate
# --------------------------------------------------------------------------------------


@dataclass
class ReadinessGateResult:
    """The gate's verdict. `ok is False` means the system refuses to draft."""

    ok: bool
    present_types: list[str] = field(default_factory=list)
    missing_required: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "present_types": self.present_types,
            "missing_required": self.missing_required,
            "missing_signals": self.missing_signals,
            "message": self.message,
        }


def _has_signal(patterns: Iterable[str], haystack: str) -> bool:
    return any(re.search(p, haystack, flags=re.IGNORECASE) for p in patterns)


def readiness_gate(sources: Sequence[SourceDoc]) -> ReadinessGateResult:
    """PRD §5 step 1 — refuse to draft on insufficient input.

    Refusal is the product working. A brief drafted from a folder that never mentioned a
    budget is a confident-looking guess, which is the failure mode the whole system exists
    to avoid, so the gate names what is missing and hands the ask back to the account lead.
    """
    present_types = sorted({s.source_type for s in sources})
    missing_required = [t for t in REQUIRED_SOURCE_TYPES if t not in present_types]
    if not any(t in present_types for t in CORROBORATING_SOURCE_TYPES):
        missing_required.append(f"one of {list(CORROBORATING_SOURCE_TYPES)}")

    corpus = "\n".join(s.text for s in sources)
    missing_signals = []
    if not _has_signal(BUDGET_SIGNAL_PATTERNS, corpus):
        missing_signals.append("budget")
    if not _has_signal(TIMELINE_SIGNAL_PATTERNS, corpus):
        missing_signals.append("timeline")

    if not missing_required and not missing_signals:
        return ReadinessGateResult(
            ok=True,
            present_types=present_types,
            message=f"input sufficient — {len(sources)} source(s): {', '.join(present_types)}",
        )

    asks = []
    if missing_required:
        asks.append("missing source(s): " + ", ".join(missing_required))
    if missing_signals:
        asks.append("no " + " or ".join(missing_signals) + " signal in any source")
    return ReadinessGateResult(
        ok=False,
        present_types=present_types,
        missing_required=missing_required,
        missing_signals=missing_signals,
        message=(
            "insufficient input — the system will not draft. "
            + "; ".join(asks)
            + ". Request this from the client and re-run."
        ),
    )


# --------------------------------------------------------------------------------------
# Scope enforcement
# --------------------------------------------------------------------------------------


def enforce_sensitivity_tier(tier: Optional[str]) -> str:
    """S0–S1 only in v1 (PRD DR-11). S2/S3 is a refusal, not a warning."""
    if tier not in PERMITTED_SENSITIVITY_TIERS:
        raise ScopeError(
            f"sensitivity_tier {tier!r} is out of MVP scope. "
            f"v1 serves {list(PERMITTED_SENSITIVITY_TIERS)}; regulated clients onboard "
            f"after the governance review (PRD DR-11)."
        )
    return tier


# --------------------------------------------------------------------------------------
# Schema validation
# --------------------------------------------------------------------------------------


def load_schema(name: str) -> dict:
    """Load a schema by bare name, e.g. `brief_schema` or `extract_schema`."""
    path = SCHEMA_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _validate(instance: dict, schema_name: str) -> None:
    from jsonschema import Draft7Validator

    validator = Draft7Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        raise SchemaValidationError(
            schema_name,
            [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors],
        )


def validate_extract(instance: dict) -> None:
    """Validate one per-source extract. Raises SchemaValidationError."""
    _validate(instance, "extract_schema")


def validate_brief(instance: dict) -> None:
    """Validate the canonical brief. Raises SchemaValidationError."""
    _validate(instance, "brief_schema")


def find_uncited_items(extract: dict) -> list[str]:
    """Every evidence item must carry a non-empty `location` and `anchor` (SOURCES.md rule 2).

    The schema enforces `minLength: 1`; this returns human-readable paths so a failing run
    can say *which* item, not just that something failed.
    """
    violations: list[str] = []
    for fieldname in BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname, []) or []):
            for key in ("location", "anchor"):
                if not (item.get(key) or "").strip():
                    violations.append(f"{fieldname}[{idx}]: empty {key} — value={item.get('value', '')!r}")
    return violations


# --------------------------------------------------------------------------------------
# The readiness block — recomputed, never trusted
# --------------------------------------------------------------------------------------


def compute_readiness_block(brief: dict) -> dict:
    """Compute `brief.readiness` deterministically from the brief's own contents.

    SYNTHESIS.md rule 8 forbids the model from populating this block, and the Tier-2 DoD
    has the harness recompute it and compare. So this function is the single definition of
    the value, called once by the runner and once by the harness — same input, same output,
    no model in the path.
    """
    entries = [e for f in BRIEF_FIELDS for e in (brief.get(f) or [])]
    evidenced_fields = sum(
        1
        for f in BRIEF_FIELDS
        if any((e.get("evidence") or []) for e in (brief.get(f) or []))
    )
    low = sum(1 for e in entries if e.get("confidence") == "low")
    share = round(low / len(entries), READINESS_SHARE_PRECISION) if entries else 0.0

    ready = (
        evidenced_fields >= READINESS_MIN_FIELDS_WITH_EVIDENCE
        and share <= READINESS_MAX_LOW_CONFIDENCE_SHARE
    )
    return {
        "fields_with_evidence": evidenced_fields,
        "low_confidence_share": share,
        "open_question_count": len(brief.get("open_questions") or []),
        "verdict": "ready_for_review" if ready else "thin_input_return_to_client",
    }
