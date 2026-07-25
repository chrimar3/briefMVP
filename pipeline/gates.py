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

#: Source types that can carry a commitment. `background` is deliberately excluded:
#: context creates no deliverable, budget or deadline on its own (SOURCES.md §5), so a
#: brand-guidelines PDF can never be one of the sources a brief rests on.
SUBSTANTIVE_SOURCE_TYPES = ("rfp", "transcript", "email_thread")

#: Minimum input set: no brief ever rests on a single source.
MIN_SUBSTANTIVE_SOURCES = 2

#: A briefable project has *some* budget and *some* timeline signal somewhere.
#: Generic domain vocabulary, GR + EN — never fixture strings.
BUDGET_SIGNAL_PATTERNS = (
    r"budget",
    r"προϋπολογισμ",
    r"€",
    r"\beur\b",
    r"ευρώ",
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

#: Readiness thresholds live in `config/readiness_policy.json`, not here — they are agency
#: policy (like the glossary), and a partner changing "5 of 7" should not need a code diff.
#: See `load_readiness_policy`.
CONFIG_DIR = REPO_ROOT / "config"
READINESS_POLICY_PATH = CONFIG_DIR / "readiness_policy.json"

#: Decimal places for `low_confidence_share`. This one stays in code: it is not policy but
#: contract — the harness recomputes the block and compares values, so the rounding rule
#: must be identical on both sides and must not be editable independently.
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


class ConfigError(GateError):
    """Agency policy config is missing or malformed.

    Deliberately fatal rather than falling back to built-in defaults: the runner and the
    harness both compute the readiness block, and a silent default would let them disagree
    about what "ready" means without anyone noticing.
    """


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
    substantive_count: int = 0
    missing_required: list[str] = field(default_factory=list)
    missing_signals: list[str] = field(default_factory=list)
    message: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "present_types": self.present_types,
            "substantive_count": self.substantive_count,
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

    Two conditions on sources, plus two on signal:
      * the RFP is present (what the client believes they are buying), and
      * at least MIN_SUBSTANTIVE_SOURCES substantive sources exist, so nothing rests on one.
    """
    present_types = sorted({s.source_type for s in sources})
    substantive = [s for s in sources if s.source_type in SUBSTANTIVE_SOURCE_TYPES]
    missing_required = [t for t in REQUIRED_SOURCE_TYPES if t not in present_types]
    too_few = len(substantive) < MIN_SUBSTANTIVE_SOURCES

    corpus = "\n".join(s.text for s in sources)
    missing_signals = []
    if not _has_signal(BUDGET_SIGNAL_PATTERNS, corpus):
        missing_signals.append("budget")
    if not _has_signal(TIMELINE_SIGNAL_PATTERNS, corpus):
        missing_signals.append("timeline")

    if not missing_required and not too_few and not missing_signals:
        return ReadinessGateResult(
            ok=True,
            present_types=present_types,
            substantive_count=len(substantive),
            message=(
                f"input sufficient — {len(sources)} source(s), {len(substantive)} substantive: "
                f"{', '.join(present_types)}"
            ),
        )

    asks = []
    if missing_required:
        asks.append("missing source(s): " + ", ".join(missing_required))
    if too_few:
        asks.append(
            f"only {len(substantive)} substantive source(s) — need {MIN_SUBSTANTIVE_SOURCES} "
            f"from {list(SUBSTANTIVE_SOURCE_TYPES)} (background does not count)"
        )
    if missing_signals:
        asks.append("no " + " or ".join(missing_signals) + " signal in any source")
    return ReadinessGateResult(
        ok=False,
        present_types=present_types,
        substantive_count=len(substantive),
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


#: Markdown emphasis / heading markers. They are formatting, not content: a citation to the
#: bolded phrase `**πρώτη εβδομάδα**` quoted as `πρώτη εβδομάδα` is a *correct* citation, so the
#: match must be on content, not markup. Stripping these from both sides removes that class of
#: false positive while leaving fabrication detection intact — an invented span still fails to
#: match after stripping, because stripping only removes markers, never content.
_MARKDOWN_MARKERS = re.compile(r"(\*+|_+|`+|^#+\s*)", re.MULTILINE)


def _normalise(text: str) -> str:
    """Normalise for citation matching: drop markdown markers, then collapse whitespace.

    Two independent sources of spurious mismatch are handled here: a line wrap inside the
    source (whitespace), and markdown emphasis the model quotes without (bold/italic markers).
    Both are formatting; neither changes what the citation points at.
    """
    return " ".join(_MARKDOWN_MARKERS.sub("", text).split())


def verify_citations(extract: dict, source_text: str) -> list[str]:
    """Every `location` and `anchor` must occur in the source, matched on content not markup.

    SOURCES.md rule 2 says a value without a citation does not exist. This is the other half
    of that rule: a citation that cannot be found in the source is worse than a missing one,
    because it survives review by *looking* verified. PRD R2 names this exact failure — "a
    confident citation to garbage" — as the dangerous one, so it is checked in code rather
    than left to the agent's self-check. Matching is markdown-insensitive (see `_normalise`):
    quoting the bolded content of a source span is a real citation, not a fabricated one.
    """
    haystack = _normalise(source_text)
    violations: list[str] = []
    for fieldname in BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname, []) or []):
            for key in ("location", "anchor"):
                needle = _normalise(item.get(key) or "")
                if needle and needle not in haystack:
                    violations.append(
                        f"{fieldname}[{idx}]: {key} {needle!r} does not occur in the source — "
                        f"citations are copied from the document, never constructed"
                    )
    return violations


def _extract_items(extract: dict):
    """(path, item) for every evidence-bearing item in an extract — the 7 brief fields plus
    both sides of each internal conflict. Internal-conflict items matter because synthesis is
    allowed to surface them (their anchors are in its known-anchor set), so every item-level
    discipline that applies to a field item applies to them identically."""
    for fieldname in BRIEF_FIELDS:
        for idx, item in enumerate(extract.get(fieldname, []) or []):
            yield f"{fieldname}[{idx}]", item
    for idx, conflict in enumerate(extract.get("internal_conflicts") or []):
        for side in ("value_a", "value_b"):
            item = conflict.get(side)
            if item:
                yield f"internal_conflicts[{idx}].{side}", item


def verify_internal_conflict_citations(extract: dict, source_text: str) -> list[str]:
    """Citations inside `internal_conflicts` must resolve in the source too.

    The shared `verify_citations` above covers the 7 brief fields and is imported by the frozen
    harness (T1.3), so it stays untouched; this runner-side gate closes the side door. The door
    exists because internal-conflict anchors were deliberately admitted into synthesis's
    known-anchor set (the Tier-3 §7 fix) — widening what synthesis may cite without widening
    what extraction verifies would let a fabricated anchor ride a conflict record straight into
    the brief. The runner may be stricter than the grader; never the reverse.
    """
    haystack = _normalise(source_text)
    violations: list[str] = []
    for idx, conflict in enumerate(extract.get("internal_conflicts") or []):
        for side in ("value_a", "value_b"):
            item = conflict.get(side) or {}
            for key in ("location", "anchor"):
                needle = _normalise(item.get(key) or "")
                if needle and needle not in haystack:
                    violations.append(
                        f"internal_conflicts[{idx}].{side}: {key} {needle!r} does not occur in the "
                        f"source — citations are copied from the document, never constructed"
                    )
    return violations


def find_unsourced_glossary_terms(extract: dict, source_text: str, glossary: dict) -> list[str]:
    """Catch silent repair and silent translation of protected terms.

    Glossary terms are `keep_latin`: they survive character-exact wherever they genuinely
    appear. So a glossary term sitting in Latin script inside an extracted `value` while the
    source never writes it in Latin means the agent produced it — by "fixing" a script-collapsed
    token (SOURCES.md rule G) or by translating (rule 5). Both are forbidden, and both are
    invisible to a schema check, because the output is perfectly well-formed.

    Matching is word-bounded on the value side (short terms like "OOH" must not fire inside an
    unrelated word) and substring on the source side (any genuine Latin occurrence, however
    embedded, clears the term). Scope includes internal-conflict items — a repair is no more
    acceptable for hiding inside a conflict record. Driven entirely by the client's own
    glossary, so it generalises to any client without the pipeline knowing anything about a
    particular document.
    """
    haystack = source_text.lower()
    terms = [
        t["term"]
        for t in (glossary.get("terms") or [])
        if t.get("rule") == "keep_latin" and t.get("term")
    ]
    violations: list[str] = []
    for path, item in _extract_items(extract):
        value = (item.get("value") or "").lower()
        for term in terms:
            lowered = term.lower()
            in_value = re.search(rf"(?<!\w){re.escape(lowered)}(?!\w)", value)
            if in_value and lowered not in haystack:
                violations.append(
                    f"{path}: value contains glossary term {term!r}, which never "
                    f"appears in Latin script in the source. If the source renders it collapsed "
                    f"into Greek script, keep the source's characters and add an extraction_note "
                    f"proposing the glossary match (SOURCES.md rule G); never repair in place."
                )
    return violations


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


def load_readiness_policy(path: Optional[Path] = None) -> dict:
    """Load the agency readiness thresholds, validating them properly.

    Keys prefixed with `_` are documentation for whoever edits the file and are ignored.
    A missing or out-of-range value raises rather than defaulting — see `ConfigError`.
    """
    path = Path(path) if path else READINESS_POLICY_PATH
    if not path.is_file():
        raise ConfigError(f"readiness policy not found at {path}. The pipeline will not guess thresholds.")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"{path}: not valid JSON — {exc}") from exc

    min_fields = policy.get("min_fields_with_evidence")
    max_share = policy.get("max_low_confidence_share")
    if not isinstance(min_fields, int) or isinstance(min_fields, bool) or not 0 <= min_fields <= len(BRIEF_FIELDS):
        raise ConfigError(
            f"{path}: min_fields_with_evidence must be an integer 0–{len(BRIEF_FIELDS)}, got {min_fields!r}"
        )
    if not isinstance(max_share, (int, float)) or isinstance(max_share, bool) or not 0 <= max_share <= 1:
        raise ConfigError(f"{path}: max_low_confidence_share must be a number 0–1, got {max_share!r}")

    return {"min_fields_with_evidence": min_fields, "max_low_confidence_share": float(max_share)}


def compute_readiness_block(brief: dict, policy: Optional[dict] = None) -> dict:
    """Compute `brief.readiness` deterministically from the brief's own contents.

    SYNTHESIS.md rule 8 forbids the model from populating this block, and the Tier-2 DoD
    has the harness recompute it and compare. So this function is the single definition of
    the value, called once by the runner and once by the harness — same input, same output,
    no model in the path. Thresholds come from `config/readiness_policy.json` so both callers
    read the same agency policy.
    """
    policy = policy or load_readiness_policy()
    entries = [e for f in BRIEF_FIELDS for e in (brief.get(f) or [])]
    evidenced_fields = sum(
        1
        for f in BRIEF_FIELDS
        if any((e.get("evidence") or []) for e in (brief.get(f) or []))
    )
    low = sum(1 for e in entries if e.get("confidence") == "low")
    share = round(low / len(entries), READINESS_SHARE_PRECISION) if entries else 0.0

    ready = (
        evidenced_fields >= policy["min_fields_with_evidence"]
        and share <= policy["max_low_confidence_share"]
    )
    return {
        "fields_with_evidence": evidenced_fields,
        "low_confidence_share": share,
        "open_question_count": len(brief.get("open_questions") or []),
        "verdict": "ready_for_review" if ready else "thin_input_return_to_client",
    }
