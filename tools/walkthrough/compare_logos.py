"""Build tools/walkthrough/logo_directions.html: the three Codex logo directions side by side (1:1 render, 128 px
small-size test, Codex's rationale from directions.md). Same tokens as the walkthrough. Data URIs only."""
import base64, io, pathlib, re, html
from PIL import Image
ROOT = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder'); L = ROOT / 'tools/walkthrough/logo'
def data_uri(path, maxdim=900, q=86, fmt='JPEG'):
    im = Image.open(path).convert('RGB'); s = min(1.0, maxdim / max(im.size))
    im = im.resize((round(im.size[0] * s), round(im.size[1] * s)), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, fmt, quality=q, optimize=True)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(b.getvalue()).decode('ascii'), im.size
def png_uri(path):
    return 'data:image/png;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
page = (ROOT / 'WALKTHROUGH.html').read_text(encoding='utf-8'); root = re.search(r':root \{[^}]*\}', page).group(0)
md = (L / 'directions.md').read_text(encoding='utf-8') if (L / 'directions.md').exists() else ''
def section(n):
    # the markdown block for direction n: from a heading mentioning dir{n} or "Direction {n}" to the next heading
    m = re.search(r'(?ms)^#+\s*(?:' + str(n) + r'\s*[\u2014:-]|dir\s*' + str(n) + r'\b|Direction\s*' + str(n) + r'\b)[^\n]*\n(.*?)(?=^#+ |\Z)', md)
    body = m.group(1).strip() if m else ''
    return re.sub(r'(?m)^\[SVG\].*$', '', body).strip()  # drop the file-link line; the page shows the renders
def title(n):
    m = re.search(r'(?m)^#+\s*' + str(n) + r'\s*[\u2014:-]\s*(.+)$', md)
    return html.escape(m.group(1).strip()) if m else f'Direction {n}'
def md_to_html(t):
    t = html.escape(t); t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t); t = re.sub(r'`(.+?)`', r'<code>\1</code>', t)
    paras = [p.strip() for p in re.split(r'\n\s*\n', t) if p.strip()]
    out = []
    for p in paras:
        if re.match(r'^[-*] ', p): out.append('<ul>' + ''.join(f'<li>{l[2:]}</li>' for l in p.splitlines() if l.strip()) + '</ul>')
        elif re.match(r'^\d+\. ', p):
            items = [re.sub(r'^\d+\. ', '', l) for l in p.splitlines() if l.strip()]
            out.append('<ol>' + ''.join('<li>' + it + '</li>' for it in items) + '</ol>')
        else: out.append(f'<p>{p}</p>')
    return '\n'.join(out)
cols = []
for n in (1, 2, 3):
    big = L / f'dir{n}_sq.svg.png'; small = L / 'small' / f'dir{n}_sq.svg.png'
    if not big.exists(): continue
    bu, bs = data_uri(big); su = png_uri(small) if small.exists() else ''
    cols.append(f'''
    <section class="col" aria-labelledby="h{n}">
      <h2 id="h{n}"><span class="k">{n}</span>{title(n)}</h2>
      <figure class="plate"><img src="{bu}" width="{bs[0]}" height="{bs[1]}" alt="Direction {n}, 1:1 crop of the master frame."><figcaption>1:1 crop of the 2560&times;1920 master &middot; flat two-colour + white &middot; <b>mock-up</b></figcaption></figure>
      {f'<figure class="small"><img src="{su}" width="128" height="128" alt="Direction {n} at 128 pixels."><figcaption><span class="lbl">Small-size test</span>128 px, as it would sit on a shelf tag or an app icon.</figcaption></figure>' if su else ''}
      <div class="why">{md_to_html(section(n))}</div>
    </section>''')
