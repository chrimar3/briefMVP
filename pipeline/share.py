"""Build SHARE_ME.html — the single-file, sendable front door.

START_HERE.html is the front door for someone who HAS the repo; its example cards link
into `runs/tier3/`. SHARE_ME.html is for someone who has nothing but one email
attachment: the pitch plus BOTH committed example pages embedded inside the file. The
recipient double-clicks, reads the story, and opens the real brief review and pipeline
walkthrough — offline, no repo, no server, no install.

How the embedding works: each example page is carried verbatim as a JSON-encoded string
(`</` escaped so no closing tag can break the carrier script). A click builds a Blob,
gets an object URL and opens it in a new tab — the page renders 1:1, own root element,
toggle and all. Popup blocked → same-tab fallback.

Committed output is generated, never hand-edited; `tests/test_share.py` fails the suite
if the embedded copies drift from the real `runs/tier3` pages. Rebuild with:

    python3 pipeline/share.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python3 pipeline/share.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import THEME_CSS, ReviewInputError

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_RUN = REPO_ROOT / "runs" / "tier3"
DEFAULT_OUT = REPO_ROOT / "SHARE_ME.html"
REPO_URL = "https://github.com/chrimar3/briefMVP"

_CSS = """
.mast-inner { max-width: 60rem; margin: 0 auto; padding: 2.6rem 1.5rem 1.6rem; }
.kicker { margin: 0 0 0.4rem; font-size: 0.72rem; letter-spacing: 0.09em;
  text-transform: uppercase; color: var(--ink-2); font-weight: 700; }
h1 { margin: 0; font-size: 2.2rem; font-weight: 700; line-height: 1.12; }
.mast-sub { margin: 0.55rem 0 1rem; color: var(--ink-2); font-size: 1rem; max-width: 42rem; }
.masthead { border-bottom: 1px solid var(--line); }
.chips { display: flex; flex-wrap: wrap; gap: 0.5rem; }
.chip.ok { background: var(--ok-bg); color: var(--ok); }
main { max-width: 60rem; margin: 0 auto; padding: 0.5rem 1.5rem 3rem; }
section { margin-top: 2.6rem; }
h2 { font-size: 1.4rem; font-weight: 700; margin: 0 0 0.4rem; }
.lede { margin: 0 0 1.1rem; color: var(--ink-2); font-size: 0.95rem; max-width: 44rem; }
.card-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(19rem, 1fr)); gap: 1rem; }
.card { text-align: left; background: var(--card); border: 1px solid var(--line);
  border-radius: 16px; padding: 1.15rem 1.25rem; color: inherit; cursor: pointer;
  font: inherit; box-shadow: 0 1px 2px rgba(0,0,0,0.05); transition: box-shadow 0.15s ease; }
.card:hover { box-shadow: 0 5px 16px rgba(0,0,0,0.1); }
.card h3 { margin: 0 0 0.25rem; font-size: 1.05rem; font-weight: 700; }
.card p { margin: 0; font-size: 0.88rem; color: var(--ink-2); }
.card .go { display: inline-block; margin-top: 0.7rem; font-size: 0.85rem; font-weight: 600;
  color: var(--brand); }
.journey { margin: 0; padding: 0; list-style: none; display: flex; flex-wrap: wrap; gap: 0.6rem; }
.jstep { display: flex; align-items: center; gap: 0.6rem; background: var(--card);
  border: 1px solid var(--line); border-radius: 999px; padding: 0.45rem 0.95rem 0.45rem 0.5rem; }
.jstep-no { width: 1.7rem; height: 1.7rem; border-radius: 999px; background: var(--bg-soft);
  color: var(--ink-2); font-size: 0.8rem; font-weight: 700; display: flex;
  align-items: center; justify-content: center; flex: none; }
.jstep.human { border-color: var(--ok); }
.jstep.human .jstep-no { background: var(--ok-bg); color: var(--ok); }
.jstep-body { display: flex; flex-direction: column; line-height: 1.25; }
.jstep-name { font-size: 0.85rem; font-weight: 600; }
.jstep-status { font-size: 0.72rem; color: var(--ink-2); }
.g-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(17rem, 1fr)); gap: 0.8rem; }
.g-card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
  padding: 0.9rem 1.05rem; }
.g-card h3 { margin: 0 0 0.2rem; font-size: 0.92rem; font-weight: 700; }
.g-card p { margin: 0; font-size: 0.84rem; color: var(--ink-2); }
footer { border-top: 1px solid var(--line); background: var(--bg-soft); margin-top: 3rem; }
footer p { max-width: 60rem; margin: 0 auto; padding: 1rem 1.5rem; color: var(--ink-2);
  font-size: 0.8rem; }
