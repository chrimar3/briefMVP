"""Intake turns raw client documents into a contract-compliant Input folder — deterministically,
refusing to guess where the evidence is thin. These tests exercise exactly that boundary."""

import json

import pytest

from pipeline import gates, intake


RAW_TRANSCRIPT = (
    "Kickoff call notes\n"
    "[00:01:10] ANNA: Καλημέρα σε όλους.\n"
    "[00:02:30] PETROS: Το launch θέλουμε τον Μάρτιο, budget γύρω στα €50.000.\n"
    "[00:04:12] ANNA: Κρατάω σημείωση.\n"
)

RAW_EMAIL = (
    "**From**: Anna (Agency) · **To**: Petros (Client) · Date: 2026-07-20\n"
    "Καλημέρα, στέλνω το recap της κλήσης.\n"
    "From: Petros · Date: 2026-07-21\nΕυχαριστώ, τα λέμε.\n"
)

RAW_RFP = "# RFP — Project Helios\nΖητούμενο: καμπάνια λανσαρίσματος, launch Μάρτιος 2027.\n"


def _write_raw(tmp_path, name, text):
    d = tmp_path / "raw"
    d.mkdir(exist_ok=True)
    (d / name).write_text(text, encoding="utf-8")
    return d


def test_intake_builds_a_folder_discover_sources_accepts(tmp_path):
    raw = _write_raw(tmp_path, "kickoff_call.txt", RAW_TRANSCRIPT)
    _write_raw(tmp_path, "mails_helios.txt", RAW_EMAIL)
    _write_raw(tmp_path, "rfp_helios.md", RAW_RFP)
    out = tmp_path / "project"

    items = intake.plan_intake(sorted(raw.glob("*")), {}, {})
    intake.write_project(items, out, force=False)

    sources = gates.discover_sources(out)
    assert {s.source_type for s in sources} == {"transcript", "email_thread", "rfp"}
    assert all(s.source_id and s.source_date for s in sources)


def test_email_date_is_read_from_the_document(tmp_path):
    raw = _write_raw(tmp_path, "mails_helios.txt", RAW_EMAIL)
    (item,) = intake.plan_intake([raw / "mails_helios.txt"], {}, {})
    assert item.source_date == "2026-07-20"
    assert item.date_provenance == "found in document"


def test_ambiguous_file_is_refused_not_guessed(tmp_path):
    raw = _write_raw(tmp_path, "notes.txt", "κάτι γενικό χωρίς δομή\n")
    with pytest.raises(intake.IntakeError, match="cannot infer source_type"):
        intake.plan_intake([raw / "notes.txt"], {}, {})


def test_explicit_type_override_wins(tmp_path):
    raw = _write_raw(tmp_path, "notes.txt", "κάτι γενικό χωρίς δομή\n")
    (item,) = intake.plan_intake([raw / "notes.txt"], {"notes.txt": "background"}, {})
    assert item.source_type == "background"


def test_already_compliant_file_passes_through_unchanged(tmp_path):
    text = "# Doc\nsource_id: legacy · source_type: rfp · source_date: 2026-01-01\n\nbody\n"
    raw = _write_raw(tmp_path, "legacy.md", text)
    (item,) = intake.plan_intake([raw / "legacy.md"], {}, {})
    assert item.already_compliant and item.source_id == "legacy"
    out = tmp_path / "project"
    intake.write_project([item], out, force=False)
    assert (out / "legacy.md").read_text(encoding="utf-8") == text


def test_greek_filename_slugs_or_refuses(tmp_path):
    raw = _write_raw(tmp_path, "πρακτικά.txt", RAW_TRANSCRIPT)
    with pytest.raises(intake.IntakeError, match="rename the file"):
        intake.plan_intake([raw / "πρακτικά.txt"], {}, {})


def test_glossary_scaffold_validates_the_tier(tmp_path):
    with pytest.raises(gates.ScopeError, match="out of MVP scope"):
        intake.scaffold_glossary(tmp_path / "acme.json", "acme", "S2")


def test_glossary_scaffold_writes_once_and_never_mutates_tier(tmp_path):
    path = tmp_path / "acme.json"
    assert intake.scaffold_glossary(path, "acme", "S1") is True
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["client_id"] == "acme" and payload["sensitivity_tier"] == "S1"
    assert intake.scaffold_glossary(path, "acme", "S1") is False  # untouched
    with pytest.raises(intake.IntakeError, match="refusing to change"):
        intake.scaffold_glossary(path, "acme", "S0")


def test_nonempty_out_dir_requires_force(tmp_path):
    raw = _write_raw(tmp_path, "rfp_x.md", RAW_RFP)
    out = tmp_path / "project"
    out.mkdir()
    (out / "existing.md").write_text("x", encoding="utf-8")
    items = intake.plan_intake([raw / "rfp_x.md"], {}, {})
    with pytest.raises(intake.IntakeError, match="--force"):
        intake.write_project(items, out, force=False)
