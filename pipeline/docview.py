"""Styled document views — brief_el.md / brief_en.md rendered as pleasant HTML.

The two rendered brief documents are the client-facing artifacts, but raw markdown is
not a reading experience. This module gives each one a styled, print-ready HTML view
(`brief_el.html` / `brief_en.html`) in the same design language as the review pages.

Same rules as every view in this repo: deterministic, zero model calls, self-contained
output, and escape-first — the markdown is model-authored, so every line is HTML-escaped
BEFORE any styling transform touches it. The renderer speaks exactly the grammar the
render stage emits (templates/northlight_client_brief.md): h1/h2 headings, blockquotes,
bold, bullet lists, numbered lists with indented continuation lines, and [source §loc]
citation brackets. Anything else stays a plain escaped paragraph — never dropped.

Usage:
    python3 pipeline/docview.py runs/<id>    # emits brief_el.html / brief_en.html
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python3 pipeline/docview.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import THEME_CSS, ReviewInputError

#: source markdown name → (output name, html lang tag)
DOCUMENTS = (("brief_el.md", "brief_el.html", "el"), ("brief_en.md", "brief_en.html", "en"))

_CITE_RE = re.compile(r"\[([^\[\]]+)\]")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_OL_RE = re.compile(r"^(\d+)\.\s+(.*)$")

_DOC_CSS = """
main.doc { max-width: 46rem; margin: 0 auto; padding: 2.6rem 1.5rem 3.5rem; }
.doc h1 { margin: 0 0 1rem; font-size: 1.75rem; font-weight: 700; line-height: 1.2;
  text-wrap: balance; }
.doc h2 { margin: 2.2rem 0 0.7rem; font-size: 1.18rem; font-weight: 700;
  padding-top: 1.1rem; border-top: 1px solid var(--line); }
.doc p { margin: 0.6rem 0; }
.doc blockquote { margin: 0.7rem 0; padding: 0.65rem 1rem; border-left: 3px solid var(--line);
  background: var(--bg-soft); border-radius: 0 10px 10px 0; color: var(--ink-2);
  font-style: italic; }
.doc ul, .doc ol { margin: 0.6rem 0; padding-left: 1.4rem; }
.doc li { margin: 0.45rem 0; }
.doc ol > li { margin: 0.9rem 0; }
.doc .cont { display: block; margin-top: 0.35rem; }
.doc .cite { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 0.72rem;
  color: var(--ink-2); background: var(--bg-soft); border-radius: 6px;
  padding: 0.08rem 0.35rem; white-space: nowrap; }
.doc strong { font-weight: 700; }
footer p { max-width: 46rem; margin: 0 auto; padding: 1rem 1.5rem; color: var(--ink-2);
  font-size: 0.8rem; }
footer { border-top: 1px solid var(--line); background: var(--bg-soft); }
@media print {
  main.doc { padding: 0; }
  .doc h2 { break-after: avoid; }
  .doc li, .doc blockquote { break-inside: avoid; }
}
"""


def _inline(text: str, cites: bool = True) -> str:
    """Inline transforms on an ALREADY-ESCAPED line: bold and citation chips."""
    text = _BOLD_RE.sub(r"<strong>\1</strong>", text)
    if cites:
        text = _CITE_RE.sub(r'<span class="cite">[\1]</span>', text)
    return text


def render_document(md_text: str, lang: str = "el") -> str:
    """Pure function: one rendered-brief markdown document in, styled HTML out."""
    out: list[str] = []
    mode = None  # None | "ul" | "ol" | "quote" | "p"
    title = "Client brief"

    def close() -> None:
        nonlocal mode
        if mode == "ul":
            out.append("</ul>")
        elif mode == "ol":
            out.append("</ol>")
        elif mode == "quote":
            out.append("</blockquote>")
        elif mode == "p":
            out.append("</p>")
        mode = None

    for raw_line in md_text.splitlines():
        stripped = raw_line.strip()
        line = html.escape(stripped, quote=True)
        if not stripped:
            close()
        elif stripped.startswith("# "):
            close()
            title = html.escape(stripped[2:], quote=True)
            out.append(f"<h1>{_inline(line[len('# '):], cites=False)}</h1>")
        elif stripped.startswith("## "):
            close()
            out.append(f"<h2>{_inline(line[len('## '):], cites=False)}</h2>")
        elif stripped.startswith("> "):
            if mode != "quote":
                close()
                out.append("<blockquote>")
                mode = "quote"
            out.append(f"<p>{_inline(line[len('&gt; '):])}</p>")
        elif stripped.startswith("- "):
            if mode != "ul":
                close()
                out.append("<ul>")
                mode = "ul"
            out.append(f"<li>{_inline(line[len('- '):])}</li>")
        elif _OL_RE.match(stripped):
            number, rest = _OL_RE.match(stripped).groups()
            if mode != "ol":
                close()
                out.append("<ol>")
                mode = "ol"
            out.append(f'<li value="{number}">{_inline(html.escape(rest, quote=True))}</li>')
        elif raw_line.startswith("   ") and mode == "ol" and out and out[-1].endswith("</li>"):
            # Indented continuation of the current numbered item (gap / why / question).
            out[-1] = out[-1][: -len("</li>")] + f'<span class="cont">{_inline(line)}</span></li>'
        else:
            if mode != "p":
                close()
                out.append("<p>")
                mode = "p"
            else:
                out.append("<br>")
            out.append(_inline(line))
    close()

    body = "".join(out)
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="{html.escape(lang, quote=True)}">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{title}</title>\n"
        f"<style>{THEME_CSS}{_DOC_CSS}</style>\n</head>\n<body>\n"
        f'<main class="doc">{body}</main>\n'
        "<footer><p>"
        + (
            "Παρήχθη ντετερμινιστικά από το αντίστοιχο έγγραφο markdown — ίδιο "
            "περιεχόμενο, μορφοποιημένο για ανάγνωση."
            if lang == "el"
            else "Generated deterministically from the matching markdown document — "
            "same content, typeset for reading."
        )
        + "</p></footer>\n</body>\n</html>\n"
    )


def write_documents(run_dir) -> list[Path]:
    """Emit a styled view for each rendered document present; return the paths.

    A run that never reached the render stage has no documents — empty list, no error.
    """
    run_dir = Path(run_dir)
    written = []
    for md_name, html_name, lang in DOCUMENTS:
        md_path = run_dir / md_name
        if not md_path.is_file():
            continue
        out_path = run_dir / html_name
        out_path.write_text(
            render_document(md_path.read_text(encoding="utf-8"), lang), encoding="utf-8"
        )
        written.append(out_path)
    return written


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Emit styled HTML views of a run's rendered brief documents."
    )
    parser.add_argument("run_dir", help="run directory containing brief_el.md / brief_en.md")
    args = parser.parse_args(argv)
    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print(f"docview: no such run directory: {run_dir}", file=sys.stderr)
        return 1
    written = write_documents(run_dir)
    if not written:
        print(
            f"docview: no brief_el.md / brief_en.md in {run_dir} — the styled views "
            "render the documents the render stage produced; run it first",
            file=sys.stderr,
        )
        return 1
    for path in written:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
