"""The committed agency-lifecycle rehearsal (runs/rehearsal-lifecycle/) regenerates, deterministically
and without model calls, to the same step sequence and exit codes it recorded."""

import importlib.util
import json

import pytest


@pytest.fixture(scope="module")
def regenerate(repo_root):
    spec = importlib.util.spec_from_file_location("rehearsal_regenerate",
                                                  repo_root / "runs" / "rehearsal-lifecycle" / "regenerate.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fresh(regenerate, tmp_path_factory):
    out = tmp_path_factory.mktemp("rehearsal")
    assert regenerate.main(["--out", str(out)]) == 0
    return out


def _steps(path):
    return [(s["step"].split(" ")[0] if s["step"].startswith("triage ") else s["step"], s["exit_code"])
            for s in json.loads(path.read_text(encoding="utf-8"))]


def test_rehearsal_regenerates_to_the_committed_sequence(fresh, repo_root):
    committed = repo_root / "runs" / "rehearsal-lifecycle" / "transcript.json"
    assert _steps(fresh / "transcript.json") == _steps(committed)


def test_rehearsal_covers_the_whole_lifecycle(fresh):
    names = [s["step"] for s in json.loads((fresh / "transcript.json").read_text(encoding="utf-8"))]
    for needed in ("init", "resolve timeline conflict", "attest (bilingual reviewer)", "audit (clean)",
                   "approve brief (account lead)", "register creative (operator)", "approve creative (creative lead)",
                   "release package", "verify package against the run", "withdraw approval (account lead)",
                   "verify package after withdrawal", "verify audit log"):
        assert needed in names
    steps = {s["step"]: s for s in json.loads((fresh / "transcript.json").read_text(encoding="utf-8"))}
    after = steps["verify package after withdrawal"]
    assert after["exit_code"] == 2 and any("withdrawn: true" in h for h in after["highlights"])
    log = steps["verify audit log"]
    assert names.index("verify audit log") > names.index("withdraw approval (account lead)")
    preview = steps["retention purge (dry run)"]
    assert preview["exit_code"] == 0 and "dry_run: true" in preview["highlights"]
    assert any("verified_intact true" in h for h in preview["highlights"])
    assert log["exit_code"] == 0 and "valid: true" in log["highlights"]


def test_rehearsal_keeps_every_open_question(fresh):
    """T-01 fixed: no question is moved out because the render citation check cannot verify it."""
    preparation = json.loads((fresh / "PREPARATION.json").read_text(encoding="utf-8"))
    assert "questions_moved_out" not in preparation
    brief = json.loads((fresh / "records" / "brief.json").read_text(encoding="utf-8"))
    assert preparation["questions_kept"] == len(brief["open_questions"]) == 10
    assert preparation["questions_with_timestamp_evidence"] == 6


def test_rehearsal_uses_distinct_fictional_actors(fresh):
    records = fresh / "records"
    signer = json.loads((records / "withdrawn_approval.json").read_text(encoding="utf-8"))["actor"]
    attester = json.loads((records / "language_review.json").read_text(encoding="utf-8"))["actor"]
    registrant = json.loads((records / "creative_draft.json").read_text(encoding="utf-8"))["registered_by"]
    approver = json.loads((records / "withdrawn_creative_approval.json").read_text(encoding="utf-8"))["actor"]
    assert len({signer, attester, registrant, approver}) == 4
    assert all(name.startswith("Synthetic ") for name in (signer, attester, registrant, approver))


def test_rehearsal_evidence_carries_no_real_name_or_machine_path(fresh, regenerate):
    probes = regenerate._probes(regenerate.real_names())
    assert probes
    for path in [p for p in fresh.rglob("*") if p.is_file()]:
        text = path.read_text(encoding="utf-8")
        assert not any(p in text for p in probes), path
        assert "/Users/" not in text and "/private/" not in text, path
