# Brief Builder — MVP PRD v1

**Case:** Northlight Communications (~40-person PR/ad agency, Athens; corporate clients incl. banking & pharma)
**Author:** Christos — AI Transformation Specialist assignment
**Status:** Working document. Feeds the 10-slide deck and the 20-minute defense.
**Design philosophy:** Deterministic core, thin AI edges. Buy the model, build the skeleton. The skeleton is the product.

---

## 1. Problem statement

Turning raw client input (kickoff transcripts, email threads, RFPs, background docs) into a structured client brief consumes account-lead hours, and **quality varies by author** — the agency's output floor is set by its most tired writer on their worst day. For creative projects, a second translation (client brief → creative brief) is inconsistent too. The cost is not only hours: weak briefs propagate downstream into creative rework and client revision rounds.

**Two distinct problems, one pipeline:**
- **Stage 1 (client brief) is an extraction problem** — completeness, accuracy, traceability to sources.
- **Stage 2 (creative brief) is a compression problem** — an opinionated single-minded proposition, not a summary.
Different failure modes → different skeletons → different evaluation.

## 2. Goals

1. Cut per-brief account-lead time from a named baseline (assumed 2 h — validated week 1) to **~50 minutes of total attention**: ~20 min input assembly (the manual folder drop — counted deliberately, because the MVP moves ingestion onto the account lead and hiding that cost would flatter the math) + ~30 min review and open-question resolution. Still a >55% cut; v2 integration removes the assembly line item.
2. **Raise the floor:** every draft conforms to the agency template, with every substantive claim traceable to a source passage.
3. Surface gaps and cross-source conflicts as **open questions** — the system never guesses.
4. Both pilot account leads (2/2) voluntarily use it on their next new project, and ≥3 additional leads request onboarding in month 2 (adoption, not mandate — absolute numbers; percentages on n=2 are theater).

## 3. Non-goals (MVP)

- **No *live* creative layer in v1.0 — shadow mode during the pilot.** Stage 2 consumes signed-off Stage 1 output; it cannot be validated on unvalidated briefs. During the pilot it runs in shadow: creative-brief drafts are generated from signed-off briefs for evaluation only, reviewed by a creative lead, never delivered into production. Promoted to live (v1.1) once draft-survival rate proves extraction quality.
- **No live integrations** (email, calendar, drive). MVP ingests from a local Input folder — manual drop. Integration is a v2 decision gated on the actual client stack (DR-4).
- **No regulated-client (S3) data in the pilot.** MVP runs on S0–S1 clients only; regulated clients onboard after the governance review (DR-11).
- **No auto-send.** Nothing reaches a client without human sign-off — by design, permanently.
- **No custom UI.** Folder + files + review checklist. The workflow is the product, not an app.

## 4. Named assumptions (validated week 1 of pilot)

| # | Assumption | Value | Validation method |
|---|---|---|---|
| A1 | Time per client brief today | 2 h | Ask account leads; sample 5 recent projects |
| A2 | New briefs per month | ~15 | Project intake log |
| A3 | Sources per project | 1 transcript (~60′), 1 RFP, 1 email thread, 1–2 background docs | Sample recent projects |
| A4 | Loaded labor cost | ~€19–20/h (€1,500 net ≈ €34k full employer cost / ~1,750 h) | HR confirm |
| A5 | Transcript source | Teams/Zoom auto-captions, mixed GR/EN | Confirm tooling |

## 5. Solution overview — the pipeline

