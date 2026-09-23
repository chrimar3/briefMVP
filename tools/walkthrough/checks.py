"""Deterministic gate for WALKTHROUGH.html (or --file <path>). Exit 0 = all green, 1 = failures (printed).

Usage: python3 tools/walkthrough/checks.py [--file PAGE]
The report is JSON on stdout: sheet count, blockquote count and the list of failures.
"""
from __future__ import annotations

import argparse
import collections
import html
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unicodedata
from html.parser import HTMLParser

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repo root, wherever it is cloned
DEFAULT_PAGE = ROOT / 'WALKTHROUGH.html'
FIXTURE = ROOT / 'fixtures/northlight_01'
CORPUS_FILES = ('transcript_kickoff.md', 'rfp_meltemi.md', 'emails_thread.md', 'background_brand_guidelines.md')
KV_PALETTE = ('#1B4F8A', '#F5C518', '#FFFFFF')
STALE_CREATIVE_CLAIMS = (
    'never delivered',
    'nothing delivered',
    'no delivered creative',
    'v1.1 takes creative live',
    'creative stays in shadow',
    'covers shadow evaluation only',
    'schema-validated edit in v1',
)
EVIDENCE_BLOCKS = ('hero', 'brief', 'exam', 'numbers', 'decisions', 'limits', 'takeaways', 'flow')


def load_corpus(fixture: pathlib.Path = FIXTURE) -> str:
    """The four northlight_01 sources, NFC-normalised, with markdown bold markers removed."""
    text = ''.join((fixture / f).read_text(encoding='utf-8') for f in CORPUS_FILES)
    return unicodedata.normalize('NFC', text.replace('**', ''))


def text_of(fragment: str) -> str:
    """Visible text of an HTML fragment: tags and the `sic` marker removed, entities decoded, NFC."""
    t = re.sub(r'<span class="sic">sic</span>', '', fragment)
    t = re.sub(r'<[^>]+>', '', t)
    return unicodedata.normalize('NFC', html.unescape(t)).strip()


