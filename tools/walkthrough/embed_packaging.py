"""Embed the Codex-generated packaging mock-up on sheet 09 as its own plate row beneath the two crops
(data URI, no external resource). Idempotent: re-running replaces the row. Run after judging: it changes the page hash."""
import base64, io, pathlib, re, sys, argparse
from PIL import Image
ROOT = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder')
ap = argparse.ArgumentParser(); ap.add_argument('--src', default='tools/walkthrough/kv_packaging_mockup.png'); ap.add_argument('--caption', default='Packaging application &middot; raster mock-up &middot; 1:1 &middot; generated for this walkthrough by an image model (gpt-6-astra, built-in image tool) from one prompt written from the brand mandatories; packaging is an undefined context in the brief <span class="dim">[open_questions/deliverables]</span>'); ap.add_argument('--alt', default='Packaging mock-up generated for this walkthrough; a corner caption reads mock-up, not for delivery.'); A = ap.parse_args()
SRC = ROOT / A.src
PAGE = ROOT / 'WALKTHROUGH.html'
MAXDIM, QUALITY = 1100, 82
im = Image.open(SRC).convert('RGB'); w, h = im.size
s = min(1.0, MAXDIM / max(w, h)); im = im.resize((round(w * s), round(h * s)), Image.LANCZOS)
buf = io.BytesIO(); im.save(buf, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
b64 = base64.b64encode(buf.getvalue()).decode('ascii')
print(f'{w}x{h} -> {im.size[0]}x{im.size[1]}, {len(buf.getvalue())//1024} KB jpeg, {len(b64)//1024} KB base64')
doc = PAGE.read_text(encoding='utf-8')
row = ('        <div class="plate-row" id="kv-packaging">\n'
       '          <div class="plate pack">\n'
       '            <i class="cm tl" aria-hidden="true"></i><i class="cm tr" aria-hidden="true"></i><i class="cm bl" aria-hidden="true"></i><i class="cm br" aria-hidden="true"></i>\n'
       f'            <img src="data:image/jpeg;base64,{b64}" width="{im.size[0]}" height="{im.size[1]}" alt="{A.alt}">\n'
       f'            <p class="slug">{A.caption}</p>\n'
       '          </div>\n'
       '        </div>\n')
doc, n = re.subn(r'        <div class="plate-row" id="kv-packaging">.*?\n        </div>\n', row, doc, flags=re.S)
if n == 0:
    anchor = '        </div>\n        <p class="slug"><span class="dim">Slug:</span> MOCK-UP'
    assert doc.count(anchor) == 1, doc.count(anchor)
    doc = doc.replace(anchor, '        </div>\n' + row + '        <p class="slug"><span class="dim">Slug:</span> MOCK-UP')
    old_slug = 'One drawing, two crops, drawn for this walkthrough; the pipeline emits text only. The ring illustrates Draft B&rsquo;s &ldquo;zero sugar&rdquo;.'
    assert doc.count(old_slug) == 1
    doc = doc.replace(old_slug, 'One drawing, two crops, drawn for this walkthrough, and one packaging application from an image model; the pipeline emits text only. The ring illustrates Draft B&rsquo;s &ldquo;zero sugar&rdquo;.')
    css_anchor = '.plate svg { display: block; width: 100%; height: auto; }'
    assert doc.count(css_anchor) == 1
    doc = doc.replace(css_anchor, css_anchor + '\n.plate.pack { width: 40%; margin-top: 8px; }\n.plate.pack img { display: block; width: 100%; height: auto; }')
    # phones: the packaging plate takes the full column like the crops
    m = re.search(r'@media \(max-width: 700px\) \{', doc)
    assert m, 'no 700px media block'
    doc = doc[:m.end()] + '\n  .plate.pack { width: 100%; }' + doc[m.end():]
    mid = '  .plate.p916 { width: 56%; }'
    assert doc.count(mid) == 1
    doc = doc.replace(mid, mid + '\n  .plate.pack { width: 56%; }')
PAGE.write_text(doc, encoding='utf-8'); print('inserted' if n == 0 else 'replaced', 'packaging plate row on sheet 09')