footer a { color: inherit; }
"""

_PITCH = """
<header class="masthead"><div class="mast-inner">
  <p class="kicker">One file, everything inside · nothing to install</p>
  <h1>Brief Builder</h1>
  <p class="mast-sub">From a messy pile of client inputs to a client-ready brief — in two
  languages, with receipts. AI writes, code checks, humans decide.</p>
  <div class="chips">
    <span class="chip ok">17/17 on a sealed answer key</span>
    <span class="chip">every claim carries a citation</span>
    <span class="chip">gaps become questions, never guesses</span>
    <span class="chip">Greek + English from one object</span>
  </div>
</div></header>
<main>

<section>
  <h2>Open the real thing</h2>
  <p class="lede">Both example pages travel inside this file — click to open them in a
  new tab. This is a finished, signed-off brief from the system's graded run
  (synthetic project, real pipeline).</p>
  <div class="card-row">
    <button type="button" class="card" data-doc="brief">
      <h3>The brief review</h3>
      <p>What the account lead gets: conflicts pinned as decisions, send-ready client
      questions with a copy button, seven evidenced fields — every value one click from
      its verbatim source quote. Greek-first, EN toggle.</p>
      <span class="go">Open the signed-off example →</span>
    </button>
    <button type="button" class="card" data-doc="run">
      <h3>The pipeline walkthrough</h3>
      <p>How that brief was built: what each source contributed, what the fidelity gate
      flagged, the cross-source conflict candidates, and the readiness verdict — the
      system explaining its own work.</p>
      <span class="go">Open the run walkthrough →</span>
    </button>
  </div>
</section>

<section>
  <h2>How it works</h2>
  <p class="lede">Seven pipeline steps, one human gate. Deterministic checks verify every
  model output — citations must resolve word-for-word, protected brand terms must
  survive, no figure may appear that no source stated.</p>
  <ol class="journey">
    <li class="jstep"><span class="jstep-no">1</span><span class="jstep-body">
      <span class="jstep-name">Readiness gate</span>
      <span class="jstep-status">refuses to draft on thin input</span></span></li>
    <li class="jstep"><span class="jstep-no">2</span><span class="jstep-body">
      <span class="jstep-name">Classification</span>
      <span class="jstep-status">project type + sensitivity tier</span></span></li>
    <li class="jstep"><span class="jstep-no">3</span><span class="jstep-body">
      <span class="jstep-name">Fidelity check</span>
      <span class="jstep-status">garbled transcripts flagged, never fixed</span></span></li>
    <li class="jstep"><span class="jstep-no">4</span><span class="jstep-body">
      <span class="jstep-name">Extraction</span>
      <span class="jstep-status">no verbatim quote → no claim</span></span></li>
    <li class="jstep"><span class="jstep-no">5</span><span class="jstep-body">
      <span class="jstep-name">Conflict pass</span>
      <span class="jstep-status">disagreements surfaced, never resolved</span></span></li>
    <li class="jstep"><span class="jstep-no">6</span><span class="jstep-body">
      <span class="jstep-name">Synthesis</span>
      <span class="jstep-status">one canonical brief object</span></span></li>
    <li class="jstep"><span class="jstep-no">7</span><span class="jstep-body">
      <span class="jstep-name">Render EL/EN</span>
      <span class="jstep-status">generate once, render twice</span></span></li>
    <li class="jstep human"><span class="jstep-no">8</span><span class="jstep-body">
      <span class="jstep-name">Human sign-off</span>
      <span class="jstep-status">nothing ships without people</span></span></li>
    <li class="jstep"><span class="jstep-no">9</span><span class="jstep-body">
      <span class="jstep-name">Creative (shadow)</span>
      <span class="jstep-status">only after sign-off, never delivered</span></span></li>
  </ol>
</section>

<section>
  <h2>What the system will not do</h2>
  <div class="g-grid">
    <div class="g-card"><h3>Guess</h3><p>Thin input is refused with a precise list of
      what to request from the client — a refusal is the product working.</p></div>
    <div class="g-card"><h3>Resolve conflicts</h3><p>When sources disagree, both quotes
      are shown with citations. Resolution belongs to the account lead, by design.</p></div>
    <div class="g-card"><h3>Silently fix garbles</h3><p>A mangled term is extracted
      as written and flagged — the reader decides what it meant.</p></div>
    <div class="g-card"><h3>Invent figures</h3><p>"Around eighty" stays that way until
      the client says eighty <em>what</em>. No number appears that no source stated.</p></div>
  </div>
</section>

