"""Retention inventory and purge: find every copy of a source, delete on instruction, leave a tombstone.

A run multiplies its inputs: `evidence/` keeps hash-named byte copies of every source, and
`history/` keeps every superseded artifact (renders, briefs, extracts) that quotes them;
release packages sit wherever the operator created them. A pilot-end deletion or an erasure
request needs to know where all of that is. Deterministic, local, no model calls:

    python3 -m pipeline.retention inventory --runs /pilot/runs
    python3 -m pipeline.retention purge --source-sha <sha256> --runs /pilot/runs --actor NAME --reason TEXT
    python3 -m pipeline.retention purge --run /pilot/runs/<run-id> --actor NAME --reason TEXT

`inventory` lists, per source SHA-256, every byte-identical copy (evidence/, history/, the
read-only staged copies agents read in `<run>/inputs/`, release packages recorded in
`releases.json`), the per-source derivatives (fidelity annotations,
extracts, verifier reports) and the run-level artifacts that quote all sources (brief, renders,
review pages); plus each run's personal-data-bearing records and the `claude -p` session IDs
the run recorded (those transcripts live in the operator's CLI profile, outside the run).

`purge --source-sha` deletes the byte-identical copies and that source's per-source
derivatives; run-level artifacts that still quote the source are listed in the tombstone as
residual, because only `purge --run` can remove them without leaving a broken run.
`purge --run` deletes the whole run directory. Release packages are listed, never deleted by
`--run`: they are delivered material and follow the delivery retention rule
(docs/pilot/DATA_PROTECTION.md §6). The run's hash-chained `audit_log.jsonl` is never deleted
silently: `purge --source-sha` never touches it, and `purge --run` writes an audit-log tombstone
into the purge record first (its SHA-256, entry count, chain head, events by type and whether
the chain verified), so the deletion of a decision trail is itself on record.

Every purge writes a tombstone (what, when, who, why; hashes of what was deleted, never its
content) to `retention_tombstones.jsonl` beside the purged runs. Committed evidence (files
tracked by git in this repository) is never deleted unless `--include-committed` is passed
AND the committed directory is itself one of the directories named on the command line.
`--dry-run` reports without deleting or writing anything.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import gates, revisions

TOMBSTONE_FILE = "retention_tombstones.jsonl"
#: The run's staged, read-only input copies (pipeline/runner.py STAGED_INPUTS_DIR).
STAGED_INPUTS_DIR = "inputs"
SHA_RE = re.compile(r"[0-9a-f]{64}")

#: Files that mark a directory as a run directory.
RUN_MARKERS = ("run_manifest.json", "evidence_index.json", "input_snapshot.json", "brief.json")

#: Run-level artifacts that quote every source (and carry names of speakers/authors).
RUN_LEVEL_DERIVED = ("brief.json", "brief_el.md", "brief_en.md", "brief_el.html", "brief_en.html",
                     "brief_review.html", "run_review.html", "conflict_candidates.json", "classification.json",
                     "agency_audit.json", "agency_audit.md", "handover.json", "creative", "creative_versions",
                     "question_exchange")

#: Governance and effort records: personal data about agency staff (names, minutes, decisions).
PERSONAL_RECORDS = ("approval.json", "language_review.json", "creative_draft.json", "creative_approval.json",
                    "amendments.json", "clarifications.json", "coverage_decisions.json", "releases.json",
                    "approval_withdrawals.json", "effort.json", "agency_inputs.json", "revision_lineage.json",
                    "audit_log.jsonl")


class RetentionError(ValueError):
    """A retention request that cannot be executed as asked."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 16), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def is_run_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and any((path / m).is_file() for m in RUN_MARKERS)


def find_runs(roots: Iterable[Path]) -> list:
    """Each root is a run directory, or a folder whose immediate children are run directories."""
    found = []
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            raise RetentionError(f"{root}: not a directory")
        if is_run_dir(root):
            found.append(root.resolve())
            continue
        found.extend(child.resolve() for child in sorted(root.iterdir()) if is_run_dir(child))
    return sorted(dict.fromkeys(found))


