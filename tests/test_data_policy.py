"""Data declaration gate (owner decision 4, 2026-09-22): a project without a valid
`data_declaration.json` is refused before any source is read, by the runner and by intake.
Synthetic data only; no model calls (the conftest poisons the claude binary)."""

import json
import shutil
from datetime import date

import pytest

from pipeline import data_policy, gates, intake, runner

APPROVED = {"data_class": "approved", "approval_ref": "DP-SYNTH-001",
            "approved_by": "Synthetic data-protection lead", "approved_on": "2026-09-01"}


def _copy_fixture(fixture_project, dest, declaration=None):
    dest.mkdir(parents=True)
    for src in fixture_project.glob("*.md"):
        shutil.copy(src, dest / src.name)
    if declaration is not None:
        (dest / "data_declaration.json").write_text(
            declaration if isinstance(declaration, str) else json.dumps(declaration), encoding="utf-8")
    return dest


def _run(project, out, *extra):
    code = runner.main(["--project", str(project), "--out", str(out), "--run-id", "dd", *extra])
    manifest = json.loads((out / "dd" / "run_manifest.json").read_text(encoding="utf-8"))
    return code, manifest


# -- the shipped folders ---------------------------------------------------------------

def test_every_fixture_and_the_demo_project_declare_synthetic(repo_root):
    folders = [p for p in (repo_root / "fixtures").iterdir() if p.is_dir()]
    folders.append(repo_root / "demo_live" / "sources")
    assert len(folders) >= 6
    for folder in folders:
        declaration = data_policy.load_declaration(folder)
        assert declaration.data_class == "synthetic", folder
        assert declaration.is_synthetic and data_policy.is_synthetic(folder)


def test_declaration_is_never_a_source(fixture_project):
    """Only *.md files are sources; the JSON declaration never enters a work order."""
    assert "data_declaration" not in {s.source_id for s in gates.discover_sources(fixture_project)}


# -- validation ------------------------------------------------------------------------

@pytest.mark.parametrize("payload, needle", [
    ({}, "data_class must be one of"),
    ({"data_class": "real"}, "data_class must be one of"),
    ({"data_class": "Synthetic"}, "data_class must be one of"),
    ({"data_class": "approved"}, "requires a non-empty approval_ref"),
    ({**APPROVED, "approved_by": "  "}, "requires a non-empty approved_by"),
    ({**APPROVED, "approved_on": "01/09/2026"}, "ISO date"),
    ({**APPROVED, "approved_on": "2026-02-30"}, "ISO date"),
    ({**APPROVED, "approved_on": "2099-01-01"}, "in the future"),
    ({"data_class": "synthetic", "approval_ref": "X"}, "carries no approval fields"),
    ({"data_class": "synthetic", "client": "x"}, "unknown key"),
    (["synthetic"], "JSON object"),
])
def test_invalid_declarations_are_refused_with_a_precise_reason(tmp_path, payload, needle):
    (tmp_path / "data_declaration.json").write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(data_policy.DataDeclarationError, match=needle):
        data_policy.load_declaration(tmp_path, today=date(2026, 9, 23))
    assert data_policy.is_synthetic(tmp_path) is False


def test_missing_or_unreadable_declaration_is_refused_never_inferred(tmp_path):
    with pytest.raises(data_policy.DataDeclarationError, match="no data_declaration.json"):
        data_policy.load_declaration(tmp_path)
    assert data_policy.is_synthetic(tmp_path) is False
    (tmp_path / "data_declaration.json").write_text("{synthetic", encoding="utf-8")
    with pytest.raises(data_policy.DataDeclarationError, match="not readable JSON"):
        data_policy.load_declaration(tmp_path)


def test_symlinked_declaration_is_refused(tmp_path):
    real = tmp_path / "elsewhere.json"
    real.write_text('{"data_class": "synthetic"}', encoding="utf-8")
    project = tmp_path / "project"
    project.mkdir()
    (project / "data_declaration.json").symlink_to(real)
    with pytest.raises(data_policy.DataDeclarationError, match="symlink"):
        data_policy.load_declaration(project)


