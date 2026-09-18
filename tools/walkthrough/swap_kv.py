"""Replace the sheet-09 key-visual art (<g id="kv-art">…</g>) with the contents of a standalone direction SVG
(viewBox 0 0 2560 1920). Keeps the wrapper the two crops <use> refer to. Backs up the page first.
Usage: python3 tools/walkthrough/swap_kv.py --src tools/walkthrough/logo/dir2.svg"""
import argparse, pathlib, re, shutil
ROOT = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder'); PAGE = ROOT / 'WALKTHROUGH.html'
ap = argparse.ArgumentParser(); ap.add_argument('--src', required=True); A = ap.parse_args()
svg = (ROOT / A.src).read_text(encoding='utf-8')
m = re.search(r'<svg\b[^>]*>(.*)</svg>\s*$', svg, flags=re.S); assert m, 'no <svg> root'
inner = m.group(1).strip('\n')
assert 'Meltemi Fizz' in inner and 'MOCK-UP' in inner and 'SPARKLING' in inner, 'required text elements missing'
assert not re.search(r'opacity=|gradient|<filter|<image|<style|<script|&middot;', inner, flags=re.I), 'forbidden construct in direction SVG'
for hexv in re.findall(r'(?:fill|stroke)="(#[0-9A-Fa-f]{6})"', inner):
    assert hexv.upper() in ('#1B4F8A', '#F5C518', '#FFFFFF'), f'off-palette {hexv}'
inner = inner.replace('&#183;', '&middot;').replace('·', '&middot;')  # the page is HTML: entities are fine there
doc = PAGE.read_text(encoding='utf-8')
shutil.copy(PAGE, ROOT / 'tools/walkthrough/backups/before_kv_swap.html')
new, n = re.subn(r'(<g id="kv-art">)(.*?)(</g>\s*</defs>)', lambda mm: mm.group(1) + '\n' + inner + '\n            ' + mm.group(3), doc, count=1, flags=re.S)
assert n == 1, 'kv-art group not found'
PAGE.write_text(new, encoding='utf-8'); print('kv-art replaced from', A.src, '| backup: tools/walkthrough/backups/before_kv_swap.html')
