"""Source of truth: /Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html (standalone).
Derives the artifact variant (no doctype/html/head/body — the Artifact tool adds those)."""
import re, pathlib
SRC = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html')
OUT = pathlib.Path(__file__).parent / 'a_brief_with_receipts.html'  # artifact variant (no doctype/html/head/body)
doc = SRC.read_text(encoding='utf-8')
title = re.search(r'<title>(.*?)</title>', doc, flags=re.S).group(1)
style = re.search(r'<style>.*?</style>', doc, flags=re.S).group(0)
body = re.search(r'<body>\n?(.*?)\n?</body>', doc, flags=re.S).group(1)
body = re.sub(r'<a class="repo" href="[^"]*">(.*?)</a>', r'<span class="repo">\1</span>', body)  # repo-relative links only work beside the repo
OUT.write_text(f'<title>{title}</title>\n{style}\n{body}\n', encoding='utf-8')
print(f'built artifact variant {OUT.name}: {len(doc.encode())} -> {OUT.stat().st_size} bytes')