def _files(directory: Path) -> list:
    """Regular files under a directory, without following symlinks."""
    out = []
    for dirpath, dirnames, filenames in os.walk(directory, followlinks=False):
        for name in filenames:
            path = Path(dirpath) / name
            if path.is_file() and not path.is_symlink():
                out.append(path)
    return sorted(out)


def run_sources(run: Path) -> dict:
    """Known sources of a run: {sha256: {"source_ids": [...], "originals": [...]}}."""
    sources: dict = {}
    for record_name in ("evidence_index.json", "input_snapshot.json"):
        for key, item in (_load(run / record_name, {}) or {}).items():
            if not key.startswith("source:") or not isinstance(item, dict):
                continue
            sha = item.get("sha256")
            if not isinstance(sha, str) or not SHA_RE.fullmatch(sha):
                continue
            entry = sources.setdefault(sha, {"source_ids": [], "originals": []})
            sid = key.split(":", 1)[1]
            if sid not in entry["source_ids"]:
                entry["source_ids"].append(sid)
            original = item.get("original") or item.get("path")
            if original and original not in entry["originals"]:
                entry["originals"].append(original)
    if not sources:
        sources = _legacy_sources(run)
    return sources


def _legacy_sources(run: Path) -> dict:
    """Runs from before input snapshots: identity from the manifest plus the CURRENT original.

    The hash is of today's file in the recorded project folder, which may differ from the
    bytes the run used; each entry says so (`identity: legacy_manifest`).
    """
    manifest = _load(run / "run_manifest.json", {}) or {}
    project = manifest.get("project_dir")
    wanted = {s.get("source_id") for s in manifest.get("sources") or [] if isinstance(s, dict)}
    if not project or not wanted:
        return {}
    candidates = [Path(project)] if Path(project).is_absolute() else [Path.cwd() / project, gates.REPO_ROOT / project]
    folder = next((c for c in candidates if c.is_dir()), None)
    if folder is None:
        return {}
    try:
        discovered = gates.discover_sources(folder)
    except gates.GateError:
        return {}
    sources = {}
    for source in discovered:
        if source.source_id in wanted:
            sha = sha256_file(source.path)
            entry = sources.setdefault(sha, {"source_ids": [], "originals": [], "identity": "legacy_manifest"})
            entry["source_ids"].append(source.source_id)
            entry["originals"].append(str(Path(source.path).resolve()))
    return sources


def release_packages(run: Path) -> list:
    """Package directories recorded by `delivery release` for this run."""
    out = []
    for item in _load(run / "releases.json", []) or []:
        if isinstance(item, dict) and item.get("path"):
            out.append(Path(item["path"]))
    return out


