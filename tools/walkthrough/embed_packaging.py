"""Embed the Codex-generated packaging mock-up on sheet 09 as its own plate row beneath the two crops
(data URI, no external resource). Idempotent: re-running replaces the row. Run after judging: it changes the page hash.

Needs Pillow, which is not part of the locked toolchain (this is a one-off page tool, not a pipeline step).
"""
from __future__ import annotations

import argparse
import base64
import io
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # repo root, wherever it is cloned
PAGE = ROOT / 'WALKTHROUGH.html'
MAXDIM, QUALITY = 1100, 82
DEFAULT_SRC = 'tools/walkthrough/archive/images/kv_packaging_mockup.png'
DEFAULT_CAPTION = (
    'Packaging application &middot; raster mock-up &middot; 1:1 &middot; generated for this walkthrough by an '
    'image model (gpt-6-astra, built-in image tool) from one prompt written from the brand mandatories; packaging '
    'is an undefined context in the brief <span class="dim">[open_questions/deliverables]</span>'
)
DEFAULT_ALT = 'Packaging mock-up generated for this walkthrough; a corner caption reads mock-up, not for delivery.'
OLD_SLUG = (
    'One drawing, two crops, drawn for this walkthrough; the pipeline emits text only. '
    'The ring illustrates Draft B&rsquo;s &ldquo;zero sugar&rdquo;.'
)
NEW_SLUG = (
    'One drawing, two crops, drawn for this walkthrough, and one packaging application from an image model; '
    'the pipeline emits text only. The ring illustrates Draft B&rsquo;s &ldquo;zero sugar&rdquo;.'
)


def encode_jpeg(src: pathlib.Path) -> tuple[str, int, int]:
    """Downscale the image to MAXDIM and return (base64 JPEG, width, height)."""
    from PIL import Image  # optional dependency, imported only when the tool runs

    im = Image.open(src).convert('RGB')
    w, h = im.size
    s = min(1.0, MAXDIM / max(w, h))
    im = im.resize((round(w * s), round(h * s)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    b64 = base64.b64encode(buf.getvalue()).decode('ascii')
    print(f'{w}x{h} -> {im.size[0]}x{im.size[1]}, {len(buf.getvalue()) // 1024} KB jpeg, {len(b64) // 1024} KB base64')
    return b64, im.size[0], im.size[1]


def plate_row(b64: str, width: int, height: int, alt: str, caption: str) -> str:
    """The sheet-09 plate row that carries the embedded image."""
    corners = ''.join(f'<i class="cm {c}" aria-hidden="true"></i>' for c in ('tl', 'tr', 'bl', 'br'))
    return (
        '        <div class="plate-row" id="kv-packaging">\n'
        '          <div class="plate pack">\n'
        f'            {corners}\n'
        f'            <img src="data:image/jpeg;base64,{b64}" width="{width}" height="{height}" alt="{alt}">\n'
        f'            <p class="slug">{caption}</p>\n'
        '          </div>\n'
        '        </div>\n'
    )


def embed(doc: str, row: str) -> tuple[str, bool]:
    """Replace an existing packaging row, or insert it with its CSS; returns (page, inserted)."""
    doc, n = re.subn(r'        <div class="plate-row" id="kv-packaging">.*?\n        </div>\n', row, doc, flags=re.S)
    if n:
        return doc, False
    anchor = '        </div>\n        <p class="slug"><span class="dim">Slug:</span> MOCK-UP'
    if doc.count(anchor) != 1:
        raise ValueError(f'slug anchor found {doc.count(anchor)} times (expected 1)')
    doc = doc.replace(anchor, '        </div>\n' + row + anchor[len('        </div>\n'):])
    if doc.count(OLD_SLUG) != 1:
        raise ValueError('sheet-09 slug text not found exactly once')
    doc = doc.replace(OLD_SLUG, NEW_SLUG)
    css_anchor = '.plate svg { display: block; width: 100%; height: auto; }'
    if doc.count(css_anchor) != 1:
        raise ValueError('plate CSS anchor not found exactly once')
    pack_css = ('\n.plate.pack { width: 40%; margin-top: 8px; }'
                '\n.plate.pack img { display: block; width: 100%; height: auto; }')
    doc = doc.replace(css_anchor, css_anchor + pack_css)
    # phones: the packaging plate takes the full column like the crops
    m = re.search(r'@media \(max-width: 700px\) \{', doc)
    if not m:
        raise ValueError('no 700px media block')
    doc = doc[:m.end()] + '\n  .plate.pack { width: 100%; }' + doc[m.end():]
    mid = '  .plate.p916 { width: 56%; }'
    if doc.count(mid) != 1:
        raise ValueError('9:16 plate rule not found exactly once')
    return doc.replace(mid, mid + '\n  .plate.pack { width: 56%; }'), True


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: embed the image into WALKTHROUGH.html; exit 1 if the page anchors moved."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--src', default=DEFAULT_SRC)
    ap.add_argument('--caption', default=DEFAULT_CAPTION)
    ap.add_argument('--alt', default=DEFAULT_ALT)
    args = ap.parse_args(argv)
    b64, width, height = encode_jpeg(ROOT / args.src)
    try:
        doc, inserted = embed(PAGE.read_text(encoding='utf-8'), plate_row(b64, width, height, args.alt, args.caption))
    except ValueError as exc:
        print(f'embed_packaging: {exc}', file=sys.stderr)
        return 1
    PAGE.write_text(doc, encoding='utf-8')
    print('inserted' if inserted else 'replaced', 'packaging plate row on sheet 09')
    return 0


if __name__ == '__main__':
    sys.exit(main())
