"""Build SHARE_ME.html — the single-file, sendable front door.

START_HERE.html is the front door for someone who HAS the repo; its example cards link
into `runs/tier3/`. SHARE_ME.html is for someone who has nothing but one email
attachment: the pitch plus BOTH committed example pages embedded inside the file. The
recipient double-clicks, reads the story, and opens the real brief review and the run view
(how that brief was built) — offline, no repo, no server, no install.

It also carries the decision itself, so a forwarded sponsor needs nothing else: the
answer first with era-labelled headline tiles (WALKTHROUGH.html sheet 01), and the three
decisions with owners and needed-by dates, what signing each one commits to in
docs/pilot/GO_LIVE_DECISIONS.md, the proven / not-proven lists and the risks (sheet 10).
That content lives in the constants below (STEP_SENTENCE, ANSWER, TILES, DECISIONS,
PROVEN, NOT_PROVEN, RISKS); tests/test_share.py checks that the step sentence, the three
decision texts and their owners also appear in WALKTHROUGH.html and START_HERE.html, so
the three front doors cannot drift apart. The full decision paper, WALKTHROUGH.html, stays
in the repository; the pitch names it in plain text because this file carries exactly one
link (the repository URL, see tests/test_share.py).

How the embedding works: each example page is carried verbatim as a JSON-encoded string
(`</` escaped so no closing tag can break the carrier script). A click builds a Blob,
gets an object URL and opens it in a new tab — the page renders 1:1, own root element,
toggle and all. Popup blocked → same-tab fallback.

Committed output is generated, never hand-edited; `tests/test_share.py` fails the suite
if the embedded copies drift from the real `runs/tier3` pages. Rebuild with:

    python3 pipeline/share.py
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

if __package__ in (None, ""):  # allow `python3 pipeline/share.py`
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.review import THEME_CSS, ReviewInputError  # noqa: E402

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
.ask { margin: 0 0 0.6rem; font-size: 1.25rem; font-weight: 700; line-height: 1.35; max-width: 44rem; }
.tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr)); gap: 1rem; }
.tile { border-top: 2px solid var(--ink); padding-top: 0.6rem; }
.tile .big { font-size: 2rem; font-weight: 700; line-height: 1.1; }
.tile .big small { font-size: 0.85rem; font-weight: 600; color: var(--ink-2); margin-left: 0.35rem; }
.tile p { margin: 0.4rem 0 0; font-size: 0.84rem; color: var(--ink-2); }
.decisions { margin: 0; padding-left: 1.4rem; }
.decisions li { margin: 0 0 0.9rem; font-size: 0.92rem; max-width: 46rem; }
.decisions .owner { display: block; margin-top: 0.25rem; font-size: 0.82rem; font-weight: 600; color: var(--ok); }
h3.sub { font-size: 1.05rem; margin: 1.4rem 0 0.3rem; }
.table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; }
table.sign { width: 100%; border-collapse: collapse; font-size: 0.84rem; }
table.sign th, table.sign td { text-align: left; vertical-align: top; padding: 0.55rem 0.8rem;
  border-top: 1px solid var(--line); }
table.sign th { border-top: 0; color: var(--ink-2); font-weight: 600; }
.plist { margin: 0.3rem 0 0; padding-left: 1.1rem; font-size: 0.84rem; color: var(--ink-2); }
.plist li { margin: 0 0 0.35rem; }
"""

STEP_SENTENCE = (
    "Ten steps, two of them people: the account lead’s sign-off and the creative lead’s"
    " approval; six are AI, two plain code."
)
"""The one step-count sentence, shared verbatim by WALKTHROUGH.html sheet 02, START_HERE.html
and this page (tests/test_share.py checks all three)."""

ANSWER = (
    "Approve a four-week pilot, with live use in week 4 conditional on the retrospective results."
)