rank = re.search(r'(?ms)^#+[^\n]*[Rr]ank[^\n]*\n(.*?)(?=^#+ |\Z)', md)
doc = f'''<title>Meltemi Wind Marks</title>
<style>
{root}
:root {{ color-scheme: light; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --paper: #1C1D1A; --ink: #ECEDE6; --pencil: #A7AAA0; --rule: #3A3C36; --white: #262823; --bar: #22241F; }} }}
:root[data-theme="dark"] {{ --paper: #1C1D1A; --ink: #ECEDE6; --pencil: #A7AAA0; --rule: #3A3C36; --white: #262823; --bar: #22241F; }}
body {{ margin: 0; background: var(--paper); color: var(--ink); font: 400 17px/26px var(--serif); }}
.desk {{ max-width: 1360px; margin: 0 auto; padding: 40px 32px 64px; }}
.kicker {{ display: flex; gap: 20px; flex-wrap: wrap; align-items: baseline; margin: 0 0 6px; font: 700 11px/16px var(--label); letter-spacing: 0.14em; text-transform: uppercase; color: var(--pencil); }}
.kicker .num {{ color: var(--ink); }}
h1 {{ margin: 0 0 8px; font: 400 40px/46px var(--serif); letter-spacing: -0.01em; text-wrap: balance; max-width: 28ch; }}
.narr {{ margin: 0 0 32px; max-width: 66ch; }}
.narr .cite {{ font: 400 13px/20px var(--ledger); color: var(--pencil); }}
.cols {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 32px; align-items: start; }}
.col h2 {{ margin: 0 0 14px; font: 400 24px/30px var(--serif); display: flex; gap: 12px; align-items: baseline; text-wrap: balance; }}
.col h2 .k {{ flex: none; display: inline-block; width: 30px; height: 30px; border: 1.5px solid var(--red); color: var(--red); font: 700 13px/28px var(--label); text-align: center; }}
figure {{ margin: 0; }}
.plate {{ background: var(--white); border: 1px solid var(--rule); box-shadow: 0 1px 0 var(--rule), 0 12px 24px -18px rgba(0,0,0,.35); padding: 14px; }}
.plate img {{ display: block; width: 100%; height: auto; }}
figcaption {{ margin-top: 10px; font: 400 13px/20px var(--ledger); color: var(--pencil); }}
figcaption b {{ color: var(--ink); }}
.small {{ margin-top: 18px; display: grid; grid-template-columns: 128px 1fr; gap: 16px; align-items: center; }}
.small img {{ display: block; width: 128px; height: 128px; border: 1px solid var(--rule); image-rendering: auto; }}
.small figcaption {{ margin: 0; font: 400 15px/22px var(--serif); color: var(--ink); }}
.lbl {{ display: block; font: 700 11px/16px var(--label); letter-spacing: 0.14em; text-transform: uppercase; color: var(--pencil); margin-bottom: 4px; }}
.why {{ margin-top: 16px; font: 400 15px/23px var(--serif); color: var(--ink); }}
.why p {{ margin: 0 0 10px; }} .why ul, .why ol, .rank ol {{ margin: 0 0 10px; padding-left: 20px; }} .rank li {{ margin: 0 0 6px; }} .why code {{ font: 400 12px/18px var(--ledger); }}
.rank {{ margin: 40px 0 0; padding: 20px 24px; border-left: 3px solid var(--red); max-width: 70ch; font: 400 16px/24px var(--serif); }}
.rank .lbl {{ margin-bottom: 8px; }}
.foot {{ margin: 32px 0 0; padding-top: 16px; border-top: 1px solid var(--rule); font: 400 13px/20px var(--ledger); color: var(--pencil); max-width: 84ch; }}
@media (max-width: 980px) {{ .cols {{ grid-template-columns: 1fr; }} h1 {{ font-size: 30px; line-height: 36px; }} }}
</style>
<div class="desk">
  <p class="kicker"><span class="num">Brief Builder</span><span>Sheet 09 &middot; key-visual lockup</span><span>Territory: the wind itself</span><span>Shadow mode &middot; synthetic brand</span></p>
  <h1>Three ways to make the meltemi the mark</h1>
  <p class="narr">The brief to Codex (gpt-6-astra): a mark only Meltemi Fizz can own, built on the north wind of the Aegean summer, ideally reading as rising fizz in the same gesture; two brand colours plus white, flat, drawn at the sheet-09 master geometry so the page&rsquo;s clear-space and palette checks apply unchanged; must survive the 1:1 and 9:16 crops and a 128&thinsp;px test. The rejected ring-and-leaf is the baseline. <span class="cite">Source SVGs: tools/walkthrough/logo/dir1..3.svg &middot; rationale: directions.md</span></p>
  <div class="cols">{''.join(cols)}
  </div>
  {f'<div class="rank"><span class="lbl">Codex&rsquo;s own ranking</span>{md_to_html(rank.group(1).strip())}</div>' if rank else ''}
  <p class="foot">Pick a number and it replaces the art on sheet 09 (tools/walkthrough/swap_kv.py), the can is re-rendered from it, and round 8 runs on the result. Nothing here is a deliverable; the walkthrough labels every visual a mock-up.</p>
</div>
'''
out = ROOT / 'tools/walkthrough/logo_directions.html'; out.write_text(doc, encoding='utf-8'); print('wrote', out, len(doc) // 1024, 'KB,', len(cols), 'directions')