```
Input folder (manual drop)
   │
   ▼
[1] INPUT READINESS GATE  (deterministic)
    minimum input set present? transcript full or summary? budget/timeline signal anywhere?
    → FAIL: system refuses to draft; returns "insufficient input — request X from client"
   │
   ▼
[2] CLASSIFICATION  (Haiku + confidence threshold)
    project type (advertising/creative vs other) + sensitivity tier (S0–S3)
    → low confidence: asks the human, never guesses
   │
   ▼
[3] TRANSCRIPT FIDELITY CHECK + GLOSSARY REPAIR  (Haiku)
    detect script-collapse artifacts (EN terms mangled into Greek script) → score → repair pass
    anchored on per-client glossary; low fidelity → flag, never silent consumption
   │
   ▼
[4] PER-SOURCE EXTRACTION  (Haiku, one pass per source)
    → structured JSON extracts, every field cites its source passage
    source provenance rules: transcript = what was said · RFP = what the client *claims* to need
    · emails = most recent state. Authority + recency ordering defined in the skeleton.
   │
   ▼
[5] CONFLICT DETECTION  (deterministic + LLM assist)
    RFP says budget X, kickoff said Y → never auto-resolved → becomes an open question
    with citations to both sources
   │
   ▼
[6] SYNTHESIS  (Sonnet, governed by SYNTHESIS.md — over compact structured extracts, not raw sources)
    → language-neutral brief schema: objectives, audiences, key messages, deliverables,
      timeline, budget, mandatories + OPEN QUESTIONS list
   │
   ▼
[7] BILINGUAL RENDER  (generate once, render twice)
    GR and EN rendered from the same schema — zero translation drift; glossary guarantees
    term fidelity (brand names, EN marketing terms survive in Latin script)
   │
   ▼
[8] HUMAN SIGN-OFF  (account lead)  ← the gate between stages
   │
   ▼  (only if classified advertising/creative, only on the SIGNED-OFF brief)
[9] CREATIVE LAYER  (v1.1 — Sonnet/Opus)
    SMP, core insight, think/feel/do, tone, RTBs, mandatories & no-gos
    + deliverables/formats per channel from a DETERMINISTIC SPEC TABLE (lookup, not generated)
    + readiness checklist (ask-don't-guess, stage-2 edition)
```

**The skeleton — 4 runtime instruction files (the proprietary thin layer):**
1. `SOURCES.md` — per-source extraction rules for the client-brief stage: ask-don't-guess, citation requirement, provenance/authority labeling, RFP-as-claim (shown in working detail as the concrete artifact).
2. `SYNTHESIS.md` — cross-source rules: conflict detection, authority + recency ordering, schema population, open-questions consolidation.
3. `TRANSLATION.md` — bilingual discipline: schema-first rendering, glossary enforcement, English-term fidelity checks, do-not-translate list.
4. `TRANSCRIPTS.md` — code-switching handling, script-collapse detection heuristics, fidelity scoring, repair protocol, full-transcript requirement.

