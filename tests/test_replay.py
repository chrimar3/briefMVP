"""Offline replay: parsing, work-order coverage, refusal, and the recording's provenance."""

import importlib.util
import json
from pathlib import Path

import pytest

from pipeline import extraction, gates, quality, replay, stages

REPO = Path(__file__).resolve().parents[1]
RECORDING = replay.DEFAULT_RECORDED_RUN


@pytest.fixture(autouse=True)
def _default_recording(monkeypatch):
    monkeypatch.delenv(replay.RECORDED_RUN_ENV, raising=False)


def _load_derive_module():
    spec = importlib.util.spec_from_file_location("derive_recording", REPO / "tools/replay/derive_recording.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_parsing_takes_prompt_and_agent_and_ignores_every_other_flag():
    argv = ["-p", "ORDER", "--agents", '{"x": {}}', "--agent", "render", "--permission-mode", "plan",
            "--allowedTools", "Read", "Write", "--add-dir", "/a", "--effort", "low", "--brand-new-flag"]
    assert replay.parse_cli(argv) == ("render", "ORDER")
    assert replay.parse_cli(["--agent=extract", "-p", "X"]) == ("extract", "X")
    with pytest.raises(replay.ReplayError, match="no --agent"):
        replay.parse_cli(["-p", "X"])


def test_every_real_work_order_names_the_paths_replay_writes(tmp_path, fixture_project):
    """Ties replay to the actual order builders: an order format change fails here, loudly."""
    sources = gates.discover_sources(fixture_project)
    transcript = next(s for s in sources if s.source_type == "transcript")
    config = {"client_id": "c", "sensitivity_tier": "S1"}
    run = tmp_path / "run dir with spaces"
    orders = {
        "classify": (stages.build_classification_order(sources, run / "classification.json", "p", config,
                                                       tmp_path / "g.json"), [run / "classification.json"]),
        "fidelity-check": (stages.build_fidelity_order(transcript, run / "fidelity/t.report.json",
                                                       run / "fidelity/t.annotated.md", tmp_path / "g.json"),
                           [run / "fidelity/t.report.json", run / "fidelity/t.annotated.md"]),
        "extract": (extraction.build_work_order(transcript, run / "extracts/t.json", "p", config,
                                                tmp_path / "g.json"), [run / "extracts/t.json"]),
        "verify-extract": (extraction.build_verify_order(transcript, run / "extracts/t.json",
                                                         run / "verification/t.verify.json", tmp_path / "g.json"),
                           [run / "verification/t.verify.json"]),
        "synthesize": (stages.build_synthesis_order(run, run / "brief.json", "p", config,
                                                    {"project_type": "x", "classification_confidence": "high",
                                                     "sensitivity_tier": "S1"}, sources, tmp_path / "g.json"),
                       [run / "brief.json"]),
        "render": (stages.build_render_order(run / "brief.json", run / "brief_el.md", run / "brief_en.md",
                                             tmp_path / "t.md", tmp_path / "g.json"),
                   [run / "brief_el.md", run / "brief_en.md"]),
        "extract repair": (extraction.build_repair_order(
            run / "extracts/t.json", ["v"],
            extraction.build_work_order(transcript, run / "extracts/t.json", "p", config, tmp_path / "g.json")),
            [run / "extracts/t.json"]),
    }
    for name, (order, expected) in orders.items():
        assert replay.output_paths(order) == expected, name


def test_replay_copies_the_recorded_artifact(tmp_path):
    target = tmp_path / "run" / "extracts" / "rfp_meltemi.json"
    order = f"project_id : northlight_01\nWrite one JSON object to exactly this path:\n    {target}\n"
    assert replay.replay("extract", order) == [target]
    assert target.read_bytes() == (RECORDING / "extracts" / "rfp_meltemi.json").read_bytes()


def test_replay_refuses_another_project_and_missing_artifacts(tmp_path):
    order = "project_id : someone_else\nWrite one JSON object to exactly this path:\n    /tmp/x/brief.json\n"
    with pytest.raises(replay.ReplayError, match="only reproduces the project it recorded"):
        replay.replay("synthesize", order)
    missing = f"Write one JSON object to exactly this path:\n    {tmp_path}/nothing_recorded.json\n"
    with pytest.raises(replay.ReplayError, match="no artifact for nothing_recorded.json"):
        replay.replay("classify", missing)


def test_pathless_repair_order_leaves_the_artifact_for_the_gate_to_judge_again():
    assert replay.replay("render", "REPAIR ORDER — your renders failed the gate:\n  - x\n") == []


def test_main_prints_a_cli_shaped_error_reply_and_exits_nonzero(capsys):
    assert replay.main(["--agent", "classify", "-p", "no paths here"]) == 1
    reply = json.loads(capsys.readouterr().out)
    assert reply["is_error"] is True and reply["total_cost_usd"] == 0.0


def test_recording_is_pre_human_and_marks_what_replay_synthesised():
    brief = json.loads((RECORDING / "brief.json").read_text(encoding="utf-8"))
    assert "readiness" not in brief
    assert brief["signoff"] == {"status": "draft"}
    assert all(c["status"] == "open" and "resolution" not in c for c in brief["conflicts"])
    labels = stages.load_template_labels(REPO / "templates" / "northlight_client_brief.labels.json")
    for lang in ("en", "el"):
        text = (RECORDING / f"brief_{lang}.md").read_text(encoding="utf-8")
        assert labels[lang]["banner_draft"] in text.splitlines()
        assert labels[lang]["banner_signed_prefix"] not in text
        assert "SIGNED OFF" not in text and "ΥΠΟΓΕΓΡΑΜΜΕΝΟ" not in text and "ΕΓΚΡΙΘΗΚΕ" not in text
    for report in (RECORDING / "verification").glob("*.verify.json"):
        assert "Synthesised for offline replay" in json.loads(report.read_text(encoding="utf-8"))["note"]


def test_committed_recording_matches_its_documented_derivation(tmp_path):
    """The recording is runs/tier3 minus the human layer, plus only the documented round-2
    contract edits: re-deriving it from the committed evidence must reproduce the committed copy
    byte for byte."""
    derived = tmp_path / "derived"
    _load_derive_module().derive(derived)
    committed = sorted(p.relative_to(RECORDING) for p in RECORDING.rglob("*") if p.is_file())
    assert sorted(p.relative_to(derived) for p in derived.rglob("*") if p.is_file()) == committed
    for rel in committed:
        assert (derived / rel).read_bytes() == (RECORDING / rel).read_bytes(), rel


def test_recording_renders_pass_the_current_render_gates():
    """The recorded renders are wiring fixtures generated from the recording's own brief.json
    against today's template: both blocking render gates must accept them as they stand, so the
    replayed render stage is judged by the real gates, never by a weakened copy."""
    brief = json.loads((RECORDING / "brief.json").read_text(encoding="utf-8"))
    brief["readiness"] = gates.compute_readiness_block(brief)
    glossary = json.loads((REPO / "glossary" / "meltemi.json").read_text(encoding="utf-8"))
    template = stages.resolve_brief_template(glossary)
    labels = stages.load_template_labels(template["labels"])
    el, en = RECORDING / "brief_el.md", RECORDING / "brief_en.md"
    assert stages.check_render(el, en, brief, glossary) == []
    assert stages.check_render_template(el, en, brief, labels) == []
    # The agency approval check too — six of the ten questions cite bracketed transcript
    # timestamps, the T-01 shape (docs/pilot/GO_LIVE_DECISIONS.md).
    assert sum(any(r["location"].startswith("[") for r in q["linked_evidence"])
               for q in brief["open_questions"]) == 6
    for lang, path in (("en", en), ("el", el)):
        assert quality.render_coverage(brief, path.read_text(encoding="utf-8"), lang) == []
