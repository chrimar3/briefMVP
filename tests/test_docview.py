"""The styled document views typeset brief_el.md / brief_en.md — the client-facing
documents — without becoming an author: escape-first, every line of the markdown must
survive into the HTML, and the page carries no script at all. Deterministic, zero
model calls.
"""

from __future__ import annotations

import html
import re
from pathlib import Path

import pytest

from pipeline import docview

REPO = Path(__file__).resolve().parents[1]

_SAMPLE = """# Acme — Client Brief [EL]

> **DRAFT** pending sign-off

**Client:** Acme · **Project:** p_01

## 1. Objectives
- Grow awareness before summer. [rfp_acme §2]
- Enter the category with force. [transcript 00:02:05]

## 2. Audiences
> No confirmed entries — see Open Questions.

## ⚠ Open Questions
1. **Budget — no figure.** Gap: no amount was stated. [rfp_acme §6]
   Why it matters: everything downstream depends on it.
   Suggested question: «What is the final amount?»
2. **KPIs missing.** Gap: no metrics agreed. [transcript 00:05:00]
"""


def _segments(md_text: str):
    """Every human-readable chunk of the markdown, split where the renderer transforms:
    block prefixes, bold markers, citation brackets."""
    for line in md_text.splitlines():
        stripped = line.strip()
        stripped = re.sub(r"^(#+\s+|>\s+|-\s+|\d+\.\s+)", "", stripped)
        for piece in re.split(r"\*\*|\[[^\[\]]+\]", stripped):
            piece = piece.strip()
            if len(piece) > 3:
                yield piece


def test_every_markdown_line_survives_into_the_view():
    """The view typesets; it never drops. Checked on the sample and on the real
    committed Greek document."""
    for md_text in (_SAMPLE, (REPO / "runs/tier3/brief_el.md").read_text(encoding="utf-8")):
        page = docview.render_document(md_text, "el")
        for segment in _segments(md_text):
            assert html.escape(segment, quote=True) in page, f"dropped: {segment[:60]!r}"


def test_structure_is_typeset_not_dropped():
    page = docview.render_document(_SAMPLE, "el")
    assert "<h1>Acme — Client Brief [EL]</h1>" in page
    assert "<h2>1. Objectives</h2>" in page
    assert "<strong>Client:</strong>" in page
    assert "<blockquote>" in page
    assert '<span class="cite">[rfp_acme §2]</span>' in page
    assert '<li value="2">' in page  # numbering preserved from the document


def test_numbered_item_continuations_stay_inside_their_item():
    """The gap / why-it-matters / suggested-question lines are indented continuations
    of one question — splitting them into separate items would garble the list."""
    page = docview.render_document(_SAMPLE, "el")
    first_item = re.search(r'<li value="1">(.*?)</li>', page, re.S).group(1)
    assert "Why it matters" in first_item
    assert "«What is the final amount?»" in first_item
    assert page.count("<ol>") == 1


def test_markdown_script_tags_arrive_escaped_and_the_page_has_no_script_at_all():
    """The document is model-authored; the view is pure typesetting — it ships zero
    JavaScript, so nothing in the markdown can ever execute."""
    payload = "<script>alert(1)</script>"
    page = docview.render_document(f"# T\n\n- {payload}\n", "en")
    assert payload not in page
    assert "<script" not in page
    assert html.escape(payload) in page


def test_language_lands_on_the_root_element():
    assert '<html lang="el">' in docview.render_document(_SAMPLE, "el")
    assert '<html lang="en">' in docview.render_document(_SAMPLE, "en")


def test_render_is_deterministic():
    md_text = (REPO / "runs/tier3/brief_el.md").read_text(encoding="utf-8")
    assert docview.render_document(md_text, "el") == docview.render_document(md_text, "el")


def test_write_documents_emits_a_view_per_present_document(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief_el.md").write_text(_SAMPLE, encoding="utf-8")
    written = docview.write_documents(run_dir)
    assert [p.name for p in written] == ["brief_el.html"]
    assert (run_dir / "brief_el.html").read_text(encoding="utf-8") == docview.render_document(
        _SAMPLE, "el"
    )


def test_runs_without_documents_write_nothing(tmp_path):
    """Extraction-only and refused runs have no renders — quiet no-op, not an error."""
    empty = tmp_path / "run"
    empty.mkdir()
    assert docview.write_documents(empty) == []


def test_cli_prints_paths_and_fails_legibly(tmp_path, capsys):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / "brief_en.md").write_text("# T\n\n- x. [s §1]\n", encoding="utf-8")
    assert docview.main([str(run_dir)]) == 0
    assert "brief_en.html" in capsys.readouterr().out
    empty = tmp_path / "empty"
    empty.mkdir()
    assert docview.main([str(empty)]) == 1
    assert "brief_el.md" in capsys.readouterr().err