*(Build-time governance — tiers, guardrails, non-goals as prohibitions — lives separately in the repo's `CLAUDE.md`, which instructs the coding agent, not the runtime pipeline.)*

## 6. Requirements

**P0 (MVP cannot ship without):** input readiness gate · per-source extraction with citations · conflict-as-open-question · synthesis to schema · bilingual render · open-questions list · sign-off checklist · S0–S1 scope enforcement · shadow-mode creative drafts on signed-off pilot briefs.
**P1 (fast follow, v1.1):** live creative layer on signed-off briefs · deterministic channel-spec table · readiness checklist.
**P2 (architectural insurance, v2):** ingestion integrations (Google Workspace API primary; Microsoft Graph if a client stack demands it) · per-client template variants · S2–S3 onboarding after governance review · brief archive → few-shot examples from the agency's own best briefs.

## 7. Success metrics

**Leading (pilot, weeks 2–4):**
- Time-to-first-draft: baseline (A1) → target <30 min of account-lead attention.
- **Draft survival rate:** % of AI-draft content surviving sign-off unchanged (edit distance). Target: >70% by pilot end.
- **Open-question precision:** % of flagged questions the account lead judges *real*. Target: >80% — this is the trust metric.
- Conflict catch rate on seeded test cases (retrospective projects have known answers).
- Voluntary adoption, in absolute numbers (n=2 — percentages would be theater): 2/2 pilot leads choose it for their next new project, and ≥3 additional leads request onboarding in month 2.
- Greek render register: pilot leads rate the EL render's naturalness (1–5) at each review, and the harness tracks asymmetric edit distance (EL edited systematically more than EN flags a register problem). "Bilingual quality" is a named trade-off — glossary byte-checks alone don't measure whether the Greek reads like agency Greek.

**Lagging (quarter 1):**
- Brief consistency (template conformance across authors — the variance story).
- Downstream signal: creative-team rework requests; client revision rounds per brief.
- Capacity returned: A1 × A2 × survival-adjusted factor → hours/year (quote the conservative floor).

## 8. Rollout & adoption

- **Week 1 — baseline & glossary.** Sit with account leads: validate A1–A5, build the per-client glossary *with them* (co-ownership = adoption lever #1). Confirm transcript retention (open question #3). **Plan B if full transcripts don't exist:** the pilot shifts prospective — record the next 2–3 kickoffs (with participant consent) while the retrospective leg runs on RFP + email + background only.
- **Weeks 2–3 — retrospective pilot.** 2 account leads × 3 *past* projects each, chosen *by them* (skeptics pick the battlefield). Side-by-side: Brief Builder draft vs the brief they actually wrote. Known outcomes = free evaluation set. Creative layer runs in **shadow** on the signed-off briefs — drafts reviewed by a creative lead for evaluation only, which also pulls the creative team into the story before anything ships to them.
- **Week 4 — live.** First real new projects. The lead owns sign-off; the tool drafts and asks.
- **Operator & handover — who, on what account, under what terms.** The pilot is operated by the AI specialist; by week 4, two named **brief champions** (ops/account coordinators) are trained on a one-page runbook (drop files → run one command → read the verdict → route the draft for sign-off). From pilot day 1 the system runs on **the agency's own Anthropic workspace** — Team/enterprise API account with DPA, zero-retention terms, EU processing, billed as a cost center — never on any individual's personal account or plan. The system must survive its author leaving — that is a design requirement, not an afterthought; v2 integration removes most operator steps.
- **Skeptic strategy:** the tool is positioned as *preparing* their judgment, not replacing it — its most visible output is the open-questions list, i.e. the thing that makes *them* look thorough in front of the client.
- **Past the pilot — surviving week 12.** An executive sponsor is named at kickoff and signs the pilot report. From month 2, new projects *start* from a Brief Builder draft by default — process embed, not tool option. Brief-quality metrics enter the monthly ops review. Novelty dies; the default setting is what remains.

## 9. The two biggest risks (as required) + mitigations

**R1 — Confidentiality (regulated clients).**
Mitigation stack: S0–S3 sensitivity tiers set **per client at onboarding** (process, not per-document vibe) → tier drives routing: S0/S1 standard cloud API; S2 restricted access + management-controlled visibility; S3 requires EU data residency / zero-retention enterprise terms — or stays out. MVP pilot is S0–S1 only. Human gate before anything external. Local-folder MVP means no standing integrations holding credentials. Production LLM substrate is an **enterprise API relationship, not a personal plan**: DPA in place, zero-data-retention terms, EU processing region, usage as a budgeted cost center — the same residency discipline applied to STT vendors applies to the model itself.

**R2 — Extraction errors / hallucination.**
The dangerous failure mode is not a missing quote — it is a *confident citation to garbage*: a garbled transcript poisons extraction, and the resulting brief looks verified precisely because it cites. Mitigation is therefore a **two-layer stack**. *Upstream (transcript integrity):* fidelity gate detects script collapse, number corruption, diarization anomalies, summary-instead-of-transcript, and truncation — annotate → flag → escalate to human → refuse; never silent consumption, never silent "repair" (full transcript required for backtracking, DR-5; vendor upgrade via weighted bake-off, DR-12). *Downstream (extraction discipline):* citations on every field → ask-don't-guess (gaps become open questions, never filler) → conflicts surfaced, never auto-resolved → deterministic spec table for channel facts → human sign-off as the final gate, placed *architecturally between* stages so stage-1 errors never propagate into creative. The sign-off works against the least-detectable error class (misattributed speakers) because every item carries `speaker_or_author` and the reviewing account lead **was in the meeting** — the gate pairs the system's traceability with a human witness. Out of MVP scope, stated deliberately: building or fine-tuning STT — the MVP doesn't fix transcription; it refuses to trust it blindly.

## 10. Cost model — deliberately the smallest line

Per brief: ~50–70K input tokens across sources. Extraction on Haiku (~$1/$5 per MTok) ≈ $0.07; synthesis + bilingual render on Sonnet (~$3/$15) over compact extracts ≈ $0.20–0.30. **Total <€0.50/brief; <€2 in an all-Opus worst case.** Against ~€38–40 of account-lead labor per brief (A1 × A4): **ratio ~75–80:1.** At ~15 briefs/month, annual API spend is double-digit euros.
Levers (already in the architecture): model tiering per stage; prompt caching on the static skeleton (−90% on cached input); extract-then-synthesize (cost and reliability *align* — the same design that shrinks tokens produces traceable intermediates); batch where latency permits (−50%).
**The real cost drivers are elsewhere: review time, adoption, glossary/template maintenance.** That is where management attention should go. And the labor ratio is deliberately the *floor* of the business case, not the case itself: the ~€5–6k/yr of returned hours merely funds the pilot — the prize is the variance floor and reduced downstream rework (creative rework cycles, client revision rounds), measured in Q1 and priced with real data rather than promised up front.

---

## 11. Decision Records — the defense armory

*Format: decision · options considered · why · reversibility · revisit trigger.*

**DR-1 — Skeleton on frontier API, not ad-hoc chat, not fine-tuning.**
Options: (a) "just use Copilot/ChatGPT we already have", (b) fine-tune a model on past briefs, (c) buy frontier models via API + build a thin instruction/process layer.
**Chosen: (c).** (a) fails on consistency — no readiness gate, no citations, no conflict detection; quality depends on who's prompting (the exact variance problem we're solving). (b) is premature: no training corpus of *good* briefs exists yet (quality varies by author — you'd fine-tune on the disease), cost/maintenance unjustified at 15 briefs/month. The skeleton *is* the product; models are commodity and swappable. **Two-way door** (skeleton is model-agnostic). Revisit: if volume 10×s or a curated gold-brief corpus emerges.

**DR-2 — Extract-then-synthesize, not single-pass.**
Options: one frontier call with all sources dumped in context vs multi-pass (per-source structured extraction → synthesis over extracts).
**Chosen: multi-pass.** Single-pass is opaque (no traceable intermediates), degrades on long mixed context, and is more expensive. Multi-pass yields citation-bearing intermediate JSON (auditability), isolates failures per source, and cuts cost. Cost and reliability align — this is the design's core argument. **Two-way door.** Revisit: never likely; single-pass has no advantage here.

**DR-3 — Model tiering per stage.**
Haiku for classification, fidelity check, per-source extraction; Sonnet for synthesis and bilingual render; Opus-class reserved for the creative layer if v1.1 evaluation shows compression quality needs it.
Why: 5× cost spread; extraction is schema-following (small model territory), synthesis and creative compression are judgment (big model territory). **Two-way door** — routing is a config line. Revisit: per-stage eval results in pilot.

**DR-4 — MVP ingestion = local Input folder; integrations deferred.**
Options: Google Workspace API · Microsoft Graph · MCP connectors · local email client (Thunderbird) as ingestion bridge · manual folder drop.
**Chosen: manual folder drop for MVP.** Every integration option forks on the client's stack (Google vs Microsoft), each with different auth, coverage (attachments!), and data-residency implications — a decision that should be made once, on facts, for v2 ("integration where possible" — the brief's own wording grants this). The folder also *is* the readiness gate's natural enforcement point. **Confirmed direction for v2: Google Workspace via API** — mail, attachments, photos, calendar, Drive files — because API access covers attachments and embedded files where MCP-style connectors currently don't; Microsoft Graph is the mirror path if a client stack demands it. **Two-way door.** Revisit: v2 kickoff, gated on client stack audit.

**DR-5 — Full transcript required, not meeting summary.**
Summaries destroy backtracking: a suspicious extraction must be traceable to the exact passage. Citations are only as good as the source's granularity. Fidelity scoring also needs raw text. **One-way-ish for the pilot evaluation** (retrospective projects without full transcripts can't be fully audited). Revisit: n/a — this is a standing data requirement.

