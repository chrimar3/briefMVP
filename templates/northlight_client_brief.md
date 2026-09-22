<!--
Northlight client-brief template — ENGLISH document (brief_en.md).
The Greek document follows templates/northlight_client_brief.el.md, section for section.

How to use this file:
- Copy every heading, label, banner and fixed sentence below CHARACTER-EXACT. The runner checks
  them against templates/northlight_client_brief.labels.json; a re-worded heading fails the run.
- Replace only the {curly-brace instructions}. Never render an instruction, and never render this comment.
- Where the template offers alternatives ("exactly one of"), render exactly one line and drop the rest.
- Internal metadata (project type, sensitivity tier, readiness, pipeline) goes ONLY in the final
  Internal section. The client-facing part above it never shows it, and never shows a raw enum value
  such as ready_for_review or advertising_creative.
-->
# Northlight Communications — Client Brief

{status banner — exactly one of these two lines, chosen from signoff.status:}
> **DRAFT — pending account-lead sign-off**
> **SIGNED OFF by {signoff.signed_by}, {date part of signoff.signed_ts}**

**Client:** {client company name, written as the glossary writes it — never the client_id} · **Project:** {meta.project_id}
**Sources used:** {one item per meta.sources entry: source_id (source_date), joined with " · "}

## 1. Objectives
{Resolved-conflict lines first — one per conflict with status "resolved_by_human" whose field is this
section's field, written exactly as:
- **Resolved by the account lead:** {conflict.resolution} {one [source_id location] tag per conflict position}
Then one line per entry: - {entry} [{source_id} {location}] — source_id exactly as in meta.sources,
e.g. [kickoff_call 00:12:05] [client_rfp §4].
If the section has neither a resolved-conflict line nor an entry, render only this blockquote:}
> No confirmed entries — see Open Questions.

## 2. Audiences
{same rules as section 1}

## 3. Key Messages
{same rules as section 1}

## 4. Deliverables
{same rules as section 1}

## 5. Timeline
{same rules as section 1; conditional items visibly hedged}

## 6. Budget
{same rules as section 1; figures exactly as stated in content — never totalled, never converted, a
spoken hedge keeps its hedge}

## 7. Mandatories & No-gos
{same rules as section 1}

## ⚠ Open Questions for the Client
{Numbered, in the brief's order, one item per open question. An open question the work order lists
as ANSWERED BY A RESOLUTION renders like this:
N. **{field} — {short title of the gap}** ✓ Answered by the account-lead resolution
   Gap as raised: {gap} [{linked_evidence tags}]
   Resolution: {the linked conflict's resolution}
   Original question (answered — do not ask as written): «{suggested_question_for_client}»
Every other open question renders like this:
N. **{field} — {short title of the gap}**
   Gap: {gap} [{linked_evidence tags}]
   Why it matters: {why_it_matters}
   Suggested question: «{suggested_question_for_client}»}

{Conflicts heading — only when the brief has conflicts; exactly one of these two lines:
the first while ANY conflict has status "open", the second when EVERY conflict is "resolved_by_human".}
## ⚠ Unresolved Source Conflicts (the account lead resolves these before sign-off)
## ⚠ Source Conflicts — Resolved by the Account Lead
{For each conflict:
**Field: {field}** — status: {open | resolved}
- Position A: {statement} [{source_id} {location}]
- Position B: {statement} [{source_id} {location}]
{…one line per further position (C, D, …)}
{only for a resolved conflict:}
- Resolution: {resolution}
- Resolved by: {resolved_by}}

## Sign-off
Account lead: ____________  Date: ________  Edits made: {signoff.edits_summary, or leave blank}

## Internal — not for the client
**Project type:** {Advertising creative | Other | Unclassified — ask the account lead} · **Sensitivity tier:** {meta.sensitivity_tier}
**Fields with evidence:** {readiness.fields_with_evidence}/7 · **Readiness:** {Ready for review | ⚠ Thin input — return to the client}
**Generated:** {meta.created_ts} · **Pipeline:** {meta.pipeline_version}
