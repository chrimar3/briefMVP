"""Retention inventory and purge (pipeline/retention.py) on synthetic runs in tmp dirs.
Committed evidence is only ever touched in dry-run or refusal paths."""

import json

import pytest

from pipeline import revisions, retention

SOURCE_TEXT = "# Synthetic RFP\nsource_id: rfp · source_type: rfp · source_date: 2026-09-01\n\nSynthetic Person A asks for a launch.\n"


def make_run(tmp_path, name="run-1", with_package=True):
    project = tmp_path / "project"
    project.mkdir(exist_ok=True)
    source = project / "rfp.md"
    source.write_text(SOURCE_TEXT, encoding="utf-8")
    runs = tmp_path / "runs"
    run = runs / name
    run.mkdir(parents=True)
    revisions.capture_evidence(run, {"source:rfp": source})
    revisions.write_json(run / "input_snapshot.json", revisions.input_state({"source:rfp": source}))
    revisions.write_json(run / "extracts" / "rfp.json", {"objectives": [{"anchor": "Synthetic Person A"}]})
    (run / "fidelity").mkdir()
    (run / "fidelity" / "rfp.annotated.md").write_text(SOURCE_TEXT + "[FIDELITY: ok]\n", encoding="utf-8")
    revisions.write_json(run / "brief.json", {"meta": {"project_id": "p"}, "objectives": []})
    (run / "brief_en.md").write_text("Synthetic Person A [rfp L1]\n", encoding="utf-8")
    # A superseded copy of the evidence and of the extract, as archive() would leave them.
    history = run / "history" / "20260901T000000-abcdef12"
    (history / "extracts").mkdir(parents=True)
    (history / "extracts" / "rfp.json").write_text("{}", encoding="utf-8")
    (history / "rfp-copy.md").write_bytes(source.read_bytes())
    revisions.write_json(history / "brief.json", {"old": True})
    revisions.write_json(run / "run_manifest.json", {
        "run_id": name, "sources": [{"source_id": "rfp"}],
        "steps": [{"name": "extraction", "extracts": [{"attempts": [{"subagent": {"session_id": "sess-synthetic-1"}}]}]}]})
    revisions.write_json(run / "effort.json", {"events": [{"actor": "synthetic-account"}]})
    package = None
    if with_package:
        package = tmp_path / "packages" / "release-1"
        package.mkdir(parents=True)
        (package / "creative.md").write_text("# Approved creative brief\n", encoding="utf-8")
        (package / "stray-source.md").write_bytes(source.read_bytes())
        revisions.write_json(run / "releases.json", [{"path": str(package), "manifest_sha256": "0" * 64, "at": "x"}])
    return runs, run, source, package


class NothingCommitted:
    def is_committed(self, path):
        return False


class EverythingCommitted:
    def is_committed(self, path):
        return True


def test_inventory_finds_every_copy_and_derivative(tmp_path):
    runs, run, source, package = make_run(tmp_path)
    report = retention.inventory([runs])
    assert report["run_count"] == 1
    (entry,) = report["sources"]
    assert entry["sha256"] == retention.sha256_file(source)
    assert entry["source_ids"] == ["rfp"]
    areas = sorted(c["area"] for c in entry["copies"])
    assert areas == ["evidence", "history", "package"]
    derived = {p["path"].split("run-1/")[-1] for p in entry["per_source_derivatives"]}
    assert {"extracts/rfp.json", "fidelity/rfp.annotated.md", "history/20260901T000000-abcdef12/extracts/rfp.json"} <= derived
    assert any(p.endswith("brief.json") for p in entry["run_level_derived"])
    assert entry["originals_present"] == [str(source.resolve())]
    (run_report,) = report["runs"]
    assert run_report["cli_session_ids"] == ["sess-synthetic-1"]
    assert "effort.json" in run_report["personal_records"] and "releases.json" in run_report["personal_records"]
    assert run_report["release_packages"] == [{"path": str(package), "exists": True}]