**DR-6 — Schema-first bilingualism: generate once, render twice.** ⚠️ **One-way door.**
Options: draft in Greek then translate · draft in English then translate · extract to language-neutral schema, render both from it.
**Chosen: schema-first.** Translate-after drifts (two versions diverge on nuance) and doubles review burden. The schema is the system's data model — everything (renders, citations, edit-distance metrics, the creative layer's input) hangs off it. Changing it later breaks the archive, the metrics, and the glossary bindings. **This is the decision to get right up front.** Round-trip mitigation (Greek sources → EN canonical → Greek render): evidence anchors are stored verbatim in the source language and remain available to the render stage — the EL render is generated from the EN canonical *plus* the original Greek anchors, so nuance is re-anchored, not re-translated. The canonicalization step itself is governed by `SYNTHESIS.md`. Revisit trigger: agency template redesign (managed as a versioned migration).

**DR-7 — Channel specs from a deterministic lookup table, never generated.**
OOH dimensions, video specs per platform, print formats are *facts*. LLM generation of facts = hallucination surface with high downstream cost (wrong spec → wrong deliverable). Table maintained by the traffic/production team; model only *selects* rows. Deterministic core, thin AI edges. **Two-way door.** Revisit: never — generating facts is not a future feature.

**DR-8 — Human gate placed *between* stages; creative layer feeds only on the signed-off brief.**
The brief's own wording ("the *approved* client brief") makes this architectural: extraction errors cannot propagate into the creative layer because sign-off stands between them. Governance via pipeline topology, not policy documents. Also sequencing logic for the MVP: you cannot validate stage 2 on unvalidated stage-1 output. **Two-way door in code, one-way in trust** — removing the gate later would need a governance case, not a code change.

