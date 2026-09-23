"""Source of truth: WALKTHROUGH.html at the repo root (standalone).

Derives the artifact variant (no doctype/html/head/body — the Artifact tool adds those).
Usage: python3 tools/walkthrough/build.py [--src PAGE] [--out FILE]
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFAULT_SRC = ROOT / 'WALKTHROUGH.html'
DEFAULT_OUT = pathlib.Path(__file__).resolve().parent / 'a_brief_with_receipts.html'


def artifact_variant(doc: str) -> str:
    """Strip the page to title + style + body; repo-relative links become plain spans (they only work in the repo)."""
    title_m = re.search(r'<title>(.*?)</title>', doc, flags=re.S)
    style_m = re.search(r'<style>.*?</style>', doc, flags=re.S)
    body_m = re.search(r'<body>\n?(.*?)\n?</body>', doc, flags=re.S)
    if not (title_m and style_m and body_m):
        raise ValueError('page lacks a <title>, <style> or <body> block')
    body = re.sub(r'<a class="repo" href="[^"]*">(.*?)</a>', r'<span class="repo">\1</span>', body_m.group(1))
    return f'<title>{title_m.group(1)}</title>\n{style_m.group(0)}\n{body}\n'


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: write the artifact variant; exit 1 when the source page is unreadable or malformed."""
    ap = argparse.ArgumentParser(description='Build the artifact variant of WALKTHROUGH.html.')
    ap.add_argument('--src', type=pathlib.Path, default=DEFAULT_SRC)
    ap.add_argument('--out', type=pathlib.Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    src, out = args.src.resolve(), args.out.resolve()
    try:
        doc = src.read_text(encoding='utf-8')
        out.write_text(artifact_variant(doc), encoding='utf-8')
    except (OSError, ValueError) as exc:
        print(f'build: {exc}', file=sys.stderr)
        return 1
    print(f'built artifact variant {out.name}: {len(doc.encode())} -> {out.stat().st_size} bytes')
    return 0


if __name__ == '__main__':
    sys.exit(main())