def test_approved_declaration_records_its_approval(tmp_path):
    (tmp_path / "data_declaration.json").write_text(json.dumps({**APPROVED, "_note": "synthetic test"}), encoding="utf-8")
    declaration = data_policy.load_declaration(tmp_path, today=date(2026, 9, 23))
    assert not declaration.is_synthetic
    record = declaration.as_record()
    assert record["approval_ref"] == "DP-SYNTH-001" and record["approved_by"].startswith("Synthetic")


def test_error_type_is_an_input_contract_error():
    """Existing callers that catch the input-contract refusal keep working."""
    assert issubclass(data_policy.DataDeclarationError, gates.InputContractError)


def test_approved_material_must_stay_outside_the_repository(tmp_path, repo_root):
    (tmp_path / "data_declaration.json").write_text(json.dumps(APPROVED), encoding="utf-8")
    declaration = data_policy.load_declaration(tmp_path)
    outside = tmp_path / "glossary.json"
    assert data_policy.check_locations(declaration, project_dir=tmp_path, out_dir=tmp_path / "runs",
                                       glossary=outside) == []
    problems = data_policy.check_locations(declaration, project_dir=tmp_path,
                                           out_dir=repo_root / "runs", glossary=None)
    assert any("output directory" in p for p in problems)
    assert any("no explicit --glossary" in p for p in problems)
    synthetic = data_policy.DataDeclaration("synthetic", tmp_path)
    assert data_policy.check_locations(synthetic, project_dir=repo_root / "fixtures", out_dir=repo_root / "runs") == []


# -- the runner ------------------------------------------------------------------------

def test_runner_refuses_an_undeclared_project_before_reading_sources(tmp_path, fixture_project):
    project = _copy_fixture(fixture_project, tmp_path / "project")
    code, manifest = _run(project, tmp_path / "runs")
    assert code == runner.EXIT_DATA_DECLARATION == 6
    assert manifest["outcome"] == "data_declaration_refused"
    assert manifest["exit_code"] == 6
    assert "no data_declaration.json" in manifest["data_declaration"]["refused"]
    # Refused before discovery: no step ran, no source was read, no input snapshot or evidence copy.
    assert manifest["steps"] == [] and manifest["sources"] == []
    assert not (tmp_path / "runs" / "dd" / "input_snapshot.json").exists()
    assert not (tmp_path / "runs" / "dd" / "evidence").exists()


def test_runner_refuses_an_invalid_declaration_with_the_reason(tmp_path, fixture_project):
    project = _copy_fixture(fixture_project, tmp_path / "project", {"data_class": "approved"})
    code, manifest = _run(project, tmp_path / "runs")
    assert code == runner.EXIT_DATA_DECLARATION
    assert "approval_ref" in manifest["data_declaration"]["refused"]


def test_runner_refuses_approved_material_writing_into_the_repository(tmp_path, fixture_project, repo_root):
    project = _copy_fixture(fixture_project, tmp_path / "project", APPROVED)
    out = tmp_path / "runs"
    code, manifest = _run(project, out)  # no --glossary → the in-repo default
    assert code == runner.EXIT_DATA_DECLARATION
    assert "outside the repository" in manifest["data_declaration"]["refused"]


def test_runner_records_a_valid_declaration_and_proceeds(tmp_path, fixture_project, repo_root):
    code, manifest = _run(fixture_project, tmp_path / "runs")
    assert manifest["data_declaration"]["data_class"] == "synthetic"
    # The run went past the declaration and the readiness gate; the poisoned model stops it.
    assert manifest["steps"][0]["name"] == "readiness_gate" and manifest["steps"][0]["status"] == "pass"
    assert code == runner.EXIT_GATE_ERROR

    project = _copy_fixture(fixture_project, tmp_path / "approved", APPROVED)
    glossary = tmp_path / "client.json"
    shutil.copy(repo_root / "glossary" / "meltemi.json", glossary)
    code, manifest = _run(project, tmp_path / "runs2", "--glossary", str(glossary))
    assert manifest["data_declaration"]["approval_ref"] == "DP-SYNTH-001"
    assert manifest["outcome"] != "data_declaration_refused"


