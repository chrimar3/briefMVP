# Pilot report — template and end-of-pilot decision rubric

The executive sponsor signs this report at the end of week 4 (PRD §8; `ROLES.md`). The operator
drafts it from `python3 eval/pilot_scorecard.py $PILOT/scorecard.csv --output report.json`, the
incident log and the effort records. Copy this file to the pilot location; it never holds client
names (leads are L1/L2, `SCORECARD.md` §6). Sections map one to one onto the scorecard output.

## 1. Decision

Scale / Extend / Stop (section 9 rubric): ______ · Sponsor: ______ · Date: ______

One paragraph: what was decided, and the one number that decided it.

## 2. Scope as run

Weeks, briefs (retro n, live n, manual fallbacks n), roles filled (D-01), account and data terms
in force (D-02, D-03), data class of every project (`approved` with reference), deviations from
`PILOT_RUNBOOK.md`.

## 3. Pass rules (paste `pass_rules` from the report)

| Phase | Rule | Target | Observed | n | Status |
|---|---|---|---|---|---|
| end of week 3 (retro) | `assembly_le_20`, `review_under_30`, `total_attention_le_50`, `question_precision_gt_80`, `critical_errors_zero`, `schema_valid_all`, `retro_set_complete` | `SCORECARD.md` §4 | | | pass / fail / insufficient_data |
| end of week 4 (live) | the same, plus `survival_en_gt_70`, `survival_el_gt_70`, `adoption_2_of_2` | | | | |

`insufficient_data` is never a pass. The week-3 stop rule applied? yes / no.

## 4. Reported measures (paste `pass_rules.reported`)

- Net lead minutes and net team minutes per retro brief (`net_lead_minutes`, `net_team_minutes`;
  say whether complete).
- Agency steps inside review time (`agency_steps_min`, share of `review_min`).
- Retro side-by-side sums and per-brief means (`retro_side_by_side`): the variance-floor evidence.
- Recalled against timed baseline (`baseline_check`).
- Canonical survival beside render survival (`survival_canonical_pct`).
- Manual fallbacks (count, share), refusals and resumes, creative strikes, approvals, releases,
  withdrawals, separation-of-duties waivers (must be 0 on PILOT rows).

## 5. Incidents

From the incident log (`INCIDENT_RECOVERY.md`): each incident, class, time to withdraw or contain,
client impact, whether it was an immediate-stop event.

## 6. Usage and cost

| Item | Planned (`PILOT_INVESTMENT.md`) | Actual |
|---|---|---|
| People hours by role | 68.8 – 116.2 h | from effort records |
| Tokens by model per brief | [T-02 PLACEHOLDER] | `python3 eval/cost_report.py $PILOT/runs` |
| Usage window consumed / seats | D-05 | |
| Spend against the D-27 ceiling | ceiling: ______ | |

## 7. Assumptions re-validated

A1 (time per brief today), A2 (briefs per month), A4 (loaded cost) as validated in week 1;
capacity returned recomputed with them (`SCORECARD.md` §3); the net team figure beside it; and the
premise "brief quality varies by author", read from the side-by-side counts per lead.

## 8. Threats to validity and open defects

For each threat in `SCORECARD.md` §5a, how much it may have moved the result. The T-03 status: which
voreas defects remain, which manual checks covered them, any sponsor exception recorded.

## 9. Decision rubric (proposal; the sponsor decides, OWNER TO CONFIRM)

| Decision | When | What follows |
|---|---|---|
| **Scale** | Both gates `pass` (end of week 3 and end of week 4, including 2/2 adoption and survival), no immediate-stop incident, spend within the D-27 ceiling | Month-2 default start (PRD §8) under a separate sponsor approval; the month-2 onboarding count is tracked, not required |
| **Extend** | No `fail` on `critical_errors_zero` or `schema_valid_all`, no immediate-stop incident, and either a gate is `insufficient_data` or exactly one timing, precision or survival rule failed | Two to four more weeks on the same scope, with the change to test named in advance and a new ceiling if needed; this report is still signed |
| **Stop** | Any `fail` on `critical_errors_zero` or `schema_valid_all`, any immediate-stop incident, `adoption_2_of_2` failed, two or more rules failed, or the D-27 ceiling exceeded | The pilot ends; retention at pilot end (D-07); the findings stay in the report |

A week-3 stop (the stop rule of `SCORECARD.md` §4) means week 4 did not go live; the report is
written on weeks 1–3 and the rubric is read on the week-3 gate alone.

## 10. Signature

Sponsor: ______ Date: ______ · Operator (author): ______ · Data-protection lead (sections 2, 5): ______
