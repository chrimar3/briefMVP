"""Approval binding policy: when a human approval of a brief still counts.

An approval (`approval.json`) is bound to the run's content fingerprint
(`revisions.fingerprint`). It is current only while nothing it vouched for changed: no
withdrawal, no unreviewed clarification reply, unchanged inputs and evidence copies, the same
fingerprint, and — for agency-managed runs — a current human language/source attestation.

Two further run facts live here because the approval policy depends on them:

* **The recorded data class.** The project's `data_declaration.json` is bound into the run's
  input snapshot when the run is prepared (`prepare_run`) or initialised (`agency init`).
  `recorded_data_class` answers from that recorded, hash-checked, re-validated declaration —
  never from whatever the project folder says today — so a declaration flipped after the run
  cannot unlock the `--solo-rehearsal` waiver, the brief-signoff regime or the reviews shelf.
* **The sign-off regime** that gates the creative stage (`signoff_regime.json`). It is recorded
  explicitly and vouched by the audit log; an unrecorded run gets the strict regime (content-bound
  approval), never a weaker one inferred from which files happen to exist.

This policy used to live in `pipeline/revisions.py`, which made the low-level utility import
the Tier 5–7 modules it serves. It now sits one layer up: this module imports revisions,
release_control, quality and data_policy; revisions imports none of them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Optional, Union

from pipeline import data_policy, quality, release_control, revisions

PathLike = Union[str, Path]

#: Input-snapshot key of the project's data declaration.
DECLARATION_KEY = "data_declaration"

#: The run's recorded sign-off regime for the creative stage.
REGIME_FILE = "signoff_regime.json"
#: Content-bound approval.json plus a current language/source attestation (agency runs).
AGENCY_APPROVAL = "agency_approval"
#: The historical Tier-4 regime: brief.json signoff.status only. Synthetic projects only.
BRIEF_SIGNOFF = "brief_signoff"
REGIMES = (AGENCY_APPROVAL, BRIEF_SIGNOFF)


def require_current_approval(run_dir: PathLike) -> None:
    """Raise ValueError unless the run carries a current, content-bound human approval."""
    run_dir = Path(run_dir)
    release_control.require_not_withdrawn(run_dir)
    if (run_dir / 'question_exchange' / 'proposals').exists():
        # question_exchange sits on top of agency (which imports this module), so it is bound
        # at call time — and only for runs that actually hold clarification proposals.
        from pipeline.question_exchange import pending_proposals
        if pending_proposals(run_dir):
            raise ValueError('Unreviewed clarification replies; review the proposals before approval or release')
    revisions.verify_inputs(run_dir)
    revisions.verify_evidence(run_dir)
    approval = revisions.load(run_dir / "approval.json", {})
    if not approval.get("actor") or approval.get("fingerprint") != revisions.fingerprint(run_dir):
        raise ValueError("Missing or stale human approval; review and approve the current revision.")
    if (run_dir / "agency_inputs.json").exists():
        path = run_dir / "language_review.json"
        attestation = revisions.load(path, {})
        if (not path.is_file() or approval.get("language_review_sha256") != revisions.file_hash(path)
                or attestation.get("fingerprint") != revisions.fingerprint(run_dir)
                or not attestation.get("actor")
                or not all(attestation.get("checks", {}).get(k) is True
                           for k in quality.field_review_checklist())):
            raise ValueError("Missing, withdrawn or stale human language/source review; approve again after review")


# -- the recorded data class -------------------------------------------------------------------


def declaration_for(paths: Mapping[str, PathLike]) -> Optional[Path]:
    """The data declaration of the one project folder the `source:*` inputs come from, or None."""
    folders = {Path(p).resolve().parent for key, p in paths.items() if key.startswith("source:")}
    if len(folders) != 1:
        return None
    path = folders.pop() / data_policy.DECLARATION_FILE
    return path if path.is_file() and not path.is_symlink() else None


def with_declaration(run_dir: PathLike, paths: Mapping[str, PathLike]) -> dict:
    """`paths` plus the project's data declaration, when it can be bound to this run.

    A snapshot recorded before the declaration was bound stays as recorded: adding a key to it
    would read as an input change and strand the run. Such a run has no recorded data class.
    """
    paths = dict(paths)
    declaration = declaration_for(paths)
    if declaration is None or DECLARATION_KEY in paths:
        return paths
    recorded = revisions.load(Path(run_dir) / "input_snapshot.json")
    if recorded is not None and DECLARATION_KEY not in recorded:
        return paths
    paths[DECLARATION_KEY] = declaration
    return paths


def recorded_data_class(run_dir: PathLike) -> Optional[str]:
    """The data class bound to this run, or None when it is not known.

    Read from the declaration recorded in input_snapshot.json: the file must still hash to the
    recorded SHA-256 (a flipped declaration is unknown, not its new value), must be a regular
    file, must pass `data_policy.validate_payload`, and must agree with the class the runner
    recorded in run_manifest.json when there is one. Anything else is None — the safe reading.
    """
    run_dir = Path(run_dir)
    try:
        snapshot = revisions.load(run_dir / "input_snapshot.json", {}) or {}
        manifest = revisions.load(run_dir / "run_manifest.json", {}) or {}
    except revisions.CorruptRecordError:
        return None
    item = snapshot.get(DECLARATION_KEY) if isinstance(snapshot, dict) else None
    if not isinstance(item, dict) or not item.get("path") or not item.get("sha256"):
        return None
    path = Path(item["path"])
    if path.is_symlink() or not path.is_file():
        return None
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        return None
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if data_policy.validate_payload(payload, str(path)):
        return None
    declared = (manifest.get("data_declaration") if isinstance(manifest, dict) else None) or {}
    if isinstance(declared, dict) and "data_class" in declared and declared["data_class"] != payload["data_class"]:
        return None
    return payload["data_class"]


# -- the sign-off regime -------------------------------------------------------------------------


def signoff_regime(run_dir: PathLike) -> str:
    """The run's recorded sign-off regime; AGENCY_APPROVAL (the strict one) when none is recorded.

    A recorded regime must be valid and vouched for by a `signoff_regime_recorded` audit entry
    (its exact bytes); otherwise ValueError. Nothing is inferred from other files' presence.
    """
    run_dir = Path(run_dir)
    path = run_dir / REGIME_FILE
    if not path.exists():
        return AGENCY_APPROVAL
    record = revisions.load(path, {})
    regime = record.get("regime") if isinstance(record, dict) else None
    if regime not in REGIMES:
        raise ValueError(f"{REGIME_FILE}: unknown sign-off regime {regime!r}")
    sha = revisions.file_hash(path)
    try:
        entries = revisions.read_audit_log(run_dir)
    except (ValueError, OSError):
        entries = []
    if not any(e.get("event") == "signoff_regime_recorded" and e.get("record_sha256") == sha for e in entries):
        raise ValueError(f"{REGIME_FILE} is not vouched for by the audit log; the sign-off regime is unknown")
    return regime


def record_regime(run_dir: PathLike, regime: str, actor: str, reason: str) -> dict:
    """Record the run's sign-off regime (audit-logged). The brief-signoff regime is refused for an
    agency-managed or non-synthetic run, and a run never moves from the strict regime to it."""
    run_dir = Path(run_dir)
    if regime not in REGIMES:
        raise ValueError(f"Unknown sign-off regime {regime!r}; use one of {list(REGIMES)}")
    if not isinstance(actor, str) or not actor.strip() or not isinstance(reason, str) or not reason.strip():
        raise ValueError("A named human actor and a reason are required to record the sign-off regime")
    if regime == BRIEF_SIGNOFF:
        if (run_dir / "agency_inputs.json").exists() or (
                (run_dir / REGIME_FILE).exists() and signoff_regime(run_dir) == AGENCY_APPROVAL):
            raise ValueError("An agency-managed run keeps the content-bound approval regime")
        if recorded_data_class(run_dir) != data_policy.SYNTHETIC:
            raise ValueError("The brief-signoff regime is only for runs whose recorded data class is synthetic")
    record = {"regime": regime, "recorded_by": actor, "reason": reason, "at": revisions.timestamp()}
    revisions.write_json(run_dir / REGIME_FILE, record)
    revisions.append_audit(run_dir, "signoff_regime_recorded", actor, record=REGIME_FILE,
                           details={"regime": regime, "reason": reason})
    return record


def require_creative_signoff(run_dir: PathLike) -> str:
    """Raise ValueError unless the run's recorded regime lets the creative stage start; return it.

    AGENCY_APPROVAL: a current content-bound approval (`require_current_approval`). BRIEF_SIGNOFF:
    the caller checks brief.json signoff.status; this adds that the recorded data class is synthetic.
    """
    regime = signoff_regime(run_dir)
    if regime == AGENCY_APPROVAL:
        require_current_approval(run_dir)
    elif recorded_data_class(run_dir) != data_policy.SYNTHETIC:
        raise ValueError("The brief-signoff regime is only for runs whose recorded data class is synthetic")
    return regime


def prepare_run(run_dir: PathLike, paths: Mapping[str, PathLike], stage: str) -> None:
    """`revisions.prepare_run` with the data declaration bound and the creative regime check."""
    revisions.prepare_run(run_dir, with_declaration(run_dir, paths), stage,
                          require_approval=require_creative_signoff)
