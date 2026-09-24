# Pilot investment and net return — worksheet

Status: planning worksheet for the sponsor and agency management, 2026-09-23. It answers the
question the return figures leave open: what the four-week pilot costs the agency, and after how
many briefs the time comes back. It feeds go-live decision D-27 (cost estimate and spending
ceiling; default **no start**) in `GO_LIVE_DECISIONS.md`. Every hour below is a **planning
figure**, not a measurement: the pilot's own effort records (`EFFORT_RECORDING.md`) replace them.
Rates other than the account-staff rate, seats and usage are **OWNER TO FILL**.

## 1. What the pilot asks of each role

Brief counts come from `SCORECARD.md` §5: 6 retrospective briefs in weeks 2–3 (2 leads × 3), and
live briefs in week 4. The adoption rule needs a live brief from each lead, so the low case has
2 live briefs; the high case has 4 (a planning upper bound). Per-brief minutes come from the time
budgets of `PILOT_RUNBOOK.md` where it sets one (assembly ≤ 20, review < 30, verdict 2, record 2);
the others are proposals marked as such. The high case doubles every per-brief figure, because
the targets are what the pilot tests, not what it can assume.

| Role (people) | Per brief, at target | Basis | Fixed work, weeks 1–4 | Total, low – high |
|---|---|---|---|---|
| Account leads (2) | retro 67 min: assembly 20 + review 30 + record 2 + retro side-by-side 15; live 52 min | runbook budgets; side-by-side is a proposal (`SCORECARD.md` §2) | 4.75 h each: A1 validation 1 h, retro projects and their known conflicts 0.75 h, glossary session 1 h, T-07 rehearsal 1 h, `ACCOUNT_LEAD_CARD.md` walkthrough 0.5 h, week-3 checkpoint 0.5 h | 17.9 – 29.8 h (both leads) |
| Operator (1) | 10 min: start the run, draft copy and `agency init`, scorecard row | runbook steps 3 and 5 (2 + 2 min) plus a proposal | 15.5 – 20.5 h: preflight and account 2–4, glossary sessions 2, T-06 training 2–3, T-07 support 2, T-08 support 1, checkpoint preparation 2.5, pilot report draft 3–5, retention at pilot end 1 | 16.8 – 23.8 h |
| Brief champions (2) | 30 min: keys the decision commands beside the lead (`ROLES.md`) | the lead's review budget; the rehearsal has 17 lead decision commands per brief | 7 h: T-06 training and one timed rehearsal each (5 h), T-07 keying (2 h) | 11.0 – 17.0 h (both) |
| Bilingual reviewer (1) | 15 min: `agency attest` | proposal (counted inside `review_min` until D-21) | 0.5 h onboarding | 2.5 – 5.5 h |
| Traffic (1) | 15 min: deliverable rows, first-handoff record | proposal | 2 – 4 h: verified spec catalog for release (`CREATIVE_DELIVERY.md`) | 4.0 – 9.0 h |
| Creative lead (1) | 20 min: review and strike the creative draft | proposal | 1 h: T-08 release rehearsal | 3.7 – 7.7 h |
| Data-protection lead (1) | 10 min: screening sign-off per project | proposal (`DATA_PROTECTION.md` §10) | 4 – 8 h: pack review, D-07, D-09, D-12, record-of-processing entry | 5.3 – 11.3 h |
| Executive sponsor (1) | — | — | 4.5 – 6 h: five checkpoints (`PILOT_RUNBOOK.md`), go-live sheet, pilot report | 4.5 – 6.0 h |
| Agency management | — | — | 3 – 6 h: D-02, D-03, D-05, D-23, D-27, D-28 | 3.0 – 6.0 h |
| **All roles** | | | | **68.8 – 116.2 h** |

Arithmetic: total = fixed + per-brief minutes × briefs ÷ 60; low = 6 retro + 2 live at target,
high = 6 retro + 4 live at twice the target. The table counts live-brief minutes as cost although
a live brief would be written anyway (about 120 minutes today, PRD A1), so it overstates the net
cost of week 4.

## 2. What the hours cost