def test_inventory_accepts_a_single_run_directory(tmp_path):
    runs, run, _, _ = make_run(tmp_path, with_package=False)
    assert retention.inventory([run])["run_count"] == 1


def test_purge_source_dry_run_changes_nothing(tmp_path):
    runs, run, source, package = make_run(tmp_path)
    before = sorted(p for p in tmp_path.rglob("*"))
    sha = retention.sha256_file(source)
    result = retention.purge_source(sha, [runs], actor="Synthetic DPO", reason="Rehearsal erasure request",
                                    dry_run=True, protection=NothingCommitted())
    assert result["dry_run"] and len(result["deleted"]) >= 5
    assert sorted(p for p in tmp_path.rglob("*")) == before
    assert not (runs / retention.TOMBSTONE_FILE).exists()


def test_purge_source_deletes_copies_and_writes_a_tombstone(tmp_path):
    runs, run, source, package = make_run(tmp_path)
    sha = retention.sha256_file(source)
    result = retention.purge_source(sha, [runs], actor="Synthetic DPO", reason="Rehearsal erasure request",
                                    protection=NothingCommitted())
    assert not list((run / "evidence").glob("*.md"))
    assert not (run / "history" / "20260901T000000-abcdef12" / "rfp-copy.md").exists()
    assert not (package / "stray-source.md").exists() and (package / "creative.md").exists()
    assert not (run / "extracts" / "rfp.json").exists() and not (run / "fidelity" / "rfp.annotated.md").exists()
    # The original project file is never deleted by this tool; the run-level quotes are residual.
    assert source.exists() and result["originals_not_deleted"] == [str(source.resolve())]
    assert any(p.endswith("brief_en.md") for p in result["residual_run_level_derived"])
    lines = (runs / retention.TOMBSTONE_FILE).read_text(encoding="utf-8").splitlines()
    tombstone = json.loads(lines[-1])
    assert tombstone["actor"] == "Synthetic DPO" and tombstone["reason"] == "Rehearsal erasure request"
    assert tombstone["action"] == "purge_source" and tombstone["target"]["source_sha256"] == sha
    assert all("sha256" in d for d in tombstone["deleted"])
    # Hashes and paths only: the tombstone never carries the deleted content.
    assert "Synthetic Person A" not in lines[-1]
    # Evidence integrity now fails for that run, as it must after an erasure.
    with pytest.raises(ValueError):
        revisions.verify_evidence(run)


def test_purge_run_deletes_the_run_and_keeps_packages(tmp_path):
    runs, run, source, package = make_run(tmp_path)
    result = retention.purge_run(run, actor="Synthetic operator", reason="Pilot-end deletion",
                                 protection=NothingCommitted())
    assert not run.exists() and package.exists() and source.exists()
    assert result["release_packages_not_deleted"] == [str(package)]
    assert result["cli_session_ids_to_delete_in_operator_profile"] == ["sess-synthetic-1"]
    tombstone = json.loads((runs / retention.TOMBSTONE_FILE).read_text(encoding="utf-8").splitlines()[-1])
    assert tombstone["action"] == "purge_run" and tombstone["deleted"][0]["kind"] == "directory"


def test_committed_evidence_is_protected_unless_explicitly_named(tmp_path):
    runs, run, source, _ = make_run(tmp_path)
    sha = retention.sha256_file(source)
    result = retention.purge_source(sha, [runs], actor="A", reason="R", protection=EverythingCommitted())
    assert result["deleted"] == [] and result["skipped_committed"]
    assert list((run / "evidence").glob("*.md"))
    with pytest.raises(retention.RetentionError, match="committed evidence"):
        retention.purge_run(run, actor="A", reason="R", protection=EverythingCommitted())
    assert run.exists()
    # Explicitly named and explicitly allowed: the operator's decision, executed and recorded.
    retention.purge_run(run, actor="A", reason="R", include_committed=True, protection=EverythingCommitted())
    assert not run.exists()


