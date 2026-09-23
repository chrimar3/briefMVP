"""Approval binding policy: when a human approval of a brief still counts.

An approval (`approval.json`) is bound to the run's content fingerprint
(`revisions.fingerprint`). It is current only while nothing it vouched for changed: no
withdrawal, no unreviewed clarification reply, unchanged inputs and evidence copies, the same
fingerprint, and — for agency-managed runs — a current human language/source attestation.

This policy used to live in `pipeline/revisions.py`, which made the low-level utility import
the Tier 5–7 modules it serves. It now sits one layer up: this module imports revisions,
release_control and quality; revisions imports none of them.
"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Union

from pipeline import quality, release_control, revisions

PathLike = Union[str, Path]


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


def prepare_run(run_dir: PathLike, paths: Mapping[str, PathLike], stage: str) -> None:
    """`revisions.prepare_run` with this module's approval check bound for the creative stage."""
    revisions.prepare_run(run_dir, paths, stage, require_approval=require_current_approval)