</main>
<footer><p>Example content is a synthetic project — no real client data. Want the
system itself? <a href="REPO_URL_HERE">REPO_URL_HERE</a> — clone it and double-click
START_HERE.html.</p></footer>
"""

_JS = """
(function () {
  "use strict";
  function openDoc(key) {
    var node = document.getElementById("doc-" + key);
    if (!node) { return; }
    var blob = new Blob([JSON.parse(node.textContent)], { type: "text/html" });
    var url = URL.createObjectURL(blob);
    var win = window.open(url, "_blank");
    if (!win) { location.href = url; }
  }
  var cards = document.querySelectorAll(".card[data-doc]");
  for (var i = 0; i < cards.length; i++) {
    cards[i].addEventListener("click", function () {
      openDoc(this.getAttribute("data-doc"));
    });
  }
})();
"""


_ADAPTED_BUTTONS = """<div class="cta-row">
<button type="button" class="cta" data-open="brief" data-mime="text/html">
<span class="i-el">Άνοιγμα σελίδας ελέγχου brief</span>
<span class="i-en">Open the brief review page</span></button>
<button type="button" class="doc-link" data-open="el" data-mime="text/html">
<span class="i-el">Έγγραφο πελάτη (ΕΛ)</span><span class="i-en">Client document (EL)</span></button>
<button type="button" class="doc-link" data-open="en" data-mime="text/html">
<span class="i-el">Έγγραφο πελάτη (EN)</span><span class="i-en">Client document (EN)</span></button>
</div>"""

_ADAPTED_JS = """
(function () {
  "use strict";
  function openPayload(key, mime) {
    var node = document.getElementById("doc-" + key);
    if (!node) { return; }
    var blob = new Blob([JSON.parse(node.textContent)], { type: mime });
    var url = URL.createObjectURL(blob);
    var win = window.open(url, "_blank");
    if (!win) { location.href = url; }
  }
  var buttons = document.querySelectorAll("[data-open]");
  for (var i = 0; i < buttons.length; i++) {
    buttons[i].addEventListener("click", function () {
      openPayload(this.getAttribute("data-open"), this.getAttribute("data-mime"));
    });
  }
})();
"""


def adapt_run_page(page_html: str, brief_html: str, el_md: str, en_md: str) -> str:
    """Prepare the walkthrough page for life inside SHARE_ME.

    Its bottom buttons link sibling files by relative href — meaningless from a blob
    page with no folder around it. So the siblings ride along: the brief page and both
    rendered documents are embedded as payloads inside the walkthrough itself, and the
    buttons become blob-openers — same mechanism as the cover cards, works anywhere.
    Everything above the button row stays byte-identical.
    """
    import re

    adapted = re.sub(
        r'<div class="cta-row">.*?</div>', _ADAPTED_BUTTONS, page_html, count=1, flags=re.S
    )
    payload_block = (
        "<style>button.cta, button.doc-link { font: inherit; cursor: pointer; }"
        " button.cta { border: 0; } button.doc-link { background: transparent; }</style>"
        + _carrier("brief", brief_html)
        + _carrier("el", el_md)
        + _carrier("en", en_md)
        + f"<script>{_ADAPTED_JS}</script>"
    )
    return adapted.replace("</body>", payload_block + "</body>", 1)


def _carrier(key: str, page_html: str) -> str:
    """JSON-encode a full HTML document so it can ride inside a <script> tag.

    `</` becomes `<\\/` (a legal JSON escape), so no `</script>` inside the payload can
    terminate the carrier element. JSON.parse on the client restores it byte-for-byte.
    """
    payload = json.dumps(page_html).replace("</", "<\\/")
    return f'<script type="application/json" id="doc-{key}">{payload}</script>'


def build_share(example_run=EXAMPLE_RUN, out_path=DEFAULT_OUT) -> Path:
    example_run = Path(example_run)
    texts = {}
    for name in ("brief_review.html", "run_review.html", "brief_el.html", "brief_en.html"):
        path = example_run / name
        if not path.is_file():
            raise ReviewInputError(
                f"no {name} in {example_run} — SHARE_ME embeds the committed example "
                "run's pages and styled document views; generate them first"
            )
        texts[name] = path.read_text(encoding="utf-8")
    pages = {
        "brief": texts["brief_review.html"],
        "run": adapt_run_page(
            texts["run_review.html"],
            texts["brief_review.html"],
            texts["brief_el.html"],
            texts["brief_en.html"],
        ),
    }
    html = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Brief Builder — see it for yourself</title>\n"
        f"<style>{THEME_CSS}{_CSS}</style>\n</head>\n<body>\n"
        + _PITCH.replace("REPO_URL_HERE", REPO_URL)
        + _carrier("brief", pages["brief"])
        + _carrier("run", pages["run"])
        + f"<script>{_JS}</script>\n</body>\n</html>\n"
    )
    out_path = Path(out_path)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main(argv=None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild the single-file sendable front door.")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)
    try:
        out_path = build_share(out_path=args.out)
    except ReviewInputError as exc:
        print(f"share: {exc}", file=sys.stderr)
        return 1
    print(out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