def test_the_real_committed_runs_are_refused(repo_root):
    tier3 = repo_root / "runs" / "tier3"
    with pytest.raises(retention.RetentionError, match="committed evidence"):
        retention.purge_run(tier3, actor="A", reason="R")
    assert (tier3 / "brief.json").is_file()


def test_legacy_runs_are_inventoried_from_their_manifest(repo_root):
    report = retention.inventory([repo_root / "runs" / "tier3"])
    ids = {sid for entry in report["sources"] for sid in entry["source_ids"]}
    assert ids == {"background_brand_guidelines", "emails_thread", "rfp_meltemi", "transcript_kickoff"}
    assert all(entry.get("identity") == "legacy_manifest" for entry in report["sources"])


def test_purge_requires_attribution_and_a_known_sha(tmp_path):
    runs, run, source, _ = make_run(tmp_path)
    with pytest.raises(retention.RetentionError, match="actor"):
        retention.purge_run(run, actor=" ", reason="R", protection=NothingCommitted())
    with pytest.raises(retention.RetentionError, match="SHA-256"):
        retention.purge_source("not-a-sha", [runs], actor="A", reason="R", protection=NothingCommitted())
    with pytest.raises(retention.RetentionError, match="No run"):
        retention.purge_source("a" * 64, [runs], actor="A", reason="R", protection=NothingCommitted())
    with pytest.raises(retention.RetentionError, match="not a run directory"):
        retention.purge_run(tmp_path / "project", actor="A", reason="R", protection=NothingCommitted())


