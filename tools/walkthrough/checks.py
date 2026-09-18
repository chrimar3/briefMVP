"""Deterministic gate for WALKTHROUGH.html (or --file <path>). Exit 0 = all green, 1 = failures (printed)."""
import re, html, pathlib, unicodedata, collections, subprocess, sys, json
ROOT = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder')
PAGE = ROOT / 'WALKTHROUGH.html'
if '--file' in sys.argv: PAGE = pathlib.Path(sys.argv[sys.argv.index('--file') + 1]).resolve()
doc = PAGE.read_text(encoding='utf-8')
fx = ROOT / 'fixtures/northlight_01'
corpus = unicodedata.normalize('NFC', ''.join((fx / f).read_text(encoding='utf-8') for f in
    ['transcript_kickoff.md', 'rfp_meltemi.md', 'emails_thread.md', 'background_brand_guidelines.md']).replace('**', ''))
fails = []
def text_of(f):
    t = re.sub(r'<span class="sic">sic</span>', '', f); t = re.sub(r'<[^>]+>', '', t)
    return unicodedata.normalize('NFC', html.unescape(t)).strip()

# 1 verbatim clippings and anchors
quotes = re.findall(r'<blockquote[^>]*>(.*?)</blockquote>', doc, flags=re.S)
for q in quotes:
    t = text_of(q)
    if t.strip('…. ').replace('’', "'") not in corpus.replace('’', "'"):
        fails.append(f'blockquote not verbatim in fixtures: {t[:80]}')
for a in re.findall(r'<mark class="cited">(.*?)</mark>', doc, flags=re.S):
    if text_of(a) not in corpus: fails.append(f'cited anchor not in source: {text_of(a)[:80]}')
# 2 zero dependencies
for u in re.findall(r'(?:src|href)=["\'](https?://[^"\']+)', doc): fails.append(f'external resource: {u}')
if re.search(r'<link\b', doc): fails.append('<link> tag present')
if re.search(r'@import|url\(', doc): fails.append('CSS @import/url() present')
# 3 structure
sheets = re.findall(r'<section class="sheet[^"]*" id="ch(\d\d)" data-n="(\d+)"', doc)
n = len(sheets)
if n > 10: fails.append(f'{n} sheets (max 10)')
if [int(a) for a, b in sheets] != list(range(1, n + 1)) or [int(b) for a, b in sheets] != list(range(1, n + 1)):
    fails.append(f'sheet numbering not 1..{n}: {sheets}')
for i in range(1, n + 1):
    if f'id="t{i:02d}"' not in doc: fails.append(f'missing title id t{i:02d}')
fol = set(re.findall(r'(\d\d) / (\d\d) &middot; Contents', doc))
if any(int(tot) != n for _, tot in fol): fails.append(f'folio totals disagree with sheet count {n}: {sorted(fol)}')
m = re.search(r"var CH = \[(.*?)\n  \];", doc, flags=re.S)
if not m or m.group(1).count("t: '") != n: fails.append('CH array length != sheet count')
ids = re.findall(r'\sid="([^"]+)"', doc)
for i, c in collections.Counter(ids).items():
    if c > 1: fails.append(f'duplicate id {i}')
for r in set(re.findall(r'href="#([^"]+)"', doc)) | set(re.findall(r"getElementById\('([^']+)'\)", doc)):
    if r not in ids: fails.append(f'reference to missing id #{r}')
for f in re.findall(r'<figure[^>]*>(.*?)</figure>', doc, flags=re.S):
    if '<figcaption' in f and f[f.index('</figcaption>') + 13:].strip(): fails.append('figcaption not last child of figure')
if not re.search(r'<!DOCTYPE html>', doc, flags=re.I): fails.append('missing doctype')
# 4 scripts parse
for i, sc in enumerate(re.findall(r'<script>(.*?)</script>', doc, flags=re.S)):
    import tempfile; p = pathlib.Path(tempfile.gettempdir()) / f'walkthrough_s{i}.js'; p.write_text(sc)
    r = subprocess.run(['node', '--check', str(p)], capture_output=True, text=True)
    if r.returncode != 0: fails.append(f'script {i} syntax: {r.stderr[:160]}')
# 5 tag balance
from html.parser import HTMLParser
class P(HTMLParser):
    VOID = {'br', 'hr', 'img', 'meta', 'link', 'input', 'line', 'rect', 'circle', 'use', 'path'}
    def __init__(s): super().__init__(); s.stack = []; s.err = []
    def handle_starttag(s, t, a):
        if t not in s.VOID: s.stack.append(t)
    def handle_endtag(s, t):
        if t in s.VOID: return
        if s.stack and s.stack[-1] == t: s.stack.pop()
        else: s.err.append((t, s.getpos()))
p = P(); p.feed(doc)
if p.err or p.stack: fails.append(f'unbalanced tags: {p.err[:3]} open={p.stack[:5]}')
# 6 word budget (concision)
for mt in re.finditer(r'<h1 class="title action"[^>]*>(.*?)</h1>', doc, flags=re.S):
    w = len(text_of(mt.group(1)).split())
    if w > 24: fails.append(f'action title {w} words (max 24): {text_of(mt.group(1))[:60]}')