**DR-9 — Classification: small model + confidence threshold + human fallback.**
Auto-trigger "by project type" needs a classifier; misclassification either spams creative briefs or misses them. Cheap model classifies; below threshold it asks the account lead (one click). Ask-don't-guess applies to the system's *own* routing too. **Two-way door.** Revisit: threshold tuned on pilot data.

**DR-10 — Conflicts are surfaced, never auto-resolved.**
Cross-source contradiction (RFP budget ≠ kickoff budget) becomes an open question citing both passages. Auto-resolution would require the system to rank client truthfulness — a judgment that belongs to the account lead. This is also the answer to "why is the machine's brief better than the human's?": not better prose — **exhaustive cross-checking + honest gaps**, which a tired human at 7pm doesn't reliably do. **Two-way door.** Revisit: if pilot shows a class of conflicts with a deterministic resolution rule (e.g. "latest email always wins on logistics"), promote that rule into `SYNTHESIS.md` — cross-source authority is assembly-stage logic (SOURCES.md runs once per source, never across sources) — and as a *rule*, not model discretion.

**DR-11 — Sensitivity tiers S0–S3 set per client at onboarding; S3 excluded from MVP.** ⚠️ **One-way-ish door (taxonomy).**
Per-document classification is a vibe; per-client tiering at onboarding is a process. The tier taxonomy will be referenced by routing rules, access controls, and client contracts — changing it later is painful, so it's kept minimal (4 levels). Pilot on S0–S1 only: prove value where the blast radius is small, then onboard regulated clients with a governance review as a *feature* of the rollout story, not a caveat. Revisit: governance review before first S2/S3 client.