def test_cli_inventory_and_refusals(tmp_path, capsys):
    runs, run, source, _ = make_run(tmp_path)
    out = tmp_path / "inventory.json"
    assert retention.main(["inventory", "--runs", str(runs), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["run_count"] == 1
    assert retention.main(["purge", "--source-sha", retention.sha256_file(source), "--actor", "A",
                           "--reason", "R"]) == 2
    assert "--runs" in capsys.readouterr().err
    assert retention.main(["purge", "--run", str(run), "--actor", "A", "--reason", "R", "--dry-run"]) == 0
    assert run.exists()


def _stage_inputs(run, source):
    """The read-only copies the runner stages for agents (pipeline/runner.py stage_inputs)."""
    staged = run / "inputs" / source.name
    (run / "inputs" / "client").mkdir(parents=True)
    staged.write_bytes(source.read_bytes())
    staged.chmod(0o444)
    (run / "inputs" / "client" / "client.json").write_text('{"client_id": "synthetic"}', encoding="utf-8")
    return staged


def test_staged_input_copies_are_inventoried_and_purged(tmp_path):
    runs, run, source, _ = make_run(tmp_path, with_package=False)
    staged = _stage_inputs(run, source)
    report = retention.inventory([runs])
    (entry,) = report["sources"]
    assert {"path": str(staged.resolve()), "area": "inputs", "run": str(run.resolve())} in entry["copies"]
    staged_listing = {p["path"] for p in report["runs"][0]["staged_inputs"]}
    assert staged_listing == {str(staged.resolve()), str((run / "inputs" / "client" / "client.json").resolve())}
    result = retention.purge_source(entry["sha256"], [runs], actor="Synthetic DPO", reason="Erasure rehearsal",
                                    protection=NothingCommitted())
    assert not staged.exists()
    assert str(staged.resolve()) in {d["path"] for d in result["deleted"]}


def _logged_run(tmp_path):
    runs, run, source, package = make_run(tmp_path, with_package=False)
    revisions.append_audit(run, "conflict_resolved", "Synthetic Lead A", record="brief.json")
    revisions.append_audit(run, "brief_amended", "Synthetic Lead A", details={"reason": "synthetic"})
    return runs, run, source


def test_purge_run_tombstones_the_audit_log_before_deleting_it(tmp_path):
    runs, run, _ = _logged_run(tmp_path)
    log = run / "audit_log.jsonl"
    sha, lines = retention.sha256_file(log), log.read_text(encoding="utf-8").splitlines()
    result = retention.purge_run(run, actor="Synthetic operator", reason="Pilot-end deletion",
                                 protection=NothingCommitted())
    assert not run.exists()
    stone = result["audit_log_deleted"]
    assert stone["sha256"] == sha and stone["entries"] == 2 and stone["verified_intact"] is True
    assert stone["events"] == {"brief_amended": 1, "conflict_resolved": 1}
    assert stone["chain_head_sha256"] == revisions._line_hash(lines[-1])
    written = (runs / retention.TOMBSTONE_FILE).read_text(encoding="utf-8").splitlines()[-1]
    assert json.loads(written)["audit_log_deleted"]["sha256"] == sha
    assert "Synthetic Lead A" not in written  # hashes and counts, never the names in the entries


def test_purge_run_dry_run_reports_the_audit_log_and_keeps_it(tmp_path):
    runs, run, _ = _logged_run(tmp_path)
    result = retention.purge_run(run, actor="Synthetic operator", reason="Check", dry_run=True,
                                 protection=NothingCommitted())
    assert result["audit_log_deleted"]["entries"] == 2 and (run / "audit_log.jsonl").is_file()


def test_purge_source_never_deletes_an_audit_log(tmp_path):
    runs, run, source = _logged_run(tmp_path)
    # Even a byte-identical copy named like the log (contrived) is not treated as a source copy.
    (run / "history" / "20260901T000000-abcdef12" / "audit_log.jsonl").write_bytes(source.read_bytes())
    retention.purge_source(retention.sha256_file(source), [runs], actor="Synthetic DPO", reason="Erasure",
                           protection=NothingCommitted())
    assert (run / "audit_log.jsonl").is_file()
    assert (run / "history" / "20260901T000000-abcdef12" / "audit_log.jsonl").is_file()


# A corrupt record is refused and named, never read as empty: before, a corrupt releases.json
# silently yielded no packages and a corrupt evidence_index.json fell back to legacy identity,
# so an inventory under-reported copies and a purge left them behind.

@pytest.mark.parametrize("record", ["releases.json", "evidence_index.json", "input_snapshot.json",
                                    "run_manifest.json"])
def test_inventory_refuses_a_corrupt_record(tmp_path, record):
    runs, run, _, _ = make_run(tmp_path)
    (run / record).write_text("{not json", encoding="utf-8")
    with pytest.raises(revisions.CorruptRecordError) as caught:
        retention.inventory([runs])
    assert caught.value.path == run / record and record in str(caught.value)


def test_purge_refuses_a_corrupt_record_and_deletes_nothing(tmp_path):
    runs, run, source, package = make_run(tmp_path)
    (run / "releases.json").write_text("[{", encoding="utf-8")
    before = sorted(p for p in tmp_path.rglob("*"))
    with pytest.raises(ValueError, match="releases.json"):
        retention.purge_source(retention.sha256_file(source), [runs], actor="Synthetic DPO",
                               reason="Erasure", protection=NothingCommitted())
    with pytest.raises(ValueError, match="releases.json"):
        retention.purge_run(run, actor="Synthetic operator", reason="Pilot end", protection=NothingCommitted())
    assert sorted(p for p in tmp_path.rglob("*")) == before
    assert not (runs / retention.TOMBSTONE_FILE).exists()


def test_cli_names_the_corrupt_record_and_exits_2(tmp_path, capsys):
    runs, run, _, _ = make_run(tmp_path)
    (run / "evidence_index.json").write_text("{", encoding="utf-8")
    assert retention.main(["inventory", "--runs", str(runs)]) == 2
    err = capsys.readouterr().err
    assert "evidence_index.json" in err and "corrupt record" in err