| Item | Low | High | Basis |
|---|---|---|---|
| Account-lead hours at A4 (€19–20 / h) | €340 | €596 | 17.9 h × €19; 29.8 h × €20 (PRD §4) |
| Every role at the account-staff rate (a floor: most roles are more senior) | €1,307 | €2,324 | 68.8 h × €19; 116.2 h × €20 |
| Other roles at their own rates | OWNER TO FILL | OWNER TO FILL | agency payroll data |
| Seats or usage | see §3 | see §3 | D-05, T-02 |
| Setup, maintenance, support outside the hours above | OWNER TO FILL | OWNER TO FILL | `WALKTHROUGH.html` sheet 10, decision 3 |

## 3. Seats and usage (measured on synthetic fixtures, 2026-09-24)

- Seats (option A, `OPERATING_TERMS.md` §c): the operator and two champions, plus any decision
  roles D-28 seats. Fee per seat and usage window: OWNER TO FILL (D-05).
- Usage per brief under the current routing (round-2 live re-baseline, `runs/r2-live`,
  `python3 eval/cost_report.py runs/r2-live`; tokens across every attempt, all complete runs):
  northlight_01 mean 695,991 (596,699–768,929, n = 3); voreas_02 mean 1,291,833 (1,269,032–1,314,634,
  n = 2 complete of 3 rolls); levanta_03 887,505 (n = 1); pooled 926,524, about 90% sonnet
  (`docs/COST_MODEL.md` §1). No run was clean: each needed at least one repair.
- Usage for the pilot, **estimate**: 8–10 pilot briefs × 926,524 ≈ 7.4–9.3 M tokens, plus
  refusals: 1 of 7 graded rolls was refused at synthesis after using 649,965 tokens
  (`docs/COST_MODEL.md` §2). T-02 still measures the per-brief usage, refusal and resume rate on
  the pilot's own inputs, which are neither synthetic nor seeded.
- Historical, Haiku-era (July): 984 820 tokens for Stage 1 of the graded run, 1 134 734 with the
  two-model creative A/B (`runs/tier3`; `docs/COST_MODEL.md` §3). Not a planning figure.

## 4. Net return and break-even

The published floor counts account-lead minutes only: (120 − 50) min × 180 briefs ÷ 60 =
210 h a year, about €3,990–4,200 at A4 (`docs/COST_MODEL.md` §4). That is 70 minutes, about
1.17 h or €22–23, per brief. Two corrections apply before it can be weighed against §1–§3:

- **Tier 5–7 role minutes.** The agency layer adds minutes for the bilingual reviewer, traffic,
  the creative lead, champions and the operator. The net measure is per brief,
  `baseline_team_min − total_team_min`, reported by `eval/pilot_scorecard.py` as
  `net_team_minutes` from the retro rows (`SCORECARD.md` §3). Every 10 minutes of added non-lead
  time per brief at steady state removes 30 h a year (10 × 180 ÷ 60), about €570–600 at A4. If the
  added team minutes reach 70 per brief, the lead-only floor is used up.
- **Usage.** Seats or metered usage (§3) are a running cost the hours figure does not include.

Break-even of the pilot's hours, in briefs, is `pilot hours × 60 ÷ net minutes saved per brief`,
and in months at PRD A2 (about 15 briefs a month):

| Net minutes saved per brief | Briefs to recover 68.8 – 116.2 h | Months at 15 briefs / month |
|---|---|---|
| 70 (lead-only floor) | 59 – 100 | 3.9 – 6.6 |
| 50 | 83 – 139 | 5.5 – 9.3 |
| 30 | 138 – 232 | 9.2 – 15.5 |

Usage and seat cost (§3) lengthen these periods once T-02 has measured them.

## 5. What is not priced

The documents call the variance floor and reduced downstream rework the real prize (PRD §10;
`docs/COST_MODEL.md` §4). It is not priced here. The pilot counts it only through the retro
side-by-side (`SCORECARD.md` §2), and downstream rework waits for quarter 1 (D-19). "Brief quality
varies by author", the premise of that prize, is itself an assumption (`SCORECARD.md` §5a).