for mu in re.finditer(r'<ul class="takeaways">(.*?)</ul>', doc, flags=re.S):
    for li in re.findall(r'<li>(.*?)</li>', mu.group(1), flags=re.S):
        w = len(text_of(li).split())
        if w > 20: fails.append(f'takeaway {w} words (max 20): {text_of(li)[:60]}')
# 7 product rules the page must keep
# X3 on the page: no total presented as a fact. Entities are decoded first (encoding cannot hide a figure);
# text the page itself strikes or flags as an error (<s>, <mark class="flag">) is exempt, as a quoted conflict position is.
plain = html.unescape(re.sub(r'<(?:s|mark class="flag")>.*?</(?:s|mark)>', '', doc, flags=re.S))
if re.search(r'€\s?8[0-5][,.]?\d{3}|\b8[0-5],000\b|\b8[0-5]k\b', plain): fails.append('a numeric budget total appears (X3)')
g = re.search(r'<g id="kv-art">(.*?)</g>\s*</defs>', doc, flags=re.S)
if g:
    art = g.group(1)
    if 'gradient' in art.lower(): fails.append('gradient in key visual')
    for hexv in re.findall(r'(?:fill|stroke)="(#[0-9A-Fa-f]{6})"', art):
        if hexv.upper() not in ('#1B4F8A', '#F5C518', '#FFFFFF'): fails.append(f'off-palette colour in key visual {hexv}')
    if 'Meltemi Fizz' not in art: fails.append('wordmark missing from key visual')
    wm = re.search(r'<text x="1280" y="(\d+)"[^>]*font-size="(\d+)"[^>]*>Meltemi Fizz', art)
    if wm:
        base, fs = int(wm.group(1)), int(wm.group(2)); cap = round(fs * 0.72); top = base - cap; zone = (top - fs, base + fs)  # em-box reading of 'height of the wordmark'
        for cm in re.finditer(r'<circle cx="(\d+)" cy="(\d+)" r="(\d+)"', art):
            cx, cy, r = map(int, cm.groups()); r2 = r + 5
            if cy + r2 > zone[0] and cy - r2 < zone[1] and cx + r2 > 825 and cx - r2 < 1735: fails.append(f'clear-space intrusion: circle {cx},{cy},{r}')
        tag = re.search(r'<text x="1280" y="(\d+)"[^>]*font-size="(\d+)"[^>]*>SPARKLING', art)
        if tag and int(tag.group(1)) - round(int(tag.group(2)) * 0.72) < zone[1]: fails.append('tagline inside wordmark clear space')
else:
    fails.append('key visual <g id="kv-art"> missing')
if 'SHADOW MODE' not in doc: fails.append('shadow-mode notice missing')
# 8a visible-word budget per sheet (details excluded): hard cap 650, sheet 09 allowed 750
for ms in re.finditer(r'<section class="sheet[^"]*" id="(ch\d\d)"(.*?)</section>', doc, flags=re.S):
    vis = re.sub(r'<details.*?</details>', '', ms.group(2), flags=re.S)
    w = len(text_of(vis).split()); cap = 750 if ms.group(1) == 'ch09' else 650
    if w > cap: fails.append(f'{ms.group(1)} has {w} visible words (cap {cap})')
# 8b key visual: no opacity compositing (strict three-colour rule), mock-up label inside the 9:16 crop
if g:
    if re.search(r'(stroke-)?opacity=', g.group(1)): fails.append('opacity attribute in key visual (composites an off-palette tint)')
    lab = re.search(r'<text x="(\d+)" y="(\d+)"[^>]*text-anchor="(\w+)"[^>]*font-size="(\d+)"[^>]*letter-spacing="(\d+)"[^>]*>MOCK-UP', g.group(1))
    if not lab: fails.append('mock-up label missing from key visual')
    else:
        x, y, anchor, fs, ls = int(lab.group(1)), int(lab.group(2)), lab.group(3), int(lab.group(4)), int(lab.group(5))
        width = 26 * (0.62 * fs + ls)
        left = x - width / 2 if anchor == 'middle' else x
        if left < 740 or left + width > 1820: fails.append(f'mock-up label leaves the 9:16 crop (x {left:.0f}..{left + width:.0f})')
# 8c exactly three top-level decisions, counter scoped to them
dec = re.search(r'<ol class="decisions">(.*?)</ol>', doc, flags=re.S)
if dec:
    top = len(re.findall(r'\n        <li>', dec.group(1)))
    if top != 3: fails.append(f'{top} top-level decisions (expected 3)')
    if '.decisions > li { ' not in doc and '.decisions > li {' not in doc: fails.append('decision counter not scoped to .decisions > li')
# 8 regression guards: no empty evidence containers
for pg in re.findall(r'<div class="page" lang="(?:el|en)">(.*?)\n        </div>', doc, flags=re.S):
    if pg.count('<h4>') < 2: fails.append('facing page has fewer than 2 sections')
for cls in ('hero', 'brief', 'exam', 'numbers', 'decisions', 'limits', 'takeaways', 'flow'):
    for m2 in re.finditer(r'<(?:div|ul|ol|article) class="' + cls + r'[^"]*">(.*?)</(?:div|ul|ol|article)>', doc, flags=re.S):
        if len(text_of(m2.group(1)).split()) < 3: fails.append(f'empty .{cls} block')

print(json.dumps({'sheets': n, 'blockquotes': len(quotes), 'failures': fails}, ensure_ascii=False, indent=1))
sys.exit(1 if fails else 0)