TILES: tuple[tuple[str, str, str], ...] = (
    (
        "17/17",
        "in 5 of 7 graded runs",
        "Current routing, September: 17/17 in 5 of 7 graded runs on three synthetic projects,"
        " one written blind; one run 16/17, one refused with no brief. July graded run"
        " (Haiku-era): 17/17 on one project.",
    ),
    (
        "926,524",
        "tokens per brief",
        "Current routing, September: mean of six complete briefs, about 90% Sonnet"
        " (northlight 695,991, voreas 1,291,833, levanta 887,505). At 15 briefs a month,"
        " ~13.9 M tokens a month — an estimate. Haiku-era (July, historical): 984,820.",
    ),
    (
        "11–14",
        "min per brief",
        "Current routing, September: stage-one wall clock per northlight brief (voreas"
        " 22–23). Haiku-era (July, historical): the graded run’s stages summed to 33 min.",
    ),
    (
        "3",
        "conflicts",
        "July graded run: all three shown with both sides cited; none decided by the machine.",
    ),
)

DECISIONS: tuple[dict[str, str], ...] = (
    {
        "ask": ANSWER,
        "detail": "Weeks 2–3: two account leads review three past projects each. Targets:"
        " over 80% of flagged questions judged useful; over 70% of draft text retained; under"
        " 30 minutes reviewing each draft; Greek naturalness rated 1–5 against a threshold the"
        " sponsor confirms before week 1. Both leads must choose voluntary reuse; missed targets"
        " block week-4 live use. Creative is in the pilot from week 1: a draft is released only"
        " after a named creative lead, not the brief signer, approves the exact files.",
        "owner": "the executive sponsor named at kickoff",
        "needed_by": "before week 1",
        "items": "D-01 team and kickoff, D-16 Greek floor (before week 1) · D-13 review time"
        " (end of week 1) · D-18 critical errors, D-20 creative measures (before week 2) ·"
        " D-14 survival, D-15 conflict catch (end of week 3)",
    },
    {
        "ask": "Accept the September re-baseline as the planning basis",
        "detail": "Measured on 2026-09-24 under the current routing (sonnet extraction + sonnet"
        " verify-extract) with the round-2 prompts; it replaces the July Haiku-era figures. Then"
        " set the refusal-rate target and decide the voreas regression precondition.",
        "owner": "the operator (AI specialist)",
        "needed_by": "before week 1",
        "items": "R-3 authorised · T-02 measured (September) · D-17 refusal-rate target"
        " (after T-02; the sponsor sets it) · T-03 voreas regression (before week 2)",
    },
    {
        "ask": "Proposed approval condition: before week 1, management and the operator estimate"
        " pilot costs and confirm capacity and workspace terms; the sponsor records a spending"
        " ceiling before any spending or client data, and an unset ceiling means no start.",
        "detail": "Costs: setup, training, subscription or seats, maintenance, support. Capacity"
        " planning starts from ~13.9 M tokens a month (an estimate, range 10.4–19.4 M), not"
        " the Haiku-era ~15 M.",
        "owner": "agency management with the operator",
        "needed_by": "before week 1",
        "items": "D-02 to D-07 account, data terms, location, usage window, retention · D-09"
        " roles and lawful basis · D-11 incident bounds · D-24, D-25, D-28 · D-27 the"
        " spending ceiling, recorded by the sponsor",
    },
)

SIGNING_RULE = "Every before-week-1 item closed means start; any one open means no start."

PROVEN: tuple[str, ...] = (
    "17/17 in 5 of 7 graded runs under the current routing, on three synthetic projects.",
    "A blind third project, written by an author who never saw the prompts and graded against"
    " an answer key sealed before the run: 17/17, and 21/21 required sub-checks on seven"
    " sealed extra checks (injection, misattribution, superseded date, currency trap,"
    " retraction, scope and language, undecided benefits).",
    "An injection canary: both planted instructions were recorded as “embedded instruction"
    " not followed”, with no side effects.",
    "A run that cannot pass a gate stops: one voreas run was refused at synthesis after two"
    " attempts and wrote no brief.",
    "The software behaves as specified (Tier 8): the deterministic suite passes, the frozen"
    " July evidence still grades 17/17 and a fault-injection benchmark passes 12/12 — a"
    " software rehearsal with no model calls.",
)

NOT_PROVEN: tuple[str, ...] = (
    "n is small: 3, 3 and 1 graded runs per project; for 3 of 3 the 95% Wilson interval is"
    " 0.44–1.00.",
    "Synthetic fixtures only: nothing has run on real client data.",
    "Greek register, review time, adoption and any time saved: those need the pilot.",
    "Creative for the September runs: pending the owner’s sign-off of run nl-r1, which is"
    " still a draft.",
)

