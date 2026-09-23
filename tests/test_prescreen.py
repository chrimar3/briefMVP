"""Advisory personal-data pre-screen (pipeline/prescreen.py). Synthetic strings only; no model calls.

The screen reports where to look (file, category, line numbers, counts) and never what it
found, and it never blocks: those two properties are what these tests pin."""

import json

import pytest

from pipeline import prescreen

SYNTHETIC_EMAIL = "synthetic.person@example.invalid"
SYNTHETIC_PHONE = "+30 210 000 0000"
SYNTHETIC_IBAN = "GR00 0000 0000 0000 0000 0000 000"


def _project(tmp_path, files):
    project = tmp_path / "project"
    project.mkdir()
    for name, text in files.items():
        (project / name).write_text(text, encoding="utf-8")
    return project


def _counts(text):
    return {k: v["count"] for k, v in prescreen.scan_text(text).items()}


@pytest.mark.parametrize("text, category", [
    (f"Contact: {SYNTHETIC_EMAIL}", "email_address"),
    (f"Τηλ. {SYNTHETIC_PHONE}", "phone_number"),
    ("κινητό 6900000000", "phone_number"),
    ("γραφείο 210-000-0000", "phone_number"),
    (f"IBAN {SYNTHETIC_IBAN}", "iban_like"),
    ("Η συνθετική συμμετέχουσα είναι έγκυος.", "health"),
    ("Ο ΑΣΘΕΝΗΣ δεν ήρθε.", "health"),  # capitals, no accents
    ("A synthetic participant mentioned a diagnosis.", "health"),
    ("θρησκευτικές πεποιθήσεις", "religious_or_philosophical_beliefs"),
    ("συνδικαλιστής της εταιρείας", "trade_union_membership"),
    ("ποινικό μητρώο", "criminal_offences"),
    ("data about a child", "children"),
])
def test_each_category_is_detected(text, category):
    assert _counts(text).get(category, 0) >= 1, (text, _counts(text))


@pytest.mark.parametrize("text", [
    "**Message 1** · From: Synthetic A · Date: 2026-07-11 09:40",  # ISO date + time
    "[00:03:41] SPEAKER: launch plan",                              # transcript timestamp
    "budget 250000 EUR, reach 1134734 tokens",                      # plain figures
    "Approval DP-SYNTH-001 on 2026-09-01",                          # approval reference and date
    "πολιτική επιστροφών και παιδική σειρά προϊόντων",               # 'policy', a product line
    "μπραντ αγουέρνες",                                             # a garbled ASR token
])
def test_ordinary_brief_text_is_not_flagged(text):
    assert _counts(text) == {}


def test_an_iban_is_counted_once_not_also_as_a_phone():
    assert _counts(f"IBAN {SYNTHETIC_IBAN}") == {"iban_like": 1}


def test_report_carries_locations_never_values(tmp_path):
    project = _project(tmp_path, {
        "emails.md": f"line one\nFrom: {SYNTHETIC_EMAIL}\nCall {SYNTHETIC_PHONE}\nΗ συμμετέχουσα είναι έγκυος\n",
        "rfp.md": "Nothing personal here.\n",
    })
    report = prescreen.scan(project)
    assert report["advisory"] is True and report["blocking"] is False
    assert report["scanned_files"] == 2 and report["sources_with_findings"] == 1
    emails = next(s for s in report["sources"] if s["file"] == "emails.md")["findings"]
    assert emails["email_address"] == {"count": 1, "lines": [2]}
    assert emails["phone_number"] == {"count": 1, "lines": [3]}
    assert emails["health"] == {"count": 1, "lines": [4]}
    assert report["totals"] == {"email_address": 1, "health": 1, "phone_number": 1}
    text = json.dumps(report, ensure_ascii=False)
    for value in (SYNTHETIC_EMAIL, "210 000 0000", "έγκυος", "εγκυ"):
        assert value not in text


def test_answer_key_and_non_text_files_are_not_scanned(tmp_path):
    project = _project(tmp_path, {
        "answer_key.json": json.dumps({"note": SYNTHETIC_EMAIL}),
        "data_declaration.json": '{"data_class": "synthetic"}',
        "source.md": "clean",
    })
    report = prescreen.scan(project)
    assert [s["file"] for s in report["sources"]] == ["source.md"]
    assert report["totals"] == {}


def test_answer_key_names_come_from_the_gates_constant(monkeypatch, tmp_path):
    monkeypatch.setattr(prescreen.gates, "HARNESS_ONLY_FILES", ("answer_key.json", "sealed.md"))
    project = _project(tmp_path, {"sealed.md": SYNTHETIC_EMAIL, "source.md": "clean"})
    assert [s["file"] for s in prescreen.scan(project)["sources"]] == ["source.md"]


def test_unreadable_file_is_listed_not_fatal(tmp_path):
    project = _project(tmp_path, {"ok.md": "clean"})
    (project / "broken.md").write_bytes(b"\xff\xfe\x00bad")
    report = prescreen.scan(project)
    assert report["unreadable"] == [{"file": "broken.md", "reason": "UnicodeDecodeError"}]
    assert report["scanned_files"] == 1


def test_missing_folder_is_an_error(tmp_path):
    with pytest.raises(FileNotFoundError):
        prescreen.scan(tmp_path / "absent")
    assert prescreen.main([str(tmp_path / "absent")]) == 2


def test_cli_exits_zero_whatever_it_finds(tmp_path, capsys):
    project = _project(tmp_path, {"emails.md": f"From: {SYNTHETIC_EMAIL}"})
    out = tmp_path / "report.json"
    assert prescreen.main([str(project), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["totals"] == {"email_address": 1}
    assert SYNTHETIC_EMAIL not in capsys.readouterr().out


def test_term_list_loads_and_every_category_has_terms(repo_root):
    terms = prescreen.load_terms()
    payload = json.loads((repo_root / "config" / "prescreen_terms.json").read_text(encoding="utf-8"))
    assert set(terms) == set(payload["categories"])
    assert {"health", "religious_or_philosophical_beliefs", "trade_union_membership",
            "criminal_offences", "children"} <= set(terms)
    assert "Advisory" in payload["_status"]


def test_graded_fixtures_screen_clean(repo_root):
    """The two graded synthetic fixtures carry no contact identifiers or special-category terms,
    so the screen adds no noise to them. Named explicitly: sealed fixtures are never scanned."""
    for name in ("northlight_01", "voreas_02"):
        report = prescreen.scan(repo_root / "fixtures" / name)
        assert report["scanned_files"] >= 4 and report["totals"] == {}, (name, report["totals"])
