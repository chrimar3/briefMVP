"""Publish finished review pages to the shareable `reviews/` shelf.

Distribution for the pilot is deliberately infrastructure-free (mission doc §8, owner
decision 2026-07-30): account leads get the pages either as an emailed file or through a
synced shared folder. This module keeps that folder tidy — after a COMPLETED run, the
runner copies both self-contained pages here under names a non-technical reader can
recognise at a glance:

    reviews/meltemi-beverages-2026-07-24-brief.html
    reviews/meltemi-beverages-2026-07-24-run.html

Rules, deliberately boring:
- Only completed runs publish (a brief page must exist). Refused or partial runs stay
  in `runs/` for the operator — the shelf is the account-lead surface.
- Same client + same date republished → overwrite. The shelf always shows the latest
  state of that day's brief; history lives in `runs/`, not here.
- Pure copy of already-generated pages. Nothing is rendered here, so every guarantee
  the pages carry (deterministic view, no cost/model info) carries over verbatim.

Usage:
    python3 pipeline/publish.py runs/<id>       # copy that run's pages onto the shelf
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python3 pipeline/publish.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import ReviewInputError, _load_brief_meta  # noqa: E402

#: The shelf lives beside `runs/` at the repo root unless a caller says otherwise.
DEFAULT_REVIEWS_DIR = Path(__file__).resolve().parent.parent / "reviews"

#: page filename in the run dir → suffix on the shelf
_PAGES = (("brief_review.html", "brief"), ("run_review.html", "run"))


def _slug(value: str) -> str:
    """Filesystem-safe kebab slug of an identifier; empty input stays empty."""
    return re.sub(r"[^a-z0-9]+", "-", str(value).lower()).strip("-")


def publish_run(run_dir, reviews_dir=None) -> list[Path]:
    """Copy a completed run's pages onto the shelf; return the published paths.

    A run without a brief page publishes nothing (empty list) — that is the normal
    case for refusals and partial stages, not an error.
    """
    run_dir = Path(run_dir)
    if not (run_dir / "brief_review.html").is_file():
        return []
    meta = _load_brief_meta(run_dir)
    client = _slug(meta.get("client_id", "")) or _slug(run_dir.name) or "client"
    date = str(meta.get("created_ts", ""))[:10] or "undated"
    reviews_dir = Path(reviews_dir) if reviews_dir else DEFAULT_REVIEWS_DIR
    reviews_dir.mkdir(parents=True, exist_ok=True)
    published = []
    for page_name, suffix in _PAGES:
        source = run_dir / page_name
        if not source.is_file():
            continue
        target = reviews_dir / f"{client}-{date}-{suffix}.html"
        shutil.copyfile(source, target)
        published.append(target)
    return published


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Copy a completed run's review pages onto the shareable reviews/ shelf."
    )
    parser.add_argument("run_dir", help="run directory containing brief_review.html")
    args = parser.parse_args(argv)
    try:
        published = publish_run(args.run_dir)
    except ReviewInputError as exc:
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