RISKS: tuple[str, ...] = (
    "Exam-green is not lead-ready: every September brief has known defects no check scores"
    " (runs/r2-live/KNOWN_DEFECTS.md) — a spoken, hedged budget turned into “80–85” in"
    " a suggested question, open questions that re-ask open conflicts, Greek grammar slips.",
    "One northlight run scored 16/17: it kept a garbled term but made no glossary proposal for it.",
    "Refusals happen: one of seven graded September runs; a refusal stops the run and never"
    " ships a guess.",
    "On a subscription the constraint is the plan’s usage window, not a price per brief;"
    " commercial and data-processing terms are unresolved, and only synthetic data is"
    " permitted until the agency approves a data policy.",
)


def _e(text: str) -> str:
    """HTML-escape one text constant (quotes left alone: the text sits in element bodies)."""
    return html.escape(text, quote=False)


def _decision_html() -> str:
    """Sheet 01 and sheet 10 of the decision paper, condensed: answer, tiles, decisions, lists."""
    tiles = "\n".join(
        f'    <div class="tile"><div class="big">{_e(big)}<small>{_e(unit)}</small></div>'
        f"<p>{_e(text)}</p></div>"
        for big, unit, text in TILES
    )
    decisions = "\n".join(
        f'    <li><b>{_e(d["ask"].rstrip("."))}.</b> {_e(d["detail"])}'
        f'<span class="owner">Owner: {_e(d["owner"])} · needed {_e(d["needed_by"])}</span></li>'
        for d in DECISIONS
    )
    rows = "\n".join(
        f'    <tr><td>{n}</td><td>{_e(d["items"])}</td><td>{_e(d["owner"])}</td>'
        f'<td>{_e(d["needed_by"])}</td></tr>'
        for n, d in enumerate(DECISIONS, start=1)
    )

    def bullets(items: tuple[str, ...]) -> str:
        """One escaped <li> per text constant."""
        return "\n".join(f"    <li>{_e(item)}</li>" for item in items)

    return f"""
<section>
  <h2>The answer first</h2>
  <p class="ask">{_e(ANSWER)}</p>
  <p class="lede">Brief Builder drafts the brief with receipts; people decide. The figures
  below say which era they come from: the July graded run (Haiku-era extraction, historical)
  or the September round-2 runs under the current routing.</p>
  <div class="tiles">
{tiles}
  </div>
</section>

<section>
  <h2>The three decisions</h2>
  <ol class="decisions">
{decisions}
  </ol>
  <h3 class="sub">What you are signing</h3>
  <p class="lede">Each decision maps to go-live items in docs/pilot/GO_LIVE_DECISIONS.md.
  {_e(SIGNING_RULE)}</p>
  <div class="table-wrap"><table class="sign">
    <tr><th>decision</th><th>go-live items</th><th>owner</th><th>needed</th></tr>
{rows}
  </table></div>
</section>

<section>
  <h2>What is proven, what is not, and the risks</h2>
  <div class="g-grid">
    <div class="g-card"><h3>Proven</h3><ul class="plist">
{bullets(PROVEN)}
    </ul></div>
    <div class="g-card"><h3>Not proven</h3><ul class="plist">
{bullets(NOT_PROVEN)}
    </ul></div>
    <div class="g-card"><h3>Risks</h3><ul class="plist">
{bullets(RISKS)}
    </ul></div>
  </div>
</section>
"""


