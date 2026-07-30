"""The Run Review Page walks an account lead through the WHOLE pipeline run — what the
RFP / email thread / transcripts contributed, what the fidelity gate flagged, which
cross-source candidates surfaced, where the run stopped. Same contract as the brief
page: it is a VIEW over the run's artifact files, so it must show what they say and be
unable to add what they do not — in particular the manifest's `attempts` payloads
(run cost + model information) must never reach it. Deterministic, zero model calls.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pytest

from pipeline import review, run_review

REPO = Path(__file__).resolve().parents[1]
STORED_RUNS = ("runs/tier3", "runs/live", "runs/evidence-20260729")

FORBIDDEN = re.compile(r"cost|model|claude|sonnet|haiku|opus", re.IGNORECASE)


def _collect(run: str) -> dict:
    return run_review.collect_run(REPO / run)


def _mini_run_dir(tmp_path, *, with_extract=True) -> Path:
    """Smallest artifact set the collector accepts: a manifest, optionally one extract."""
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    manifest = {
        "run_id": "r_01",
        "pipeline_version": "1.0.0",
        "project_dir": str(tmp_path / "missing-project"),
        "started_ts": "2026-07-30T10:00:00",
        "finished_ts": "2026-07-30T10:05:00",
        "outcome": "complete",
        "exit_code": 0,
        "stage": "full",
        "demo_profile": None,
        "sources": [
            {"source_id": "src_a", "source_type": "rfp", "source_date": "2026-07-01"}
        ],
        "steps": [
            {
                "number": 1,
                "name": "readiness_gate",
                "kind": "deterministic",
                "agent": None,
                "description": "Refuse to draft on insufficient input",
                "status": "pass",
                "attempts": [{"subagent": {"cost_usd": 9.99, "model_ids": ["poisoned"]}}],
            }
        ],
    }
    (run_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    if with_extract:
        extract = {
            "meta": {"source_id": "src_a"},
            "objectives": [
                {
                    "value": "Grow awareness in the launch window.",
                    "lang": "en",
                    "location": "§2",
                    "anchor": "grow awareness fast",
                    "speaker_or_author": "Acme CMO",
                    "qualifier": "stated",
                    "confidence": "high",
                }
            ],
            "audiences": [],
            "key_messages": [],
            "deliverables": [],
            "timeline": [],
            "budget": [],
            "mandatories": [],
            "open_questions": [{"field": "budget", "question": "amount?"}],
            "internal_conflicts": [],
            "extraction_notes": ["Token flagged as glossary-match; extracted as written."],
        }
        (run_dir / "extracts").mkdir()
        (run_dir / "extracts" / "src_a.json").write_text(
            json.dumps(extract, ensure_ascii=False), encoding="utf-8"
        )
    return run_dir


# ---------------------------------------------------------------- completeness


@pytest.mark.parametrize("run", STORED_RUNS)
def test_every_source_and_its_extract_anchors_appear(run):
    """The page's promise is 'see how the ingested material travelled' — every source
    and every cited excerpt it contributed must be on the page."""
    data = _collect(run)
    page = run_review.render_run_review(data)
    for source in data["run"]["sources"]:
        assert html.escape(str(source["source_id"])) in page
    assert data["extracts"], f"{run} has no extracts — fixture no longer exercises the test"
    for extract in data["extracts"].values():
        for field in review.BRIEF_FIELDS:
            for item in extract.get(field) or []:
                assert html.escape(item["anchor"]) in page
                assert html.escape(item["value"]) in page
        for note in extract.get("extraction_notes") or []:
            assert html.escape(str(note)) in page


@pytest.mark.parametrize("run", STORED_RUNS)
def test_every_pipeline_step_and_conflict_candidate_appears(run):
    data = _collect(run)
    page = run_review.render_run_review(data)
    for step in data["run"]["steps"]:
        assert f'jstep-no">{step["number"]}<' in page
    for candidate in (data.get("conflicts") or {}).get("cross_source_candidates") or []:
        for position in candidate.get("positions") or []:
            assert html.escape(position["anchor"]) in page


def test_fidelity_verdict_rides_with_its_transcript():
    """The fidelity gate's judgement is the transcript's health certificate — it must
    appear with the source card, flagged-token count included."""
    data = _collect("runs/evidence-20260729")
    page = run_review.render_run_review(data)
    assert data["fidelity"], "evidence run lost its fidelity report"
    for report in data["fidelity"].values():
        assert html.escape(str(report["verdict"])) in page
    assert "όροι επισημάνθηκαν" in page


# ----------------------------------------------------------------- containment


def test_page_chrome_never_adds_cost_or_model_strings(tmp_path):
    """The manifest's attempts payloads carry run cost + model ids; the collector must
    drop them and the chrome must add none of its own. The synthetic manifest here
    plants a poisoned attempts block to prove the filter."""
    run_dir = _mini_run_dir(tmp_path)
    page = run_review.render_run_review(run_review.collect_run(run_dir))
    assert "$" not in page
    assert "poisoned" not in page
    assert "9.99" not in page
    assert not FORBIDDEN.search(page), FORBIDDEN.search(page).group(0)


@pytest.mark.parametrize("run", STORED_RUNS)
def test_stored_pages_add_nothing_the_artifacts_do_not_say(run):
    """Any forbidden-family string on the page must already exist in the artifact files
    the page renders (extracts, conflicts, classification, brief) — never from the
    manifest's attempts or the chrome."""
    data = _collect(run)
    page = run_review.render_run_review(data)
    assert "$" not in page
    corpus = json.dumps(
        {k: data[k] for k in ("run", "classification", "fidelity", "extracts", "conflicts", "brief")},
        ensure_ascii=False,
    ) + "".join(data["raw_sources"].values())
    for match in {m.group(0).lower() for m in FORBIDDEN.finditer(page)}:
        assert re.search(match, corpus, re.IGNORECASE), (
            f"page says {match!r} but the run's artifacts never do"
        )
    assert not re.search(r"claude|sonnet|haiku|opus", page, re.IGNORECASE)