**DR-12 — Transcript fidelity gate + glossary repair; STT source strategy.**
Mixed GR/EN meetings inflate WER and produce script collapse exactly on the tokens the brief most needs (English terms, brand names, numbers). Trusting transcripts blindly poisons every downstream citation. A cheap detection + glossary-anchored repair pass costs ~nothing and protects the whole pipeline. Validated empirically on real Greek/English audio rather than vendor benchmarks. **Two-way door** — and deliberately so: the fidelity gate sits downstream of *any* STT source, so the transcription vendor is a swappable module, not a dependency.

*Sub-decision A — MVP transcript source: platform captions.* Teams/Zoom auto-captions are free, already running, and require no procurement. Their GR/EN code-switching quality is mediocre — which is exactly why the fidelity gate + glossary repair exists. MVP accepts imperfect input and compensates downstream rather than blocking on a vendor decision.

*Sub-decision B — Upgrade path: dedicated STT, selected by bake-off, not by datasheet.* No vendor publishes Greek↔English code-switching accuracy; vendor benchmarks are quoted on clean single-language speech. Selection method: run the agency's own recorded meetings through the candidates and score on a **weighted high-value-token metric** (decisions, owners, dates, numbers, brand names) plus a dedicated **English-term fidelity check** (did "deploy", "KPI", "brand awareness" survive in Latin script?) — never raw WER. Candidates, positioned honestly:

| Vendor | Position | Watch-out |
|---|---|---|
| ElevenLabs Scribe | Strongest independently measured code-switching accuracy | EU data residency on enterprise tier only |
| Gladia / Soniox | EU-hosted; explicitly support GR/EN code-switching | Verify on our audio, not their demo |
| Google (Gemini Flash / Cloud STT) | Cheapest path; natural fit if the agency runs Google Workspace (v2 stack) | Confirm data-residency & retention terms for S2+ |
| Omilia | Greek-native enterprise vendor; telephony/contact-center strength | Enterprise procurement weight — likely v2, call channel |
| Self-hosted Whisper/Parakeet | Full GDPR control, fine-tunable on agency jargon | Build/maintain cost only justified if a hard on-prem mandate appears |

Buy-first verdict transfers from prior analysis: at this volume STT cost is trivial, so **accuracy and EU residency drive the decision, not price**; build only if forced.

*Sub-decision C — The call channel (v2): a goldmine behind a legal gate.* Client *phone calls* carry the freshest state — budget changes and scope pivots agreed by phone that never reach email — and today they are invisible to briefing: the single biggest untapped input source. But calls differ from meetings in two hard ways: (1) **consent/GDPR** — recording calls requires notification and a lawful basis under Greek law; legal review is a prerequisite, not a checkbox; (2) **audio quality** — PSTN/mobile codecs degrade STT far more than meeting audio, which is where telephony-grade vendors (Omilia territory) earn their place. Sequencing: v2, after legal review, with the same bake-off run on *real call audio*, not meeting audio. Revisit trigger: first client whose engagements run primarily by phone.

---

## 12. Open questions (for the discussion, honestly held)

1. Agency template: does one canonical client-brief template exist, or does "template" itself vary by team? (If it varies, template consolidation is week-1 work and a hidden win.)
2. Who owns the glossary and spec table long-term? (Proposal: traffic/production owns specs; account leads own client glossaries.)
3. Transcript tooling: what does the agency actually record with today, and does it retain full transcripts? (Determines whether the fidelity gate is a filter or a vendor conversation.)
4. Volume reality check: is ~15 briefs/month right, and how seasonal is it?
