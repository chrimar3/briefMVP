"""demo/run_demo.py — the script shown live in the defence session — under test, offline.

The happy path replays a wiring recording through the fake `claude` CLI (zero model calls):
the facts table must carry verbatim anchors, the verification gates must be recomputed, and
nothing may be written into the repository's runs/. The refusal paths never reach a model.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from pipeline import gates, replay

REPO = Path(__file__).resolve().parents[1]
DEMO = REPO / "demo" / "run_demo.py"
KICKOFF = REPO / "fixtures" / "northlight_01" / "transcript_kickoff.md"


def _load_demo():
    spec = importlib.util.spec_from_file_location("run_demo_under_test", DEMO)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def run_demo():
    return _load_demo()


@pytest.fixture
def repo_runs_unchanged():
    """The demo writes its run folder under gates.REPO_ROOT/runs; tests redirect it, and check that."""
    before = {p.name for p in (REPO / "runs").iterdir()}
    yield
    assert {p.name for p in (REPO / "runs").iterdir()} == before, "the demo test wrote into runs/"


def _script(*args, stdin=None):
    """Run the demo as a script against the offline replay binary (a real CLI is refused without
    the live opt-in, before any other check), so the refusal under test is the one reached."""
    env = {**os.environ, "BRIEF_BUILDER_CLAUDE_BIN": str(REPO / "tools" / "replay" / "claude")}
    env.pop("BRIEF_BUILDER_LIVE", None)
    return subprocess.run([sys.executable, str(DEMO), *args], cwd=REPO, input=stdin, env=env,
                          capture_output=True, text=True, timeout=60)


def _declared(folder: Path) -> Path:
    """A synthetic data declaration for the folder holding the demo input (the demo refuses an
    undeclared folder before it reads the input)."""
    (folder / "data_declaration.json").write_text('{"data_class": "synthetic"}', encoding="utf-8")
    return folder


def test_help_works_as_a_script():
    result = _script("--help")
    assert result.returncode == 0, result.stderr
    assert "One document in, verified facts out." in result.stdout


def test_missing_file_is_refused_before_any_model_call(tmp_path, repo_runs_unchanged):
    result = _script(str(_declared(tmp_path) / "absent.md"), "--out", str(tmp_path / "out"))
    assert result.returncode != 0
    assert "[demo] no such file" in result.stderr


def test_uninferable_document_is_refused_with_instructions(tmp_path, repo_runs_unchanged):
    notes = _declared(tmp_path) / "notes.txt"
    notes.write_text("A few loose thoughts about a campaign.\nNothing that says what this is.\n", encoding="utf-8")
    result = _script(str(notes), "--out", str(tmp_path / "out"))
    assert result.returncode != 0
    assert "cannot infer what this document is" in result.stderr
    assert "--type transcript|rfp|email_thread|background" in result.stderr


def test_invalid_type_override_is_refused(tmp_path, repo_runs_unchanged):
    notes = _declared(tmp_path) / "notes.txt"
    notes.write_text("Loose notes.\n", encoding="utf-8")
    result = _script(str(notes), "--type", "memo", "--out", str(tmp_path / "out"))
    assert result.returncode != 0
    assert "--type must be one of" in result.stderr


def test_long_input_is_capped_at_the_word_limit_without_cutting_the_header(run_demo):
    header = "# Notes\nsource_id: long · source_type: transcript · source_date: 2026-09-01\n\n"
    body = "\n".join(f"[00:00:{i:02d}] A: " + "word " * 20 for i in range(60))  # 60 lines x 22 words
    capped, count, was_capped = run_demo._cap_words(header + body, 800)
    assert was_capped and count <= 800
    assert capped.startswith(header.rstrip("\n").split("\n")[0])
    assert "source_id: long" in capped
    untouched, count, was_capped = run_demo._cap_words(header + "[00:00:01] A: short\n", 800)
    assert not was_capped and untouched == header + "[00:00:01] A: short\n"


def test_broken_input_is_stamped_as_a_transcript(run_demo):
    """demo/broken_input.txt (the rehearsal's bad phone line) has no header: the demo stamps it."""
    text = (REPO / "demo" / "broken_input.txt").read_text(encoding="utf-8")
    stamped, meta = run_demo._stamp(text, "broken_input.txt", None)
    assert meta["source_type"] == "transcript" and meta["source_id"] == "demo_input"
    assert gates.parse_source_header(stamped, Path("demo_input.md"))["source_type"] == "transcript"


def _demo_recording(tmp_path: Path) -> Path:
    """The northlight wiring recording, re-labelled for the demo's project id (`demo`)."""
    recording = tmp_path / "recording"
    shutil.copytree(replay.DEFAULT_RECORDED_RUN, recording)
    classification = recording / "classification.json"
    data = json.loads(classification.read_text(encoding="utf-8"))
    data["project_id"] = "demo"
    classification.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return recording


def test_replayed_demo_prints_verbatim_facts_and_recomputed_gates(
        run_demo, fake_claude, tmp_path, monkeypatch, capsys, repo_runs_unchanged):
    monkeypatch.setenv(replay.RECORDED_RUN_ENV, str(_demo_recording(tmp_path)))
    monkeypatch.setenv("BRIEF_BUILDER_CLAUDE_BIN", str(fake_claude))
    monkeypatch.setenv("DEMO_NO_OPEN", "1")
    (tmp_path / "runs").mkdir()  # the run folder goes to tmp_path/runs (--out), never the repo's runs/

    glossary = next((REPO / "glossary").glob("*.json"))  # the single client config (meltemi)
    assert run_demo.main([str(KICKOFF), "--retries", "0", "--glossary", str(glossary),
                          "--project-id", "demo", "--out", str(tmp_path / "runs")]) == 0
    out = capsys.readouterr().out

    written = sorted((tmp_path / "runs").glob("demo-*/extracts/transcript_kickoff.json"))
    assert len(written) == 1, "the demo wrote no extract (or more than one run)"
    extract = json.loads(written[0].read_text(encoding="utf-8"))
    assert (written[0].parents[1] / "run_review.html").is_file(), "the walkthrough page was not written"
    source = KICKOFF.read_text(encoding="utf-8")
    items = [i for f in gates.BRIEF_FIELDS for i in extract.get(f) or []]
    assert items
    assert all(i["anchor"] in source for i in items), "an anchor is not verbatim in the source"
    assert f"FACTS the document actually states ({len(items)}):" in out
    assert f"citations: {len(items)}/{len(items)} anchor+location strings occur verbatim" in out
    assert "✅ schema" in out
    assert f"OPEN QUESTIONS created instead of guesses ({len(extract.get('open_questions') or [])})" in out
    # Zero spend, reported in tokens (W-S: the demo reports tokens by the CLI, not dollars).
    assert "model: offline replay (no model calls)" in out
    assert "· 0 tokens reported by the CLI ·" in out
