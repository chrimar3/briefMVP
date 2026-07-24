# Tier 4 — Stretch: shadow creative A/B · **GREEN**

**Date:** 2026-07-24 (Friday, before the Saturday-noon cutoff) · **Branch:** `main`
**Run:** `runs/tier3` (Stage 2 on the signed brief) · **Preceding commit:** `265ca46`

The optional tier. On the human-signed brief, `creative-shadow` produced two creative-brief
drafts — sonnet vs opus, identical input — with every channel spec drawn from a deterministic
lookup table, never generated. Shadow mode: evaluation drafts, never for delivery.

---

## 1. DoD

| # | Criterion | Result |
|---|---|---|
| 1 | Human sign-off precedes Stage 2 (agent never signs off) | ✅ `signoff.status = signed_off`, signed by the account lead; `creative-shadow` refuses otherwise |
| 2 | Both drafts produced (A/B sonnet vs opus, identical signed brief) | ✅ `creative_brief_sonnet.md`, `creative_brief_opus.md` |
| 3 | Channel specs match the table byte-for-byte (no generated specs) | ✅ both drafts clean on the first attempt; every spec-shaped token traces to `config/channel_specs.json` |
| 4 | Usage note comparing the two runs | ✅ §4 |
| 5 | `runs/tier_4_report.md` | ✅ this file |

```
# human action (not the agent):   signoff.status → signed_off   (+ 3 conflicts resolved)
python3 pipeline/runner.py --project fixtures/northlight_01 --stage creative --run-id tier3
    → creative-shadow sonnet  · 1 attempt · clean
    → creative-shadow opus    · 1 attempt · clean
python3 -m pytest -q   → 215 passed, 6 skipped
```

## 2. The two deterministic guarantees (a model cannot self-enforce these)

**Sign-off gate (DR-8).** `creative.require_signed_off` refuses unless `signoff.status ==
"signed_off"`. Stage-1 errors cannot propagate into creative because the human gate stands
between the stages in *topology*, not policy. Confirmed: the stage read the signed brief and ran;
on the draft brief it would have refused.

**Spec table (DR-7).** Channel dimensions, aspect ratios and file types are facts, not creative
decisions. They live in `config/channel_specs.json` (owned by traffic/production; a stub for the
pilot). The model *selects* rows and tags each with its id (`[spec: instagram_reel]`); it never
writes a spec value. `check_creative_brief` scans each draft for any spec-shaped token
(`1080x1920`, `9:16`) and fails the run if one is not in the table byte-for-byte. This is the
Tier-4 machine check, and it is what makes "no hallucinated specs" a property rather than a hope.

## 3. The A/B — same brief, same skeleton, only the model moves

Both drafts carry the full eight-section structure (SMP · core insight · think/feel/do · tone ·
RTBs · mandatories & no-gos · deliverables & specs · readiness checklist), the shadow banner, and
correct handling of every seeded trap:

- **Retracted OOH/metro** — neither commits it as a deliverable (it appears only as an example
  use-case for key visuals).
- **Speculative TikTok dance** — both mark it explicitly conditional and "not a commitment".
- **Superseded RFP positions** — opus adds a traceability note confirming Gen Z 18–24, October,
  and €90k-media-inclusive were *not* promoted (the human resolved those conflicts to 25–40,
  15 September, and production-in-the-eighties-excl-media at sign-off).

| Dimension | sonnet (`claude-sonnet-5`) | opus (`claude-opus-4-8`) |
|---|---|---|
| Length | 6,994 chars | 8,525 chars |
| Spec rows cited | 2 (TikTok in-feed, key visual) | 5 (all: TikTok, IG reel/story/feed, key visual) |
| Framing | lean, decisive; one clear proposition | fuller; explicitly flags the SMP as a shadow candidate and that no client-agreed SMP exists yet |
| Self-audit | trap-correct, cites entries | adds a closing traceability note (every claim → entry; no spec generated; superseded positions not promoted) |
| Cost | **$0.27** | **$0.47** |

**Read for the defense:** on this brief the models differ in thoroughness, not correctness — both
are trap-clean and spec-clean. Sonnet gives a tighter, more committed draft; opus gives broader
channel coverage and more explicit hedging about what the brief does *not* yet contain. For shadow
evaluation (a creative lead reviewing), opus's self-auditing verbosity is the safer default and
its ~1.7× cost is trivial in absolute terms; sonnet is the better pick if a lead wants a sharper
single proposition to react to. Routing is a config line (DR-3), so this is a per-use choice, not
an architecture decision.

## 4. Usage & cost

| Step | Model | Attempts | Cost |
|---|---|---|---|
| Re-render signed brief (banner → SIGNED OFF, resolved conflicts) | `claude-sonnet-5` | 1 | $1.27 |
| creative-shadow — sonnet | `claude-sonnet-5` | 1 | $0.27 |
| creative-shadow — opus | `claude-opus-4-8` | 1 | $0.47 |
| **Tier-4 total (accepted path)** | | | **$2.01** |

Plus ~$1.23 on a discarded first A/B that surfaced the gate bug in §5. The creative A/B itself is
**$0.74** for two full creative briefs — the compression stage is cheap; the earlier Stage-1
figures dominate a per-brief cost.

## 5. One gate false-positive found and fixed — durations are not aspect ratios

The first A/B run had both models fail the spec gate on the first attempt. Cause: the aspect-ratio
detector (`\d{1,2}:\d{1,2}`) matched **video timecodes** — `00:03`, `00:06`, `00:10` (a
three/six/ten-second cut) — as if they were aspect ratios absent from the table. The repair loop
"recovered" by forcing both models to strip legitimate durations, which is the gate corrupting
good content rather than catching bad content.

Fixed: aspect ratios in this domain have no leading zeros (9:16, 4:5, 16:9); timecodes do
(00:06). Requiring both sides to start 1–9 excludes timecodes while still catching an invented
aspect ratio (16:9 when the table holds only 9:16) — verified by
`test_invented_aspect_ratio_is_still_caught_after_the_timecode_fix`. After the fix both drafts pass
**clean on the first attempt**. This is the fourth gate false-positive found across Tiers 3–4
(markdown boundaries, `internal_conflicts` anchors, and now timecodes) — all the same shape: a
deterministic gate too narrow for valid model output, each closed with a regression test.

## 6. Model versions — observed this tier

| Role | Alias | Resolved |
|---|---|---|
| `creative-shadow` (A) | `sonnet` | `claude-sonnet-5` |
| `creative-shadow` (B) | `opus` | `claude-opus-4-8` |
| `render` (re-render) | `sonnet` | `claude-sonnet-5` |
| Orchestrator | `opus[1m]` | `claude-opus-4-8[1m]` |

The A/B runs the *same* creative-shadow definition; only `model_override` differs
(`agents.build_inline_agent(..., model_override=...)`). Everything else — prompt, skeleton, signed
brief, spec table — is held constant, so the drafts isolate the model.

## 7. Notes

- **Drafts are shadow-mode artifacts** and are gitignored like all run outputs (only tier reports
  are tracked). They live at `runs/tier3/creative/creative_brief_{sonnet,opus}.md` locally. This
  report is the committed record; excerpt them for the deck as needed.
- **Spec table is a stub** — synthetic but plausible values, clearly labelled. A real deployment
  points the same lookup at traffic/production's live table; the gate logic is unchanged.
- **Nothing was delivered.** Every draft leads with the shadow banner; this stage exists to prove
  the shape and the guardrails, not to ship creative.

---

**Tier 4 DoD: 5/5 green. Tiers 0–4 complete. Stopping for human review.**
