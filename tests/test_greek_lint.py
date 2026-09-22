"""Render-stage language lint (r1-W4) — warnings for the human language review, never a block.

Synthetic sentences only. Each rule is tested both ways: the error pattern is reported, and the
correct form (or a legitimate look-alike) is not.
"""

import pytest

from pipeline import stages

GLOSSARY = {"terms": [{"term": "Aurora Foods", "rule": "keep_latin", "note": "Company name."},
                      {"term": "Aurora Bloom", "rule": "keep_latin", "note": "Product name."}]}
BRIEF = {"objectives": [{"content": "x", "evidence": [{"source_id": "call", "location": "00:01:00",
                                                       "anchor": "σήμερα το είπαμε, τη κατηγορία την ξέρουμε",
                                                       "speaker_or_author": "Synthetic"}]}]}


def _lint(tmp_path, el="", en=""):
    (tmp_path / "el.md").write_text(el, encoding="utf-8")
    (tmp_path / "en.md").write_text(en, encoding="utf-8")
    return stages.render_language_warnings(tmp_path / "el.md", tmp_path / "en.md", BRIEF, GLOSSARY)


@pytest.mark.parametrize("sentence", [
    "Χρειαζόμαστε τη τελική έγκριση.",
    "Ποιο είναι το εύρος για τη κατηγορία;",
    "Θα μπει δυναμικά στη αγορά.",
    "Το υλικό δε είναι έτοιμο.",
    "Ζητάμε να μη τεθεί ξανά.",
    "Περιμένουμε τη μπροσούρα.",
])
def test_missing_final_nu_is_reported(tmp_path, sentence):
    warnings = _lint(tmp_path, el=sentence)
    assert len(warnings) == 1 and "final ν" in warnings[0]


@pytest.mark.parametrize("sentence", [
    "Χρειαζόμαστε την τελική έγκριση.",
    "Περιμένουμε τη Δευτέρα.",
    "Τα στοιχεία είναι μη επιβεβαιωμένα.",  # negative prefix: correctly no ν
    "Δεν έχει οριστεί ημερομηνία.",
])
def test_correct_article_forms_are_not_reported(tmp_path, sentence):
    assert _lint(tmp_path, el=sentence) == []


@pytest.mark.parametrize("word", ["Ποιό", "ποιά", "πιό", "μιά"])
def test_accented_monosyllable_is_reported(tmp_path, word):
    warnings = _lint(tmp_path, el=f"{word} είναι το ζητούμενο;")
    assert any("takes no accent" in w for w in warnings)


def test_correct_monosyllables_and_the_numeral_are_not_reported(tmp_path):
    assert _lint(tmp_path, el="Ποιο είναι πιο σημαντικό; Μία ή δύο εκδοχές.") == []


@pytest.mark.parametrize("question", [
    "Πόσα key visuals θα χρειαστούν και που θα χρησιμοποιηθούν;",
    "Που θα γίνει το launch;",
    "Προτεινόμενη ερώτηση: «Πως κατανέμεται ο προϋπολογισμός;»",
])
def test_unaccented_interrogative_in_a_question_is_reported(tmp_path, question):
    assert any("interrogative" in w for w in _lint(tmp_path, el=question))


@pytest.mark.parametrize("sentence", [
    "Ποια είναι τα κανάλια που θα χρησιμοποιηθούν;",  # relative pronoun
    "Το υλικό, που θα σταλεί αύριο το πρωί, είναι έτοιμο.",  # relative after a comma, not a question
    "Πού θα χρησιμοποιηθούν;",
])
def test_relative_pronoun_and_accented_interrogative_are_not_reported(tmp_path, sentence):
    assert not any("interrogative" in w for w in _lint(tmp_path, el=sentence))


def test_company_name_with_a_neuter_article_is_reported(tmp_path):
    warnings = _lint(tmp_path, el="Το Northlight θα στείλει πλάνο. Το Aurora Foods συμφωνεί.")
    assert sum("feminine article" in w for w in warnings) == 2


def test_company_with_feminine_article_and_product_with_neuter_are_not_reported(tmp_path):
    assert _lint(tmp_path, el="Η Northlight θα στείλει πλάνο για το Aurora Bloom.") == []


def test_calques_from_the_style_table_are_reported(tmp_path):
    warnings = _lint(tmp_path, el="Επιλύθηκαν οι αντικρούσεις. Ο εγκριτής δεν είναι γνωστός.")
    assert any("«αντικρούσεις» is on the avoid list" in w for w in warnings)
    assert any("«εγκριτής» is on the avoid list" in w for w in warnings)
    assert sum("avoid list" in w for w in warnings) == 2


def test_time_words_are_reported_in_both_languages(tmp_path):
    warnings = _lint(tmp_path, el="Προτεινόμενη ερώτηση: «Σήμερα ειπώθηκε κάτι άλλο.»",
                     en='Suggested question: "Today it was said otherwise."')
    assert any(w.startswith("el:") and "σήμερα" in w.lower() for w in warnings)
    assert any(w.startswith("en:") and "'today'" in w for w in warnings)


def test_verbatim_source_quotes_are_not_linted(tmp_path):
    """A quotation that is part of an evidence anchor is the speaker's own wording."""
    assert _lint(tmp_path, el="Είπε: «σήμερα το είπαμε, τη κατηγορία την ξέρουμε». [call 00:01:00]") == []


def test_widened_hedge_is_reported_in_english(tmp_path):
    warnings = _lint(tmp_path, en="Budget: somewhere in the sixties, units unstated.")
    assert len(warnings) == 1 and "decade range" in warnings[0]
    assert _lint(tmp_path, en="Budget: around sixty, units unstated.") == []


def test_citation_tags_are_not_linted(tmp_path):
    assert _lint(tmp_path, el="Ισχύει ο κανόνας. [call τη αγορά]") == []


def test_warnings_carry_language_and_line_number(tmp_path):
    warnings = _lint(tmp_path, el="Γραμμή ένα.\nΧρειαζόμαστε τη τελική έγκριση.")
    assert warnings[0].startswith("el:2:")


def test_missing_style_table_degrades_to_the_built_in_rules(tmp_path):
    (tmp_path / "el.md").write_text("Τη αρχή και οι αντικρούσεις.", encoding="utf-8")
    warnings = stages.render_language_warnings(tmp_path / "el.md", tmp_path / "none.md", {}, {}, style={})
    assert len(warnings) == 1 and "final ν" in warnings[0]


def test_shipped_style_table_is_well_formed():
    style = stages.load_greek_style()
    assert style["preferred_terms"] and all(t["avoid"] and t["el"] for t in style["preferred_terms"])
    assert {"el", "en"} <= set(style["temporal_deixis"])
    assert "Warnings only" in style["_status"]