# -- intake ----------------------------------------------------------------------------

RAW_RFP = "# RFP — Synthetic Helios\nΖητούμενο: καμπάνια λανσαρίσματος, launch Μάρτιος 2027.\n"


def _raw(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "rfp_helios.md").write_text(RAW_RFP, encoding="utf-8")
    return raw


def test_intake_requires_an_explicit_data_class(tmp_path, capsys):
    raw = _raw(tmp_path)
    with pytest.raises(SystemExit) as exc:
        intake.main([str(raw), "--out", str(tmp_path / "p"), "--client", "helios", "--tier", "S1"])
    assert exc.value.code == 2
    assert "--data-class" in capsys.readouterr().err
    assert not (tmp_path / "p").exists()


def test_intake_writes_the_declaration_the_runner_requires(tmp_path):
    raw = _raw(tmp_path)
    out = tmp_path / "p"
    code = intake.main([str(raw), "--out", str(out), "--client", "helios", "--tier", "S1", "--data-class", "synthetic"])
    assert code in (0, 1)  # 1 = readiness refusal on a one-document folder; the folder is still written
    assert data_policy.load_declaration(out).is_synthetic
    assert json.loads((out / "data_declaration.json").read_text(encoding="utf-8")) == {"data_class": "synthetic"}


def test_intake_approved_needs_the_approval_record_and_an_outside_location(tmp_path, repo_root):
    raw = _raw(tmp_path)
    assert intake.main([str(raw), "--out", str(tmp_path / "a"), "--client", "helios", "--tier", "S1",
                        "--data-class", "approved"]) == 2
    assert not (tmp_path / "a").exists()
    inside = repo_root / "fixtures" / "must_not_be_created"
    assert intake.main([str(raw), "--out", str(inside), "--client", "helios", "--tier", "S1",
                        "--data-class", "approved", "--approval-ref", "DP-SYNTH-001",
                        "--approved-by", "Synthetic lead", "--approved-on", "2026-09-01"]) == 2
    assert not inside.exists()
    out = tmp_path / "b"
    code = intake.main([str(raw), "--out", str(out), "--client", "helios", "--tier", "S1",
                        "--data-class", "approved", "--approval-ref", "DP-SYNTH-001",
                        "--approved-by", "Synthetic lead", "--approved-on", "2026-09-01"])
    assert code in (0, 1)
    assert data_policy.load_declaration(out).approval_ref == "DP-SYNTH-001"


def test_intake_never_silently_changes_a_declared_class(tmp_path):
    raw = _raw(tmp_path)
    out = tmp_path / "p"
    intake.main([str(raw), "--out", str(out), "--client", "helios", "--tier", "S1", "--data-class", "synthetic"])
    code = intake.main([str(raw), "--out", str(out), "--client", "helios", "--tier", "S1", "--force",
                        "--data-class", "approved", "--approval-ref", "DP-SYNTH-001",
                        "--approved-by", "Synthetic lead", "--approved-on", "2026-09-01"])
    assert code == 2
    assert data_policy.load_declaration(out).is_synthetic
    with pytest.raises(data_policy.DataDeclarationError, match="only valid with --data-class approved"):
        data_policy.build_declaration("synthetic", approval_ref="X")


def test_only_synthetic_runs_publish_to_the_in_repo_review_shelf(tmp_path, monkeypatch, fixture_project):
    """reviews/ lives inside the repository: approved material must never be copied there."""
    from pipeline import publish, run_review
    published = []
    monkeypatch.setattr(publish, "_publish_locked", lambda run_dir: published.append(run_dir) or [])
    monkeypatch.setattr(run_review, "write_run_review", lambda run_dir: None)
    for data_class, expected in (("approved", 0), ("synthetic", 1)):
        r = runner.Runner(fixture_project, tmp_path / data_class, run_id="shelf")
        r.run_dir.mkdir(parents=True)
        r.started_ts = "2026-09-23T00:00:00"
        r.data_declaration = {"data_class": data_class}
        r._write_manifest("complete", runner.EXIT_OK)
        assert len(published) == expected
