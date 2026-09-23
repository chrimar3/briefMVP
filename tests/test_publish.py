"""The reviews/ shelf is the pilot's distribution surface: completed runs publish their
two pages under recognisable names; refusals and partial runs never reach it. Publishing
is a pure file copy — every guarantee the pages carry (deterministic view, no cost/model
info) must carry over byte-identically. Deterministic, zero model calls.
"""

from __future__ import annotations

import json
from pathlib import Path

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
    run_dir = _run_dir(tmp_path)
    prefix = publish.shelf_prefix(run_dir)
    assert prefix.startswith("acme-soda-run-2026-07-30-")
    prefix = publish.shelf_prefix(run_dir)
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert [p.name for p in published] == [
        f"{prefix}-brief.html",
        f"{prefix}-run.html",
    ]
    assert (shelf / f"{prefix}-brief.html").read_text() == "<p>brief page</p>"
    assert (shelf / f"{prefix}-run.html").read_text() == "<p>run page</p>"


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
    prefix = publish.shelf_prefix(run_dir)
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert published[0].name.startswith("acme-s-da-gmbh-co-run-2026-07-30-")
    assert published[0].name.startswith(prefix)


def test_shelf_walkthrough_buttons_link_shelf_names(tmp_path):
    """The walkthrough's bottom buttons link siblings by run-dir name; on the shelf the
    siblings wear shelf names, so unrewritten hrefs are dead buttons — the exact bug
    an account lead would hit first."""
    shelf = tmp_path / "shelf"
    run_dir = _run_dir(tmp_path)
    (run_dir / "run_review.html").write_text(
        '<a href="brief_review.html">x</a><a href="brief_el.md">y</a>'
        '<a href="brief_en.md">z</a>',
        encoding="utf-8",
    )
    (run_dir / "brief_el.md").write_text("el", encoding="utf-8")
    (run_dir / "brief_en.md").write_text("en", encoding="utf-8")
    prefix = publish.shelf_prefix(run_dir)
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert {p.name for p in published} == {
        f"{prefix}-brief.html",
        f"{prefix}-run.html",
        f"{prefix}-el.md",
        f"{prefix}-en.md",
    }
    shelf_run = (shelf / f"{prefix}-run.html").read_text(encoding="utf-8")
    assert f'href="{prefix}-brief.html"' in shelf_run
    assert f'href="{prefix}-el.md"' in shelf_run
    assert 'href="brief_review.html"' not in shelf_run
    assert (shelf / f"{prefix}-el.md").read_text(encoding="utf-8") == "el"


def test_republishing_preserves_original_and_same_bundle_is_idempotent(tmp_path):
    shelf = tmp_path / "shelf"
    run_dir = _run_dir(tmp_path)
    first = publish.publish_run(run_dir, reviews_dir=shelf)
    assert publish.publish_run(run_dir, reviews_dir=shelf) == first
    (run_dir / "brief_review.html").write_text("<p>signed-off version</p>", encoding="utf-8")
    second = publish.publish_run(run_dir, reviews_dir=shelf)
    assert first[0].read_text() == "<p>brief page</p>"
    assert second[0].read_text() == "<p>signed-off version</p>"
    assert len(list(shelf.glob("*.html"))) == 4


def test_missing_meta_falls_back_to_the_run_dir_name(tmp_path):
    shelf = tmp_path / "shelf"
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief_review.html").write_text("<p>x</p>", encoding="utf-8")
    prefix = publish.shelf_prefix(run_dir)
    published = publish.publish_run(run_dir, reviews_dir=shelf)
    assert published[0].name.startswith("run-run-undated-")
    assert published[0].name.startswith(prefix)


def test_cli_prints_shelf_paths_and_fails_legibly_when_empty(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(publish, "DEFAULT_REVIEWS_DIR", tmp_path / "shelf")
    run_dir = _run_dir(tmp_path)
    prefix = publish.shelf_prefix(run_dir)
    assert publish.main([str(run_dir)]) == 0
    out = capsys.readouterr().out
    assert f"{prefix}-brief.html" in out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert publish.main([str(empty)]) == 1
    assert "brief_review.html" in capsys.readouterr().err


def test_two_same_day_projects_and_two_revisions_keep_all_pages(tmp_path):
    shelf = tmp_path / 'shelf'
    run_dir = _run_dir(tmp_path)
    first = publish.publish_run(run_dir, reviews_dir=shelf)
    meta = json.loads((run_dir / 'brief.json').read_text())
    meta['meta']['project_id'] = 'second-campaign'
    (run_dir / 'brief.json').write_text(json.dumps(meta))
    second = publish.publish_run(run_dir, reviews_dir=shelf)
    (run_dir / 'brief_review.html').write_text('<p>revised</p>')
    third = publish.publish_run(run_dir, reviews_dir=shelf)
    assert set(first).isdisjoint(second)
    assert set(second).isdisjoint(third)
    assert all(p.exists() for p in first + second + third)
    assert len(list(shelf.glob('*.html'))) == 6
