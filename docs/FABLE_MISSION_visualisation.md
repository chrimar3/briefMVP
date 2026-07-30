# Fable Mission — Brief visualisation for account leads

**Status:** IN PROGRESS — owner gave the explicit go 2026-07-30. §5 is the plan being
executed; §6 owner decisions are binding.
**Author:** Claude Fable 5, from the owner's prompt: *"better visualisation for the account
leads for the briefs and the results they get."*
**Date:** 2026-07-30

---

## 1. The problem, concretely

An account lead's job in this pipeline is exactly four verbs: **review** the draft,
**resolve** conflicts, **send** the open questions, **sign off**. What they receive today:

| Artifact | What it is | Why it fails the account lead |
|---|---|---|
| `brief_el.md` / `brief_en.md` | Prose walls with `[source §loc]` tags | Conflicts and questions are sections at the bottom; confidence/qualifiers are words in sentences; no way to *see* what is solid vs shaky at a glance |
| `brief.json` | The canonical object | Machine food — the evidence trail lives here, unreadable to a non-technical lead |
| Runner/harness console | Gate results, 17/17, costs | CLI output; invisible unless someone screenshots it for them |

The product's core claim is *"every value carries its evidence, gaps become questions,
conflicts are yours to resolve"* — and none of that is **visible** without reading tags.

## 2. Proposal (recommended): the Brief Review Page

One **self-contained static HTML file per run** — `brief_review.html`, generated
**deterministically from `brief.json`** by pipeline code. No model call, no server, no
install: the account lead double-clicks a file, or the agency drops it in an email.

### Layout sketch

```
┌────────────────────────────────────────────────────────────┐
│  Meltemi Fizz — Launch brief (draft)        [EL] [EN]      │
│  ● READY FOR REVIEW   7/7 fields evidenced · 4% low-conf   │
│  ⚠ 2 conflicts to resolve · 9 questions to send            │
├────────────────────────────────────────────────────────────┤
│  ⚠ CONFLICTS — resolve before sign-off        (pinned top) │
│  ┌─ Budget ────────────────┬───────────────────────────┐   │
│  │ RFP: €90.000 incl media │ CFO: «ογδόντα, ίσως 85»   │   │
│  │ rfp_meltemi §6          │ excl. media · [00:14:32]  │   │
│  └─────────────────────────┴───────────────────────────┘   │
│  ❓ OPEN QUESTIONS — one click copies the list for email    │
│  1. [budget] Το 80–85 αφορά χιλιάδες ευρώ; …               │
├────────────────────────────────────────────────────────────┤
│  1. Objectives                                             │
│  ▸ Brand awareness — new category    [stated · high] ▼     │
│     └ «το βασικό για μας είναι το μπραντ αγουέρνες»        │
│        transcript_kickoff [00:02:05] — DIMITRIS            │
│  ▸ TikTok dance idea            [conditional · low ⚠] ▼    │
└────────────────────────────────────────────────────────────┘
```

The grammar of the page:

- **Conflicts pinned first**, as two-column cards quoting both positions verbatim with
  citations — the lead's decision, framed as a decision.
- **Open questions as a send-ready list** (copy button) — because "send the questions" is a
  real task, not reading.
- **Every entry wears its epistemic state**: confidence pill (high/medium/low), qualifier
  badge (`stated` / `implied` / `conditional` — conditional always amber). Shaky things
  *look* shaky.
- **Evidence one click away, never gone**: each entry expands to the verbatim anchor quote,
  source, location, speaker. The trust story becomes tactile.
- **A run-health strip** for "the results they get": readiness verdict, gates passed,
  garbles flagged-not-fixed, cost of the run. Small, factual, no charts for charts' sake.
- **EL/EN toggle** re-using the two rendered documents plus the canonical entries.

### Why deterministic generation is the whole trick

The page is assembled by Python from `brief.json` — the same object both renders come from.
Zero drift risk (it cannot say anything the brief doesn't), zero model cost, fully unit-
testable, and it inherits every gate that already protects the object. This is a **view**,
not a fourth author.

## 3. Alternatives considered

| Option | What | Verdict |
|---|---|---|
| **A. Brief Review Page** (above) | Per-run static HTML from `brief.json` | **Recommended first** — highest value per unit of scope, zero model cost, ~2–3 sessions |
| B. Runs dashboard | Index page over `runs/`: harness verdicts, costs, timings | Useful for the *agency/ops*, not the account lead. Cheap follow-on (same renderer, one more template) — phase 2 |
| C. Interactive resolution | Conflict resolve / sign-off buttons writing back to `brief.json` | This is an application: state, auth, audit trail. Genuinely valuable (it's the lead's real workflow) but it's a different mission with server-shaped risks. Park as v2 seed |

## 4. The scope question this mission must answer honestly

PRD non-goals say **"no UI"**, and CLAUDE.md rule 5 makes non-goals prohibitions. That guard
existed to keep the MVP from becoming a web app. Option A threads it deliberately: a
**generated document** (like the renders, like the SVG evidence images) — no server, no
routes, no state, no editing. But approving this mission is a **conscious scope amendment**
by the owner, and the doc says so out loud. Boundaries that keep it a document:

1. Read-only forever within this mission — no write-back of any kind.
2. Self-contained single file — no network requests, no CDN, no build toolchain.
3. Generated only from the canonical object + existing run artifacts.
4. If it ever needs a server, it has left this mission and needs a new one.

## 5. Build plan (if approved)

| Step | Deliverable | Check |
|---|---|---|
| 1 | `pipeline/review.py` — pure function `brief.json` → HTML string; CLI `python3 pipeline/review.py runs/<id>` | Unit tests: every entry/conflict/question present; no content not in the object; conditional/low always badged |
| 2 | Runner integration: emitted automatically after render (deterministic step, no model) | Runner test + manifest records the artifact |
| 3 | Templates polish: EL/EN toggle, copy-questions button, print stylesheet (PDF for clients) | Rendered on the 3 stored briefs (tier3, live, evidence run) and eyeballed |
| 4 | Evidence pack + README: one screenshot-style capture, one line under "Run it" | Docs updated |

Effort: ~2–3 focused sessions. Model cost: **$0 per brief** (deterministic).
Test posture: same as gates — deterministic, no model calls in tests.

## 6. Owner decisions (2026-07-30)

1. **Run-health strip: account lead only** — readiness verdict + conflict/question counts.
   No cost or model information on the page.
2. **Internal only for the pilot** — the client continues to receive the rendered documents;
   print-to-PDF stays an internal convenience.
3. **`./run_full.sh` opens the review page when the run completes** — the demo's closing shot.
4. **Greek-first chrome**, EN toggle available; content bilingual regardless.

## 7. Explicitly out of scope (v2 seeds, separate missions)

Resolution write-back and sign-off capture (option C) · runs dashboard (option B) ·
client delivery portal · notifications/integrations of any kind (PRD non-goal stands).

---

*Next step: the owner says "go" (or edits this doc further) — implementation then starts
as its own tracked work with the usual gates, and this status line changes to IN PROGRESS.*
