"""Content-bound review and safe reuse; no model calls or implicit human decisions."""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def input_state(paths):
    return {key: {"path": str(Path(path).resolve()), "sha256": file_hash(path)}
            for key, path in sorted(paths.items())}


def verify_inputs(run_dir):
    state = load(Path(run_dir) / "input_snapshot.json", {})
    recorded_sources = {Path(item["path"]).resolve() for key, item in state.items() if key.startswith("source:")}
    for directory in {p.parent for p in recorded_sources}:
        current_sources = {p.resolve() for p in directory.glob("*.md") if p.is_file()}
        if current_sources != {p for p in recorded_sources if p.parent == directory}:
            raise ValueError("The source document set changed; use a new run with all current sources.")
    for key, item in state.items():
        if not Path(item["path"]).is_file() or file_hash(item["path"]) != item["sha256"]:
            raise ValueError(f"Input {key} changed; use a new run with current sources.")


def fingerprint(run_dir):
    run_dir = Path(run_dir)
    names = ["brief.json", "brief_el.md", "brief_en.md", "input_snapshot.json",
             "agency_inputs.json", "clarifications.json", "coverage_decisions.json"]
    files = [run_dir / n for n in names] + sorted((run_dir / "extracts").glob("*.json"))
    return digest({str(p.relative_to(run_dir)): file_hash(p) for p in files if p.is_file()})


def require_current_approval(run_dir):
    run_dir = Path(run_dir)
    verify_inputs(run_dir)
    approval = load(run_dir / "approval.json", {})
    if not approval.get("actor") or approval.get("fingerprint") != fingerprint(run_dir):
        raise ValueError("Missing or stale human approval; review and approve the current revision.")
    if (run_dir / "agency_inputs.json").exists():
        from pipeline.quality import field_review_checklist
        path = run_dir / "language_review.json"
        attestation = load(path, {})
        if (not path.is_file() or approval.get("language_review_sha256") != file_hash(path)
                or attestation.get("fingerprint") != fingerprint(run_dir)
                or not attestation.get("actor")
                or not all(attestation.get("checks", {}).get(k) is True for k in field_review_checklist())):
            raise ValueError("Missing, withdrawn or stale human language/source review; approve again after review")


def archive(run_dir, names, copy_only=False):
    run_dir = Path(run_dir)
    files = [run_dir / n for n in names if (run_dir / n).exists()]
    if not files:
        return
    target = run_dir / "history" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid4().hex[:8])
    target.mkdir(parents=True)
    for path in files:
        if copy_only:
            if path.is_dir():
                shutil.copytree(path, target / path.name)
            else:
                shutil.copy2(path, target / path.name)
        else:
            shutil.move(str(path), str(target / path.name))


def prepare_run(run_dir, paths, stage):
    """Refuse changed-input reuse. Archive invalidated products before a leg rerun.

    Legacy runs without a snapshot remain usable for the original demo; they cannot
    receive agency approval until initialized and explicitly reviewed.
    """
    run_dir = Path(run_dir)
    state = input_state(paths)
    previous = load(run_dir / "input_snapshot.json")
    if previous is not None:
        verify_inputs(run_dir)
    if previous is not None and (any(previous.get(k) != v for k, v in state.items())
            or {k for k in previous if k.startswith("source:")} != {k for k in state if k.startswith("source:")}):
        raise ValueError("Inputs/configuration changed; create a new run instead of reusing stale artifacts.")
    # A legacy artifact was not necessarily made from today's inputs: never backfill proof.
    if previous is None and not (run_dir / "brief.json").exists() and not (run_dir / "extracts").exists():
        write_json(run_dir / "input_snapshot.json", state)
    if stage == "creative":
        if (run_dir / "agency_inputs.json").exists():
            require_current_approval(run_dir)
        return
    downstream = ["approval.json", "language_review.json", "agency_audit.json", "creative", "brief_review.html", "run_review.html",
                  "brief_el.html", "brief_en.html", "brief_el.md", "brief_en.md"]
    if stage in ("synthesis", "extraction", "full"):
        downstream += ["brief.json", "conflict_candidates.json"]
    if stage == "extraction":
        # Keep unaffected source extracts for --source resumes, but preserve every
        # original before the extractor can overwrite its selected output path.
        archive(run_dir, ["extracts", "fidelity"], copy_only=True)
    if stage == "full":
        downstream += ["classification.json", "extracts", "fidelity"]
    archive(run_dir, downstream)


def changes(before, after):
    """Field-level content comparison, useful before approving a changed brief."""
    return {key: {"before": before.get(key), "after": after.get(key)}
            for key in sorted(set(before) | set(after)) if before.get(key) != after.get(key)}