def _pitch() -> str:
    """The page body before the embedded carriers: pitch, decision, how it works, guarantees."""
    return f"""
<header class="masthead"><div class="mast-inner">
  <p class="kicker">One file, everything inside · nothing to install</p>
  <h1>Brief Builder</h1>
  <p class="mast-sub">From a messy pile of client inputs to a review-ready draft brief — in two
  languages, with receipts. AI writes, code checks, humans decide.</p>
  <div class="chips">
    <span class="chip ok">17/17 in 5 of 7 graded runs · synthetic projects</span>
    <span class="chip">every claim carries a citation</span>
    <span class="chip">gaps become questions, never guesses</span>
    <span class="chip">Greek + English from one object</span>
  </div>
</div></header>
<main>
{_decision_html()}
<section>
  <h2>Open the real thing</h2>
  <p class="lede">Both example pages travel inside this file — click to open them in a
  new tab. This is the finished, signed-off brief from the July graded run (synthetic
  project, real pipeline, Haiku-era extraction); the September current-routing briefs are
  review-ready drafts still awaiting the owner's sign-off.</p>
  <div class="card-row">
    <button type="button" class="card" data-doc="brief">
      <h3>The brief review</h3>
      <p>What the account lead gets: conflicts pinned as decisions, send-ready client
      questions with a copy button, seven evidenced fields — every value one click from
      its verbatim source quote. Greek-first, EN toggle.</p>
      <span class="go">Open the signed-off example →</span>
    </button>
    <button type="button" class="card" data-doc="run">
      <h3>How this brief was built (run view)</h3>
      <p>What each source contributed, what the fidelity gate flagged, the cross-source
      conflict candidates, and the readiness verdict — the system explaining its own work.</p>
      <span class="go">Open the run view →</span>
    </button>
  </div>
</section>

<section>
  <h2>How it works</h2>
  <p class="lede">{_e(STEP_SENTENCE)} Seven build the client brief; the account lead signs it
  before any creative work starts; the creative draft follows; and a named creative lead
  approves the exact files before any creative leaves as a package. Deterministic checks
  verify every model output — citations must resolve word-for-word, protected brand terms
  must survive, no figure may appear that no source stated.</p>
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
      <span class="jstep-status">no verbatim quote → no claim; a second reader checks it</span></span></li>
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
      <span class="jstep-status">the account lead signs before any creative work</span></span></li>
    <li class="jstep"><span class="jstep-no">9</span><span class="jstep-body">
      <span class="jstep-name">Creative draft</span>
      <span class="jstep-status">only after sign-off; a draft until approved</span></span></li>
    <li class="jstep human"><span class="jstep-no">10</span><span class="jstep-body">
      <span class="jstep-name">Creative approval</span>
      <span class="jstep-status">named creative lead; then a local package, never sent automatically</span></span></li>
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
      as written and flagged for a person to confirm. (The July graded run's renders dropped
      that flag — runs/tier3/KNOWN_DEFECTS.md B3; the September runs keep it visible next to
      the proposed match.)</p></div>
    <div class="g-card"><h3>Invent figures</h3><p>"Around eighty" stays that way until
      the client says eighty <em>what</em>. No number appears that no source stated.</p></div>
    <div class="g-card"><h3>Release creative on its own</h3><p>Creative starts as a draft,
      on signed-off briefs only. It becomes a local delivery package only after a named
      creative lead approves the exact files; nothing is sent, posted or approved on anyone's
      behalf.</p></div>
  </div>
</section>

<section>
  <h2>Since the July graded run</h2>
  <p class="lede">In September (Tiers 5–8) the system gained the operating layer an agency
  needs around it — local commands run by people, with no model calls: evidence-coverage
  audits and question triage; resolution, bilingual attestation and sign-off bound to the
  exact revision; creative registration, approval, release, verification and withdrawal;
  clarification packs; effort and rework records. Round 1 hardened it: runtime agents read
  only staged copies under an untrusted-content rule and deny rules; separation of duties and
  a hash-chained audit log; a data declaration on every project (refused without one);
  retention tooling; offline replay. Round 2 removed graded-fixture text from the runtime
  prompts and re-measured the pipeline live. The pilot operating pack is in docs/pilot/.</p>
</section>

</main>
<footer><p>Example content is a synthetic project — no real client data. Want the
system itself? <a href="{REPO_URL}">{REPO_URL}</a> — clone it and double-click
START_HERE.html; the full decision paper is WALKTHROUGH.html in the same folder.</p></footer>
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
    """Prepare the run view (run_review.html) for life inside SHARE_ME.

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
    page = (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>Brief Builder — see it for yourself</title>\n"
        f"<style>{THEME_CSS}{_CSS}</style>\n</head>\n<body>\n"
        + _pitch()
        + _carrier("brief", pages["brief"])
        + _carrier("run", pages["run"])
        + f"<script>{_JS}</script>\n</body>\n</html>\n"
    )
    out_path = Path(out_path)
    out_path.write_text(page, encoding="utf-8")
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
