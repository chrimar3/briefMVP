"""The reviews/ shelf is the pilot's distribution surface: completed runs publish their
two pages under recognisable names; refusals and partial runs never reach it. Publishing
is a pure file copy — every guarantee the pages carry (deterministic view, no cost/model
info) must carry over byte-identically. Deterministic, zero model calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import publish


def _run_dir(tmp_path, *, client="acme_soda", created="2026-07-30T10:00:00",
             with_brief_page=True, with_run_page=True) -> Path:
    run_dir = tmp_path / "run"
    run_dir.mkdir(exist_ok=True)
    (run_dir / "brief.json").write_text(
        json.dumps({"meta": {"client_id": client, "created_ts": created}}),
        encoding="utf-8",
    )
    if with_brief_page:
        (run_dir / "brief_review.html").write_text("<p>brief page</p>", encoding="utf-8")
    if with_run_page:
        (run_dir / "run_review.html").write_text("<p>run page</p>", encoding="utf-8")
    return run_dir


def test_completed_run_publishes_both_pages_under_recognisable_names(tmp_path):
    shelf = tmp_path / "shelf"
    published = publish.publish_run(_run_dir(tmp_path), reviews_dir=shelf)
    assert [p.name for p in published] == [
        "acme-soda-2026-07-30-brief.html",
        "acme-soda-2026-07-30-run.html",
    ]
    assert (shelf / "acme-soda-2026-07-30-brief.html").read_text() == "<p>brief page</p>"
    assert (shelf / "acme-soda-2026-07-30-run.html").read_text() == "<p>run page</p>"


def test_runs_without_a_brief_page_never_reach_the_shelf(tmp_path):
    """Refused and partial runs are operator material — the shelf is the account-lead
    surface, so publishing them would put half-built work in front of leads."""
    shelf = tmp_path / "shelf"
    run_dir = _run_dir(tmp_path, with_brief_page=False)
    assert publish.publish_run(run_dir, reviews_dir=shelf) == []
    assert not shelf.exists()


def test_awkward_client_ids_become_safe_slugs(tmp_path):
    shelf = tmp_path / "shelf"
    run_dir = _run_dir(tmp_path, client="Acme Söda GmbH & Co.!")
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert published[0].name == "acme-s-da-gmbh-co-2026-07-30-brief.html"


def test_republishing_the_same_day_overwrites_latest_wins(tmp_path):
    """The shelf shows the latest state of that day's brief; history lives in runs/."""
    shelf = tmp_path / "shelf"
    run_dir = _run_dir(tmp_path)
    publish.publish_run(run_dir, reviews_dir=shelf)
    (run_dir / "brief_review.html").write_text("<p>signed-off version</p>", encoding="utf-8")
    publish.publish_run(run_dir, reviews_dir=shelf)
    assert (shelf / "acme-soda-2026-07-30-brief.html").read_text() == "<p>signed-off version</p>"
    assert len(list(shelf.glob("*.html"))) == 2


def test_missing_meta_falls_back_to_the_run_dir_name(tmp_path):
    shelf = tmp_path / "shelf"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief_review.html").write_text("<p>x</p>", encoding="utf-8")
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert published[0].name == "run-undated-brief.html"


def test_cli_prints_shelf_paths_and_fails_legibly_when_empty(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(publish, "DEFAULT_REVIEWS_DIR", tmp_path / "shelf")
    run_dir = _run_dir(tmp_path)
    assert publish.main([str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert "acme-soda-2026-07-30-brief.html" in out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert publish.main([str(empty)]) == 1
    assert "brief_review.html" in capsys.readouterr().err