def test_artifact_script_tags_arrive_escaped(tmp_path):
    """Extract content is model-authored and untrusted, raw source docs doubly so."""
    payload = "<script>alert(1)</script>"
    run_dir = _mini_run_dir(tmp_path)
    extract_path = run_dir / "extracts" / "src_a.json"
    extract = json.loads(extract_path.read_text(encoding="utf-8"))
    extract["objectives"][0]["value"] = payload
    extract["objectives"][0]["anchor"] = payload
    extract["extraction_notes"] = [payload]
    extract_path.write_text(json.dumps(extract, ensure_ascii=False), encoding="utf-8")
    page = run_review.render_run_review(run_review.collect_run(run_dir))
    assert payload not in page
    assert page.count("<script>") == 1  # the page's own inline script only
    assert html.escape(payload) in page


# ----------------------------------------------------------- chrome & behavior


def test_greek_first_chrome_with_a_data_lang_toggle(tmp_path):
    page = run_review.render_run_review(run_review.collect_run(_mini_run_dir(tmp_path)))
    assert '<html lang="el" data-lang="el">' in page
    assert 'data-set-lang="en"' in page
    assert '[data-lang="el"] .i-en { display: none; }' in page
    assert "Τι εισήλθε" in page


def test_demo_override_and_refusal_statuses_are_visible():
    """runs/live went through the demo profile: the gate refused, the profile overrode
    it — the walkthrough must show that honestly, never hide it."""
    page = run_review.render_run_review(_collect("runs/live"))
    assert "παράκαμψη demo" in page
    assert "προφίλ demo" in page


def test_synthesis_section_links_to_the_brief_page_when_it_exists():
    data = _collect("runs/evidence-20260729")
    assert data["has_brief_page"], "evidence run lost brief_review.html"
    page = run_review.render_run_review(data)
    assert 'href="brief_review.html"' in page
    readiness = data["brief"]["readiness"]
    assert f"{readiness['fields_with_evidence']}/7" in page


def test_partial_run_without_brief_renders_a_quiet_absence(tmp_path):
    """An extraction-only or refused run has no brief — the page must say so plainly
    instead of breaking or pretending."""
    run_dir = _mini_run_dir(tmp_path)
    page = run_review.render_run_review(run_review.collect_run(run_dir))
    assert "Η σύνθεση δεν έτρεξε" in page
    assert 'href="brief_review.html"' not in page


def test_render_is_deterministic(tmp_path):
    data = run_review.collect_run(_mini_run_dir(tmp_path))
    assert run_review.render_run_review(data) == run_review.render_run_review(data)


def test_raw_source_documents_are_embedded_when_the_project_resolves():
    """fixtures/northlight_01 still exists beside the evidence run, so the original
    RFP/emails/transcript ride along for reference — capped, escaped."""
    data = _collect("runs/evidence-20260729")
    if not data["raw_sources"]:
        pytest.skip("project dir not resolvable on this machine")
    page = run_review.render_run_review(data)
    assert "Πρωτότυπο έγγραφο" in page
    some_id, some_text = next(iter(data["raw_sources"].items()))
    assert html.escape(some_text[:200]) in page


# ------------------------------------------------------------------ write/CLI


def test_write_run_review_emits_the_page_beside_the_manifest(tmp_path):
    run_dir = _mini_run_dir(tmp_path)
    out = run_review.write_run_review(run_dir)
    assert out == run_dir / "run_review.html"
    assert out.read_text(encoding="utf-8") == run_review.render_run_review(
        run_review.collect_run(run_dir)
    )


def test_write_run_review_raises_a_legible_error_without_a_manifest(tmp_path):
    empty = tmp_path / "not-a-run"
    empty.mkdir()
    with pytest.raises(review.ReviewInputError) as excinfo:
        run_review.write_run_review(empty)
    message = str(excinfo.value)
    assert "run_manifest.json" in message
    assert str(empty) in message


def test_cli_prints_the_emitted_path_and_fails_legibly(tmp_path, capsys):
    run_dir = _mini_run_dir(tmp_path)
    assert run_review.main([str(run_dir)]) == 0
    assert str(run_dir / "run_review.html") in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_review.main([str(empty)]) == 1
    assert "run_manifest.json" in capsys.readouterr().err
