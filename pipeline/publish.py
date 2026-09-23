"""Publish immutable review bundles identified by client, project, date and content.

Repeating the same bundle is idempotent. Different campaigns or changed content
receive distinct paths; existing shared links keep pointing at their original revision.
The legacy demo permits draft review pages; agency-managed runs also verify input
freshness, and signed pages require current content-bound human approval.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional, Union

if __package__ in (None, ""):  # allow `python3 pipeline/publish.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import ReviewInputError, load_brief_meta  # noqa: E402
from pipeline import approval, data_policy, docview, gates, review, revisions  # noqa: E402

#: The shelf lives beside `runs/` at the repo root unless a caller says otherwise.
DEFAULT_REVIEWS_DIR = Path(__file__).resolve().parent.parent / "reviews"

#: run-dir filename → suffix on the shelf. The walkthrough page cross-links the other
#: three by their run-dir names, so its copy gets those hrefs rewritten to shelf names.
_FILES = (
    ("brief_review.html", "brief.html"),
    ("run_review.html", "run.html"),
    ("brief_el.html", "el.html"),
    ("brief_en.html", "en.html"),
    ("brief_el.md", "el.md"),
    ("brief_en.md", "en.md"),
)


def _slug(value: str) -> str:
    """Filesystem-safe kebab slug of an identifier; empty input stays empty."""
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def shelf_prefix(run_dir: Union[str, Path]) -> str:
    """`<client>-<project>-<date>-<content revision>`: the run's immutable name on the shelf."""
    run_dir = Path(run_dir)
    meta = load_brief_meta(run_dir)
    client = _slug(meta.get("client_id", "")) or _slug(run_dir.name) or "client"
    project = _slug(meta.get("project_id", "")) or _slug(run_dir.name) or "project"
    date = _slug(str(meta.get("created_ts", ""))[:10]) or "undated"
    files = [run_dir / name for name, _ in _FILES] + [run_dir / "brief.json"]
    identity = {p.name: revisions.file_hash(p) for p in files if p.is_file()}
    revision = revisions.digest(identity)[:16]
    return f"{client}-{project}-{date}-{revision}"


def require_shelf_allowed(run_dir: Union[str, Path], reviews_dir: Optional[Union[str, Path]] = None) -> None:
    """Refuse (ReviewInputError) to put a run on a shelf inside the repository unless the run's
    RECORDED data class is synthetic (`approval.recorded_data_class`): non-synthetic material
    never writes into the repository (data_policy.check_locations; DATA_PROTECTION.md §6)."""
    shelf = Path(reviews_dir) if reviews_dir else DEFAULT_REVIEWS_DIR
    root = gates.REPO_ROOT.resolve()
    if shelf.resolve() != root and root not in shelf.resolve().parents:
        return
    data_class = approval.recorded_data_class(run_dir)
    if data_class != data_policy.SYNTHETIC:
        raise ReviewInputError(
            f"refused: the reviews shelf lives inside the repository and only runs whose recorded data class is "
            f"synthetic go on it; this run's recorded class is {data_class!r} (no declaration bound to the run, "
            f"or one changed since, counts as non-synthetic)")


def publish_run(run_dir: Union[str, Path], reviews_dir: Optional[Union[str, Path]] = None) -> list[Path]:
    """Refuse non-synthetic runs for an in-repository shelf, take the run lock, then publish the
    run's pages onto the shelf (`publish_locked`)."""
    require_shelf_allowed(run_dir, reviews_dir)
    with revisions.run_lock(run_dir):
        return publish_locked(run_dir, reviews_dir)


def publish_locked(run_dir: Union[str, Path], reviews_dir: Optional[Union[str, Path]] = None) -> list[Path]:
    """Copy a completed run's pages onto the shelf; return the published paths.

    For a caller that already holds the run lock (the runner, while writing its manifest);
    everyone else calls `publish_run`. A run without a brief page publishes nothing (empty
    list) — that is the normal case for refusals and partial stages, not an error.
    """
    run_dir = Path(run_dir)
    if not (run_dir / "brief_review.html").is_file():
        return []
    try:
        revisions.verify_inputs(run_dir)
    except ValueError as exc:
        raise ReviewInputError(str(exc)) from exc
    if (run_dir / "agency_inputs.json").exists():
        try:
            brief = revisions.load(run_dir / "brief.json", {})
            if (run_dir / "brief_review.html").read_text(encoding="utf-8") != review.render_review(brief):
                raise ValueError("Review page differs from canonical brief; regenerate the views")
            for lang in ("el", "en"):
                html = run_dir / f"brief_{lang}.html"
                md = run_dir / f"brief_{lang}.md"
                if html.exists() and (not md.exists() or html.read_text(encoding="utf-8") != docview.render_document(md.read_text(encoding="utf-8"), lang)):
                    raise ValueError("Document view differs from its render; regenerate the views")
            if brief.get("signoff", {}).get("status") == "signed_off":
                approval.require_current_approval(run_dir)
        except ValueError as exc:
            raise ReviewInputError(str(exc)) from exc
    prefix = shelf_prefix(run_dir)
    reviews_dir = Path(reviews_dir) if reviews_dir else DEFAULT_REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)
    shelf_names = {
        name: f"{prefix}-{suffix}"
        for name, suffix in _FILES
        if (run_dir / name).is_file()
    }
    published = []
    for name, shelf_name in shelf_names.items():
        source = run_dir / name
        target = reviews_dir / shelf_name
        if name == "run_review.html":
            # The walkthrough's bottom buttons link its siblings by run-dir name;
            # on the shelf those siblings wear shelf names — rewrite or the buttons die.
            text = source.read_text(encoding="utf-8")
            for sibling, sibling_shelf in shelf_names.items():
                if sibling != name:
                    text = text.replace(f'href="{sibling}"', f'href="{sibling_shelf}"')
            data = text.encode("utf-8")
        else:
            data = source.read_bytes()
        try:
            with target.open("xb") as handle:
                handle.write(data)
        except FileExistsError:
            if target.read_bytes() != data:
                raise ReviewInputError(f"Immutable publication collision: {target}") from None
        published.append(target)
    return published


#: Deprecated private name of `publish_locked`, kept for callers written before it was public.
_publish_locked = publish_locked


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Copy a completed run's review pages onto the shareable reviews/ shelf."
    )
    parser.add_argument("run_dir", help="run directory containing brief_review.html")
    args = parser.parse_args(argv)
    try:
        published = publish_run(args.run_dir)
    except (ReviewInputError, ValueError) as exc:
        print(f"publish: {exc}", file=sys.stderr)
        return 1
    if not published:
        print(
            f"publish: nothing to publish — {args.run_dir} has no brief_review.html "
            "(only completed runs go on the shelf)",
            file=sys.stderr,
        )
        return 1
    for path in published:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