def session_ids(run: Path) -> list:
    """`claude -p` session IDs recorded in the run's artifacts (transcripts live in the CLI profile)."""
    found = set()

    def walk(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                if key == "session_id" and isinstance(inner, str) and inner:
                    found.add(inner)
                else:
                    walk(inner)
        elif isinstance(value, list):
            for inner in value:
                walk(inner)

    for path in [run / "run_manifest.json"] + sorted((run / "diagnostics").glob("*.json*")):
        if path.suffix == ".jsonl" and path.is_file():
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    walk(json.loads(line))
                except ValueError:
                    continue
        else:
            walk(_load(path, {}))
    return sorted(found)


def _per_source_derivatives(run: Path, source_ids: Iterable[str]) -> list:
    out = []
    for sid in source_ids:
        for pattern in (f"fidelity/{sid}.*", f"extracts/{sid}.json", f"verification/{sid}.*",
                        f"history/*/fidelity/{sid}.*", f"history/*/extracts/{sid}.json",
                        f"history/*/verification/{sid}.*"):
            out.extend(p for p in run.glob(pattern) if p.is_file() and not p.is_symlink())
    return sorted(dict.fromkeys(out))


def _run_level_derived(run: Path) -> list:
    out = []
    for name in RUN_LEVEL_DERIVED:
        path = run / name
        if path.exists() and not path.is_symlink():
            out.append(path)
    history = run / "history"
    if history.is_dir():
        out.extend(p for p in sorted(history.glob("*/*")) if p.name in RUN_LEVEL_DERIVED)
    return out


def _tracked(repo_root: Path = gates.REPO_ROOT) -> Optional[set]:
    """Resolved paths git tracks in this repository; None when git cannot answer."""
    try:
        result = subprocess.run(["git", "-C", str(repo_root), "ls-files", "-z"], capture_output=True,
                                timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    root = Path(repo_root).resolve()
    return {(root / name).resolve() for name in result.stdout.decode("utf-8", "replace").split("\0") if name}


class _Protection:
    """Committed evidence guard. Without git, everything inside the repository counts as committed."""

    def __init__(self, repo_root: Path = gates.REPO_ROOT):
        self.repo_root = Path(repo_root).resolve()
        self.tracked = _tracked(self.repo_root)

    def is_committed(self, path: Path) -> bool:
        path = Path(path).resolve()
        if self.tracked is None:
            return self.repo_root == path or self.repo_root in path.parents
        if path.is_dir():
            return any(p == path or path in p.parents for p in self.tracked)
        return path in self.tracked


def inventory(roots: Iterable[Path]) -> dict:
    """Every copy of every known source across the runs under `roots`, with hashes."""
    runs = find_runs(roots)
    by_sha: dict = {}
    run_reports = []
    for run in runs:
        sources = run_sources(run)
        files = _files(run)
        hashes = {path: sha256_file(path) for path in files}
        packages = release_packages(run)
        package_files = []
        for package in packages:
            if package.is_dir() and not package.is_symlink():
                package_files.extend(_files(package))
        for path in package_files:
            hashes[path] = sha256_file(path)
        for sha, meta in sources.items():
            entry = by_sha.setdefault(sha, {"sha256": sha, "source_ids": [], "originals": [], "copies": [],
                                            "per_source_derivatives": [], "run_level_derived": []})
            for sid in meta["source_ids"]:
                if sid not in entry["source_ids"]:
                    entry["source_ids"].append(sid)
            for original in meta["originals"]:
                if original not in entry["originals"]:
                    entry["originals"].append(original)
            if meta.get("identity"):
                entry["identity"] = meta["identity"]
            for path, digest in sorted(hashes.items()):
                if digest == sha:
                    area = "package" if path in package_files else _area(path.relative_to(run))
                    entry["copies"].append({"path": str(path), "area": area, "run": str(run)})
            entry["per_source_derivatives"].extend(
                {"path": str(p), "sha256": hashes.get(p) or sha256_file(p), "run": str(run)}
                for p in _per_source_derivatives(run, meta["source_ids"]))
            entry["run_level_derived"].extend(str(p) for p in _run_level_derived(run))
        run_reports.append({
            "run": str(run),
            "sources": sorted(sources),
            "file_count": len(files),
            "personal_records": [name for name in PERSONAL_RECORDS if (run / name).exists()],
            "staged_inputs": [{"path": str(p), "sha256": hashes[p]} for p in files
                              if p.relative_to(run).parts[0] == STAGED_INPUTS_DIR],
            "release_packages": [{"path": str(p), "exists": p.is_dir()} for p in packages],
            "cli_session_ids": session_ids(run),
        })
    for entry in by_sha.values():
        entry["originals_present"] = [o for o in entry["originals"] if Path(o).is_file()]
    return {
        "generated_at": _now(),
        "roots": [str(Path(r).resolve()) for r in roots],
        "run_count": len(runs),
        "sources": sorted(by_sha.values(), key=lambda e: (e["source_ids"], e["sha256"])),
        "runs": run_reports,
        "not_covered": [
            "Original project folders are listed (originals_present) but never deleted by this tool.",
            "claude -p session transcripts in the operator's CLI profile: listed by session ID only; "
            "delete them there (docs/pilot/DATA_PROTECTION.md §6).",
            "Copies outside the scanned roots (downloads, e-mail, shared drives) are invisible to this tool.",
        ],
    }


def _area(relative: Path) -> str:
    """Where a byte copy sits inside a run: history, evidence, the staged inputs, or the run itself."""
    if "history" in relative.parts:
        return "history"
    return {"evidence": "evidence", STAGED_INPUTS_DIR: "inputs"}.get(relative.parts[0], "run")


def audit_log_tombstone(run: Path) -> Optional[dict]:
    """What a purge records about the run's audit log before deleting it; None if there is none.

    Hashes and counts only (the entries carry staff names): enough to prove later that a chain of
    N decisions with this head existed and was deleted by this purge, and whether it verified.
    """
    path = Path(run) / revisions.AUDIT_LOG
    if not path.is_file() or path.is_symlink():
        return None
    lines = [line for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    events: dict = {}
    for line in lines:
        try:
            event = json.loads(line).get("event", "?")
        except (ValueError, AttributeError):
            event = "unreadable"
        events[event] = events.get(event, 0) + 1
    problems = revisions.verify_audit_log(run)
    return {"path": str(path), "sha256": sha256_file(path), "entries": len(lines),
            "chain_head_sha256": hashlib.sha256(lines[-1].encode("utf-8")).hexdigest() if lines else None,
            "events": dict(sorted(events.items())), "verified_intact": not problems,
            "verification_problems": problems}


def _delete(path: Path) -> dict:
    record = {"path": str(path)}
    if path.is_dir() and not path.is_symlink():
        record.update(kind="directory", file_count=len(_files(path)))
        shutil.rmtree(path)
    else:
        record.update(kind="file", sha256=sha256_file(path), bytes=path.stat().st_size)
        path.unlink()
    return record


def _plan_record(path: Path) -> dict:
    if path.is_dir():
        return {"path": str(path), "kind": "directory", "file_count": len(_files(path))}
    return {"path": str(path), "kind": "file", "sha256": sha256_file(path), "bytes": path.stat().st_size}


def _guard(targets: list, named_dirs: list, include_committed: bool, protection: _Protection):
    """Split targets into deletable and protected (committed evidence not explicitly named)."""
    named = [Path(d).resolve() for d in named_dirs]
    allowed, protected = [], []
    for path in targets:
        if protection.is_committed(path):
            explicit = include_committed and any(path == d or d in path.parents for d in named)
            (allowed if explicit else protected).append(path)
        else:
            allowed.append(path)
    return allowed, protected


def _write_tombstone(location: Path, record: dict) -> Path:
    path = Path(location) / TOMBSTONE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def _require_attribution(actor: str, reason: str):
    if not (actor or "").strip() or not (reason or "").strip():
        raise RetentionError("A named actor and a reason are required for every purge")


def purge_source(sha: str, roots: list, *, actor: str, reason: str, dry_run: bool = False,
                 include_committed: bool = False, protection: Optional[_Protection] = None,
                 tombstone_dir: Optional[Path] = None) -> dict:
    """Delete byte copies and per-source derivatives of one source across the runs under `roots`."""
    _require_attribution(actor, reason)
    if not SHA_RE.fullmatch(sha or ""):
        raise RetentionError("--source-sha must be a lowercase 64-character SHA-256")
    report = inventory(roots)
    entry = next((e for e in report["sources"] if e["sha256"] == sha), None)
    if entry is None:
        raise RetentionError(f"No run under {', '.join(report['roots'])} records a source with SHA-256 {sha}")
    targets = [Path(c["path"]) for c in entry["copies"]] + [Path(d["path"]) for d in entry["per_source_derivatives"]]
    # A decision trail is never a source copy; a purge by source must not be able to delete it.
    targets = sorted(p for p in dict.fromkeys(targets) if p.name != revisions.AUDIT_LOG)
    protection = protection or _Protection()
    allowed, protected = _guard(targets, roots, include_committed, protection)
    residual = sorted(set(entry["run_level_derived"]))
    record = {
        "action": "purge_source", "target": {"source_sha256": sha, "source_ids": entry["source_ids"]},
        "actor": actor, "reason": reason, "at": _now(), "dry_run": dry_run,
        "deleted": [_plan_record(p) for p in allowed] if dry_run else [_delete(p) for p in allowed],
        "skipped_committed": [str(p) for p in protected],
        "residual_run_level_derived": residual,
        "originals_not_deleted": entry["originals_present"],
        "note": "Run-level artifacts still quote this source; purge those runs with --run to remove them. "
                "Hashes identify deleted content for audit; no content is recorded.",
    }
    if not dry_run:
        location = tombstone_dir or Path(report["roots"][0])
        record["tombstone"] = str(_write_tombstone(location, record))
    return record


def purge_run(run: Path, *, actor: str, reason: str, dry_run: bool = False, include_committed: bool = False,
              protection: Optional[_Protection] = None, tombstone_dir: Optional[Path] = None) -> dict:
    """Delete one run directory, leaving a tombstone beside it."""
    _require_attribution(actor, reason)
    run = Path(run)
    if run.is_symlink() or not is_run_dir(run):
        raise RetentionError(f"{run}: not a run directory (no {' / '.join(RUN_MARKERS)})")
    run = run.resolve()
    protection = protection or _Protection()
    allowed, protected = _guard([run], [run], include_committed, protection)
    if protected:
        raise RetentionError(f"{run} is committed evidence; pass --include-committed to purge it explicitly")
    sources = run_sources(run)
    packages = release_packages(run)
    sessions = session_ids(run)
    audit_log = audit_log_tombstone(run)  # recorded BEFORE the directory goes
    record = {
        "action": "purge_run", "target": {"run": str(run), "source_sha256": sorted(sources)},
        "actor": actor, "reason": reason, "at": _now(), "dry_run": dry_run,
        "audit_log_deleted": audit_log,
        "deleted": [_plan_record(run)] if dry_run else [_delete(run)],
        "release_packages_not_deleted": [str(p) for p in packages if p.exists()],
        "cli_session_ids_to_delete_in_operator_profile": sessions,
        "note": "Release packages are delivered material and follow the delivery retention rule; "
                "CLI session transcripts are deleted in the operator's CLI profile. The run's audit log "
                "is deleted with it; audit_log_deleted is its tombstone (hashes and counts, no names).",
    }
    if not dry_run:
        record["tombstone"] = str(_write_tombstone(tombstone_dir or run.parent, record))
    return record


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    inv = commands.add_parser("inventory", help="List every copy of each source under the given runs")
    inv.add_argument("--runs", type=Path, action="append", required=True,
                     help="A run directory, or a folder of run directories (repeatable)")
    inv.add_argument("--output", type=Path, help="Also write the inventory JSON here")
    purge = commands.add_parser("purge", help="Delete copies of one source, or one whole run; writes a tombstone")
    target = purge.add_mutually_exclusive_group(required=True)
    target.add_argument("--source-sha", help="SHA-256 of the source to purge across --runs")
    target.add_argument("--run", type=Path, help="One run directory to delete")
    purge.add_argument("--runs", type=Path, action="append", default=[],
                       help="With --source-sha: run directories or folders of runs to search (repeatable)")
    purge.add_argument("--actor", required=True)
    purge.add_argument("--reason", required=True)
    purge.add_argument("--dry-run", action="store_true")
    purge.add_argument("--include-committed", action="store_true",
                       help="Allow deleting committed evidence inside the directories named on this command line")
    purge.add_argument("--tombstone-dir", type=Path, help="Where retention_tombstones.jsonl is appended")
    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.runs)
            if args.output:
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        elif args.source_sha:
            if not args.runs:
                raise RetentionError("--source-sha needs at least one --runs directory to search")
            result = purge_source(args.source_sha, args.runs, actor=args.actor, reason=args.reason,
                                  dry_run=args.dry_run, include_committed=args.include_committed,
                                  tombstone_dir=args.tombstone_dir)
        else:
            result = purge_run(args.run, actor=args.actor, reason=args.reason, dry_run=args.dry_run,
                               include_committed=args.include_committed, tombstone_dir=args.tombstone_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (RetentionError, OSError) as exc:
        print(f"retention: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