class TagBalance(HTMLParser):
    """Stack-based open/close tag matcher (void elements excluded)."""

    VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'line', 'rect', 'circle', 'use', 'path'}

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.err: list[tuple[str, tuple[int, int]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Push every non-void start tag."""
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        """Pop a matching end tag, record a mismatch otherwise."""
        if tag in self.VOID:
            return
        if self.stack and self.stack[-1] == tag:
            self.stack.pop()
        else:
            self.err.append((tag, self.getpos()))


def check_verbatim(doc: str, corpus: str) -> tuple[list[str], int]:
    """1: every blockquote and cited anchor is verbatim in the fixture corpus; returns (failures, quote count)."""
    fails = []
    quotes = re.findall(r'<blockquote[^>]*>(.*?)</blockquote>', doc, flags=re.S)
    for q in quotes:
        t = text_of(q)
        if t.strip('…. ').replace('’', "'") not in corpus.replace('’', "'"):
            fails.append(f'blockquote not verbatim in fixtures: {t[:80]}')
    for a in re.findall(r'<mark class="cited">(.*?)</mark>', doc, flags=re.S):
        if text_of(a) not in corpus:
            fails.append(f'cited anchor not in source: {text_of(a)[:80]}')
    return fails, len(quotes)


def check_dependencies(doc: str) -> list[str]:
    """2: zero external resources."""
    fails = [f'external resource: {u}' for u in re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', doc)]
    if re.search(r'<link\b', doc):
        fails.append('<link> tag present')
    if re.search(r'@import|url\(', doc):
        fails.append('CSS @import/url() present')
    return fails


def check_structure(doc: str) -> tuple[list[str], int]:
    """3: sheet numbering, folios, contents array, unique ids, resolvable anchors; returns (failures, sheet count)."""
    fails = []
    sheets = re.findall(r'<section class="sheet[^"]*" id="ch(\d\d)" data-n="(\d+)"', doc)
    n = len(sheets)
    if n > 10:
        fails.append(f'{n} sheets (max 10)')
    if [int(a) for a, _ in sheets] != list(range(1, n + 1)) or [int(b) for _, b in sheets] != list(range(1, n + 1)):
        fails.append(f'sheet numbering not 1..{n}: {sheets}')
    for i in range(1, n + 1):
        if f'id="t{i:02d}"' not in doc:
            fails.append(f'missing title id t{i:02d}')
    fol = set(re.findall(r'(\d\d) / (\d\d) &middot; Contents', doc))
    if any(int(tot) != n for _, tot in fol):
        fails.append(f'folio totals disagree with sheet count {n}: {sorted(fol)}')
    m = re.search(r"var CH = \[(.*?)\n  \];", doc, flags=re.S)
    if not m or m.group(1).count("t: '") != n:
        fails.append('CH array length != sheet count')
    ids = re.findall(r'\sid="([^"]+)"', doc)
    for i, c in collections.Counter(ids).items():
        if c > 1:
            fails.append(f'duplicate id {i}')
    for r in set(re.findall(r'href="#([^"]+)"', doc)) | set(re.findall(r"getElementById\('([^']+)'\)", doc)):
        if r not in ids:
            fails.append(f'reference to missing id #{r}')
    for f in re.findall(r'<figure[^>]*>(.*?)</figure>', doc, flags=re.S):
        if '<figcaption' in f and f[f.index('</figcaption>') + 13:].strip():
            fails.append('figcaption not last child of figure')
    if not re.search(r'<!DOCTYPE html>', doc, flags=re.I):
        fails.append('missing doctype')
    return fails, n


def check_scripts(doc: str) -> list[str]:
    """4: every inline script parses (`node --check`)."""
    fails = []
    for i, sc in enumerate(re.findall(r'<script>(.*?)</script>', doc, flags=re.S)):
        p = pathlib.Path(tempfile.gettempdir()) / f'walkthrough_s{i}.js'
        p.write_text(sc)
        try:
            r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
        except FileNotFoundError:
            fails.append('node is not installed: inline scripts cannot be syntax-checked')
            break
        if r.returncode != 0:
            fails.append(f'script {i} syntax: {r.stderr[:160]}')
    return fails


def check_tag_balance(doc: str) -> list[str]:
    """5: open and close tags balance."""
    p = TagBalance()
    p.feed(doc)
    return [f'unbalanced tags: {p.err[:3]} open={p.stack[:5]}'] if p.err or p.stack else []


def check_word_budget(doc: str) -> list[str]:
    """6: action titles at most 24 words, takeaways at most 20."""
    fails = []
    for mt in re.finditer(r'<h1 class="title action"[^>]*>(.*?)</h1>', doc, flags=re.S):
        w = len(text_of(mt.group(1)).split())
        if w > 24:
            fails.append(f'action title {w} words (max 24): {text_of(mt.group(1))[:60]}')
    for mu in re.finditer(r'<ul class="takeaways">(.*?)</ul>', doc, flags=re.S):
        for li in re.findall(r'<li>(.*?)</li>', mu.group(1), flags=re.S):
            w = len(text_of(li).split())
            if w > 20:
                fails.append(f'takeaway {w} words (max 20): {text_of(li)[:60]}')
    return fails


def plain_text(doc: str) -> str:
    """Decoded page text with struck or flagged passages removed (they are exempt from the X3 rule)."""
    return html.unescape(re.sub(r'<(?:s|mark class="flag")>.*?</(?:s|mark)>', '', doc, flags=re.S))


def kv_art(doc: str) -> str | None:
    """The key-visual SVG group, or None when the page lost it."""
    g = re.search(r'<g id="kv-art">(.*?)</g>\s*</defs>', doc, flags=re.S)
    return g.group(1) if g else None


def check_key_visual(art: str | None) -> list[str]:
    """7: palette, wordmark and its clear space; 8b: no opacity compositing, mock-up label inside the 9:16 crop."""
    if art is None:
        return ['key visual <g id="kv-art"> missing']
    fails = []
    if 'gradient' in art.lower():
        fails.append('gradient in key visual')
    for hexv in re.findall(r'(?:fill|stroke)="(#[0-9A-Fa-f]{6})"', art):
        if hexv.upper() not in KV_PALETTE:
            fails.append(f'off-palette colour in key visual {hexv}')
    if 'Meltemi Fizz' not in art:
        fails.append('wordmark missing from key visual')
    wm = re.search(r'<text x="1280" y="(\d+)"[^>]*font-size="(\d+)"[^>]*>Meltemi Fizz', art)
    if wm:
        base, fs = int(wm.group(1)), int(wm.group(2))
        top = base - round(fs * 0.72)
        zone = (top - fs, base + fs)  # em-box reading of 'height of the wordmark'
        for cm in re.finditer(r'<circle cx="(\d+)" cy="(\d+)" r="(\d+)"', art):
            cx, cy, r = map(int, cm.groups())
            r2 = r + 5
            if cy + r2 > zone[0] and cy - r2 < zone[1] and cx + r2 > 825 and cx - r2 < 1735:
                fails.append(f'clear-space intrusion: circle {cx},{cy},{r}')
        tag = re.search(r'<text x="1280" y="(\d+)"[^>]*font-size="(\d+)"[^>]*>SPARKLING', art)
        if tag and int(tag.group(1)) - round(int(tag.group(2)) * 0.72) < zone[1]:
            fails.append('tagline inside wordmark clear space')
    return fails


def check_kv_label(art: str | None) -> list[str]:
    """8b: no opacity compositing (strict three-colour rule), mock-up label inside the 9:16 crop."""
    if art is None:
        return []
    fails = []
    if re.search(r'(stroke-)?opacity=', art):
        fails.append('opacity attribute in key visual (composites an off-palette tint)')
    lab = re.search(
        r'<text x="(\d+)" y="(\d+)"[^>]*text-anchor="(\w+)"[^>]*font-size="(\d+)"'
        r'[^>]*letter-spacing="(\d+)"[^>]*>MOCK-UP',
        art,
    )
    if not lab:
        return [*fails, 'mock-up label missing from key visual']
    x, anchor, fs, ls = int(lab.group(1)), lab.group(3), int(lab.group(4)), int(lab.group(5))
    width = 26 * (0.62 * fs + ls)
    left = x - width / 2 if anchor == 'middle' else x
    if left < 740 or left + width > 1820:
        fails.append(f'mock-up label leaves the 9:16 crop (x {left:.0f}..{left + width:.0f})')
    return fails


def check_budget_total(plain: str) -> list[str]:
    """7 (X3): no budget total presented as a fact; entities are decoded first, so encoding cannot hide a figure."""
    if re.search(r'€\s?8[0-5][,.]?\d{3}|\b8[0-5],000\b|\b8[0-5]k\b', plain):
        return ['a numeric budget total appears (X3)']
    return []


def check_creative_scope(doc: str, plain: str) -> list[str]:
    """7/7b: shadow-mode notice; no superseded shadow-only claims; the approval-gated release is stated."""
    fails = []
    if 'SHADOW MODE' not in doc:
        fails.append('shadow-mode notice missing')
    for stale in STALE_CREATIVE_CLAIMS:
        if stale in plain:
            fails.append(f'superseded creative/sign-off claim on the page: {stale!r}')
    if 'approves the exact files' not in plain:
        fails.append('creative release rule (a named creative lead approves the exact files) missing')
    if 'pipeline.agency resolve, attest and approve' not in plain:
        fails.append('Tier 5 sign-off commands missing from the sign-off description')
    return fails


def check_sheet_words(doc: str) -> list[str]:
    """8a: visible-word budget per sheet (details excluded): hard cap 650, sheet 09 allowed 750."""
    fails = []
    for ms in re.finditer(r'<section class="sheet[^"]*" id="(ch\d\d)"(.*?)</section>', doc, flags=re.S):
        vis = re.sub(r'<details.*?</details>', '', ms.group(2), flags=re.S)
        w = len(text_of(vis).split())
        cap = 750 if ms.group(1) == 'ch09' else 650
        if w > cap:
            fails.append(f'{ms.group(1)} has {w} visible words (cap {cap})')
    return fails


def check_decisions(doc: str) -> list[str]:
    """8c: exactly three top-level decisions, counter scoped to them."""
    dec = re.search(r'<ol class="decisions">(.*?)</ol>', doc, flags=re.S)
    if not dec:
        return []
    fails = []
    top = len(re.findall(r'\n        <li>', dec.group(1)))
    if top != 3:
        fails.append(f'{top} top-level decisions (expected 3)')
    if '.decisions > li { ' not in doc and '.decisions > li {' not in doc:
        fails.append('decision counter not scoped to .decisions > li')
    return fails


def check_empty_blocks(doc: str) -> list[str]:
    """8: regression guards: no empty evidence containers."""
    fails = []
    for pg in re.findall(r'<div class="page" lang="(?:el|en)">(.*?)\n        </div>', doc, flags=re.S):
        if pg.count('<h4>') < 2:
            fails.append('facing page has fewer than 2 sections')
    for cls in EVIDENCE_BLOCKS:
        pattern = r'<(?:div|ul|ol|article) class="' + cls + r'[^"]*">(.*?)</(?:div|ul|ol|article)>'
        for m2 in re.finditer(pattern, doc, flags=re.S):
            if len(text_of(m2.group(1)).split()) < 3:
                fails.append(f'empty .{cls} block')
    return fails


def run_checks(doc: str, corpus: str) -> dict:
    """Every check, in the historical order; returns the JSON report (sheets, blockquotes, failures)."""
    verbatim, n_quotes = check_verbatim(doc, corpus)
    structure, n_sheets = check_structure(doc)
    art = kv_art(doc)
    plain = plain_text(doc)
    fails = [
        *verbatim,
        *check_dependencies(doc),
        *structure,
        *check_scripts(doc),
        *check_tag_balance(doc),
        *check_word_budget(doc),
        *check_budget_total(plain),
        *check_key_visual(art),
        *check_creative_scope(doc, plain),
        *check_sheet_words(doc),
        *check_kv_label(art),
        *check_decisions(doc),
        *check_empty_blocks(doc),
    ]
    return {'sheets': n_sheets, 'blockquotes': n_quotes, 'failures': fails}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the JSON report; exit 1 on any failure or an unreadable page."""
    ap = argparse.ArgumentParser(description='Deterministic gate for WALKTHROUGH.html.')
    ap.add_argument('--file', type=pathlib.Path, default=DEFAULT_PAGE, help='page to check (default: WALKTHROUGH.html)')
    args = ap.parse_args(argv)
    try:
        doc = args.file.resolve().read_text(encoding='utf-8')
        corpus = load_corpus()
    except OSError as exc:
        print(f'checks: {exc}', file=sys.stderr)
        return 1
    report = run_checks(doc, corpus)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report['failures'] else 0


if __name__ == '__main__':
    sys.exit(main())
