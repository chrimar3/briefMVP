# Data protection preparation pack (DPIA inputs)

Status: preparation record for the agency's data-protection lead (DPO or equivalent), 2026-09-23.
It is not legal advice and it authorizes nothing. The repository still processes synthetic
fixtures only (`CLAUDE.md` rule 4); real client data needs the agency's data-policy approval
(owner decision 4, `docs/OPERATING_DECISIONS.md` 2026-09-22). Every legal judgement below is
marked **OWNER/DPO TO CONFIRM**; the facts about the software are checked against the code and
cite it. Open items are consolidated in `GO_LIVE_DECISIONS.md`.

## 1. Controls that exist today (code, not policy)

| Control | Where | What it does |
|---|---|---|
| Data declaration | `pipeline/data_policy.py`; runner exit 6; intake `--data-class` | A project folder without a valid `data_declaration.json` is refused before any source is read. `approved` requires `approval_ref`, `approved_by`, `approved_on`; approved projects, their client config and run output must be outside the repository. The run manifest records the declaration. |
| Data-protection preconditions on the declaration | `pipeline/data_policy.py` (`PRECONDITION_FIELDS`) | An `approved` declaration may record `screened_by` and `screened_on` (§10), `processor_ref` (the filed processor terms, D-03) and `dpia_ref` (the DPIA or screening decision, D-09). All four are required for `approved` (`REQUIRE_PRECONDITIONS`, round 2 phase B): non-empty, `screened_on` an ISO date not in the future; a declaration missing one is refused (exit 6). `pipeline/intake.py` writes them from `--screened-by`, `--screened-on`, `--processor-ref`, `--dpia-ref`. Synthetic declarations carry none of them. |
| Advisory personal-data pre-screen | `pipeline/prescreen.py`; `config/prescreen_terms.json` | `python3 -m pipeline.prescreen PROJECT_DIR` counts, per source and category, the lines carrying e-mail addresses, phone numbers, IBAN-like strings, or Greek/English special-category terms (Art. 9, Art. 10, children). It records counts and line numbers, never the matched values; it never blocks. The runner also records it in every run manifest (`prescreen`), over the declared sources only (never another file in the folder). An aid for the §10 screening, not a control. |
| CLI session persistence off | `pipeline/agents.py` (`--no-session-persistence`; round 2, phase B) | Runtime agents run with session persistence disabled, so no transcript of the sources is kept in the operator's Claude Code profile. The flag exists in the CLI version the flags were checked against (2.1.280, `claude --help`); an older CLI is refused before any stage runs, and each run manifest records the CLI version (`cli`). Offline-verifiable: the argv is tested; that the CLI honours the flag is confirmed on the first live run. Runs made before the flag was added (every committed run) did keep transcripts; retention lists their session IDs (§6). |
| Sensitivity tier | `gates.enforce_sensitivity_tier`, schema enum S0/S1 | S2/S3 clients are refused at intake and on every run and agency read. |
| Answer-key exclusion | `gates.HARNESS_ONLY_FILES`, `revisions.capture_evidence` | The grading key is never a source or an evidence copy. |
| Release minimisation | `pipeline/delivery.py` release | Packages carry the approved creative and deliverable rows only: no raw sources, evidence, glossary, audit notes or paths. |
| Retention inventory and purge | `pipeline/retention.py` | Finds every copy of a source (evidence/, history/, the staged `inputs/` copies agents read, packages), deletes on instruction, writes a tombstone; never deletes committed evidence unless explicitly named; never deletes a run's `audit_log.jsonl` silently (a source purge never touches it; a run purge records its hash, entry count and chain head in the tombstone first). |
| Pseudonymised scorecard | `SCORECARD.md` §6 | Leads appear as L1/L2; the name mapping stays outside the repository. |

Not implemented (open, §11): speaker pseudonymisation before extraction, and any blocking
personal-data control (the pre-screen above is advisory by design).

## 2. Personal-data inventory

| Data subjects | Categories | Where it enters | Where it persists |
|---|---|---|---|
| Client staff (meeting participants, e-mail senders and recipients, RFP authors) | Names, roles, speaker labels, verbatim statements, e-mail header names, signatures if pasted | Transcripts, e-mail threads, RFPs | `extracts/*.json` (`speaker_or_author`, verbatim `anchor`), `brief.json` (conflict positions such as "X stated …", question text), renders, review HTML, `evidence/` copies, `history/` |
| Third parties named in meetings (other agencies, suppliers, board members) | Names, roles, opinions attributed to them | Transcripts, e-mails | As above |
| Agency staff | Names as actors; decisions; minutes of effort; handoff outcomes | Human commands (`--actor`), `pipeline.effort` | `approval.json`, `language_review.json`, `creative_draft.json`, `creative_approval.json`, `amendments.json`, `clarifications.json`, `coverage_decisions.json`, `releases.json`, `approval_withdrawals.json`, `effort.json`, `brief.json` (`signoff.signed_by`, `conflicts[].resolved_by`), scorecard CSV (pseudonymised) |
| Consumers / audiences | Aggregate descriptions only (e.g. an age band); no individual consumer data is expected | RFPs, research | As client staff data |

Special categories (GDPR Art. 9) and criminal-offence data (Art. 10) are not needed for any
brief field; they could still appear incidentally (for example a health remark in a meeting).
The screening step in §10 exists for that case.

## 3. Flow map: what leaves the machine

Every model stage runs `claude -p` (`pipeline/agents.py`) on the account the Claude Code CLI is
signed into; the agent reads files by path, so the file contents reach the model provider.

| Stage | Reads (work order) | Personal data sent to the model provider | Written locally |
|---|---|---|---|
| Intake, readiness gate, conflict pass, agency/delivery/effort commands | local files | none | project folder, run directory |
| 2 classify | every source (`stages.py` work order) | all of it | `classification.json` |
| 3 fidelity-check | each transcript | speaker names, statements | `fidelity/` (annotated copy) |
| 4 extract | one source (annotated transcript) + glossary | all of it | `extracts/`, `diagnostics/` |
| 4b verify-extract | the source + its extract | all of it | `verification/` |
| 6 synthesize | extracts (not raw sources) | quoted anchors, speaker attributions | `brief.json` |
| 7 render | `brief.json` + glossary + template | quoted anchors, names in positions/questions | `brief_el.md`, `brief_en.md`, HTML views |
| 9 creative | signed `brief.json` + spec table | as render | `creative/` |

Runtime agents hold Read/Write tools over the directories the runner grants
(`runner._access_dirs`); the scope-narrowing work is in `docs/SECURITY.md` (round-1 W2).
Processor terms for this flow: §8. Retention on the provider side depends on the account
terms: **OWNER/DPO TO CONFIRM** (`OPERATING_TERMS.md` §c).

## 4. DPIA screening inputs

Whether a full DPIA (Art. 35) is required: **OWNER/DPO TO CONFIRM**. Inputs against the
regulators' usual screening criteria (EDPB/WP248 list):

| Criterion | Assessment input |
|---|---|
| New technology | Yes: large language models process client documents. |
| Systematic monitoring of employees | Only if effort records are used about individuals; §9 limits the purpose so that they are not. |
| Evaluation or scoring of people | Not intended; effort and quality metrics are per brief and role. |
| Sensitive data | Not intended; incidental occurrence handled by §10. |
| Large scale | No: a four-week pilot, 2 leads, about 6 retro and a few live briefs (`SCORECARD.md`). |
| Vulnerable subjects | Employees (power imbalance) for effort data; no children expected. |
| Matching or combining datasets | No. |
| Transfer outside the EEA | Depends on the account and processing region: **OWNER/DPO TO CONFIRM**. |
| Prevents exercise of rights | No automated decision about individuals; every decision is a named human's. |

**Hellenic DPA list (Art. 35(4)).** The Hellenic Data Protection Authority's Decision 65/2018
lists the processing operations for which a DPIA is mandatory in Greece. Screen this processing
against that list as well as against WP248. Items to check first, given §2 and §9: innovative use
of new technology (language models on client documents), systematic monitoring or evaluation of
employees (effort records, if ever used about individuals), processing of special-category data
(incidental only, §10), and combination of datasets (none intended). The list's exact wording must
be read from the Authority's own publication, not from this summary, and the result of the check
is **OWNER/DPO TO CONFIRM** (D-09).

Risk and measure pairs for the DPIA, if one is run: provider access to client staff statements
(DPA, zero retention, EU region — §8); over-retention through copies (`pipeline/retention.py`,
§6); real data landing in a tracked repository (data declaration, out-of-repository rule);
effort data misused for performance review (§9); incidental special-category data (§10).

## 5. Lawful basis and transparency (options, not conclusions)

Controller/processor roles: for client-supplied documents the agency may act as the client's
processor, or as a controller for its own account-management purposes; which applies, per
data category, is **OWNER/DPO TO CONFIRM** and decides whose lawful basis and notices apply.

| Processing | Options to evaluate | Status |
|---|---|---|
| Client staff and third-party data in briefing documents | Art. 6(1)(f) legitimate interest (preparing the commissioned work), with a balancing test; or processing on the client's documented instructions if the agency is processor | OWNER/DPO TO CONFIRM |
| Recorded kickoff meetings | Consent of participants (PRD §8 Plan B already requires it) or another basis the DPO names | OWNER/DPO TO CONFIRM |
| Agency staff actor names on approvals | Art. 6(1)(f) or (c) (accountability of approvals) | OWNER/DPO TO CONFIRM |
| Effort recording | Art. 6(1)(f) with an employee information step; national employment-data rules (GDPR Art. 88; Law 4624/2019 Art. 27, processing in the employment context) | OWNER/DPO TO CONFIRM |

Legitimate-interest balancing template (one per processing): purpose; why the processing is
necessary (could the brief be built without names? speaker attribution is what makes a
conflict checkable, `schema/extract_schema.json` `speaker_or_author`); reasonable expectations
of the people concerned; safeguards (§1, §6, §9); outcome and who signed it.

Transparency outline (Art. 13/14): who processes (agency; model provider as processor), what
(documents and meeting records for the brief), why, basis (above), retention (§6), rights and
contact (§7), transfers (§8). Delivery routes to decide: client-contact notice through the
client relationship; kickoff participants at the start of a recorded meeting; staff through
the employee privacy notice. Wording: **OWNER/DPO TO CONFIRM**.

## 6. Retention schedule per artifact

Periods are proposals for the owner; nothing is deleted automatically. Default proposal:
pilot inputs and outputs deleted 30 days after the pilot report is signed, except records the
agency must keep for accountability (**OWNER/DPO TO CONFIRM**, `GO_LIVE_DECISIONS.md` D-07).

| Artifact | Location | Contains | Proposed retention | How to delete |
|---|---|---|---|---|
| Project folder (sources, declaration, client config) | pilot location, outside the repository | originals | pilot end + 30 days | agency file deletion; `retention inventory` lists it as `originals_present` |
| Run directory: `inputs/` (staged read-only source copies), `evidence/`, `history/`, `extracts/`, `fidelity/`, `verification/`, `diagnostics/`, briefs, renders, review HTML | `<pilot runs>/<run-id>/` | copies and quotes of sources | pilot end + 30 days | `python3 -m pipeline.retention purge --run DIR --actor NAME --reason TEXT` |
| One source across runs (erasure request) | any run under the pilot runs folder | byte copies and per-source derivatives | on request | `purge --source-sha SHA --runs DIR ...`; run-level quotes remain until `--run` purge (listed as residual) |
| Governance records (approvals, withdrawals, amendments, releases, clarifications, audit log) | run directory | agency staff names, decisions | as long as the delivered work needs an accountability trail: OWNER/DPO TO CONFIRM | with the run; the purge record carries an `audit_log_deleted` tombstone (hash, entry count, chain head, events by type, whether it verified; no names) |
| Effort records | `effort.json` in the run; exported CSV | staff minutes | until the pilot report; CSV keeps only L1/L2 | with the run; CSV by file deletion |
| Release packages | wherever `delivery release --output` wrote them | approved creative, deliverable rows | the agency's delivery retention | not deleted by `purge --run` (listed in the tombstone) |
| Review shelf and share pages | `reviews/` (inside the repository, git-ignored) and wherever shared | brief views | never for pilot data: publish to the pilot location instead | file deletion |
| `claude -p` session transcripts | the operator's Claude Code profile (per-project session files) | everything the agents read and wrote | none kept: runtime agents run with `--no-session-persistence` (round 2, §1); legacy runs made before the flag: delete at run end (D-24) | legacy runs only: the CLI profile; `retention inventory` lists each run's session IDs |
| Provider-side data | model provider | prompts and outputs | per account terms (zero retention requested) | per DPA: OWNER/DPO TO CONFIRM |
| Tombstones | `retention_tombstones.jsonl` beside purged runs | what/when/who/why, hashes only | accountability period | file deletion by the DPO's decision |

## 7. Data-subject rights procedure

1. Log the request (date, requester, right: access, rectification, erasure, restriction,
   objection) in the agency's rights log, which the data-protection lead keeps; the one-month
   clock (Art. 12(3)) starts.
2. Locate: `python3 -m pipeline.retention inventory --runs <pilot runs>`; search run
   directories for the person's name (sources, extracts, briefs, governance records); list
   release packages and session IDs from the inventory.
3. Access: provide the relevant excerpts (sources as supplied, extracts and brief entries that
   quote the person), after the DPO's review of third-party data.
4. Rectification: sources are records of what was said; correct the brief through `agency
   apply` or a new run with a corrected source, with the reason recorded.
5. Erasure or objection upheld: `purge --source-sha` for the source, then `purge --run` for
   every run that still quotes it (the tombstone lists residuals); delete the original in the
   project folder, CLI session files and any copies outside the pilot location; ask the
   provider per the DPA.
6. Record the outcome and the tombstone path in the rights log. Whether any record may be kept
   despite an erasure request (for example an accountability trail): **OWNER/DPO TO CONFIRM**.

## 8. Processor checklist (Art. 28) and transfer questions for the model provider

- Is a DPA in place for the exact account type the pilot uses (subscription workspace vs API)?
  (`OPERATING_TERMS.md` §c; **OWNER TO CONFIRM** in writing.)
- Subject matter, duration, nature and purpose of processing as described in §3.
- Retention: is zero data retention available and applied to this account; how long are
  prompts, outputs and safety logs kept otherwise?
- Use of customer content for model training: what do the account's terms say?
- Processing region and international transfers: EU processing available? transfer mechanism
  (adequacy decision or standard contractual clauses)? sub-processor list and change notice?
- Security measures, breach notification timeline, assistance with rights requests and DPIAs,
  deletion or return at the end, audit rights.
- The Claude Code CLI itself: which telemetry or error reports leave the machine and whether
  they can be disabled (OPERATOR TO CONFIRM, D-24). Local session transcripts are switched off
  for runtime agents (`--no-session-persistence`, §1); interactive developer sessions are not
  runtime agents and never see pilot data.
- Any transcription (STT) vendor used before intake is a separate processor with its own
  checklist; the pipeline does not call one.

## 9. Purpose limitation for effort recording

Effort and handoff records (`pipeline/effort.py`, `EFFORT_RECORDING.md`) exist to measure
whether the brief workflow saves attention and reduces rework, per brief and per role. They are
not used for individual performance evaluation, discipline, pay or ranking of staff. Before the
first real record, staff receive the information in §5; records name roles and fictional or
pseudonymous actor IDs where possible; the scorecard carries L1/L2 only; access is limited to
the operator and the sponsor. Greek law adds employment-context rules for this processing (Law
4624/2019 Art. 27, implementing GDPR Art. 88), including when employee data may be processed
and the information owed to staff; whether and how they apply here, and whether any works-council
or staff-consultation step is needed, is **OWNER/DPO TO CONFIRM** (D-12). Any other use needs a new
decision: **OWNER/DPO TO CONFIRM**.

## 10. Special-category screening step (before `approved` is declared)

Before an account lead declares a project `approved` and runs it: open each source and check
for health, ethnic origin, political opinion, religious belief, trade-union membership, sexual
life, genetic or biometric data, criminal-offence data, and data about children. If present and
not needed for the brief, remove it from the source before intake (keep the original out of the
pilot location); if it cannot be removed, do not run the project. Start from the advisory
pre-screen (`python3 -m pipeline.prescreen RAW_FOLDER`): it lists the lines to look at, never the
values, and a clean result proves nothing. Record who screened and when in the approval record
that `approval_ref` points to and in the declaration itself (`screened_by`, `screened_on`), with
`processor_ref` and `dpia_ref`; a declaration without all four is refused (intake exit 2, runner
exit 6).

## 11. Committed-artifact minimisation and open items

- The repository holds synthetic fixtures only. The committed graded run (`runs/tier3`) records
  the case-study author's own name as signer and conflict resolver; it stays unchanged as
  historical evidence (read-only rule). New committed evidence uses fictional actors: the
  lifecycle rehearsal (`runs/rehearsal-lifecycle/`) replaces that name when it copies tier3.
  Tests use "Synthetic …" actors.
- Pilot data is never committed: approved projects are refused inside the repository.
- Open: speaker pseudonymisation before extraction (§13); making the declaration's
  precondition fields mandatory once intake can write them (§1); CLI telemetry settings (D-24).
  Closed in round 2: an advisory pre-screen exists (advisory by design, not a control); session
  persistence is off for runtime agents.

## 12. Record of processing activities (Art. 30) — entry template

One entry for the pilot, kept by the agency as controller (Art. 30(1)). If the DPO concludes that
the agency acts as the client's processor for client documents (§5), the processor record of Art.
30(2) applies to that part instead. Contents: **OWNER/DPO TO CONFIRM**.

| Art. 30(1) item | Entry for "AI-assisted brief preparation (pilot)" |
|---|---|
| (a) Controller, representative, DPO contact | The agency; the data-protection lead named at kickoff (D-01) |
| (b) Purposes | Preparing campaign briefs from client documents; recording review decisions for accountability; measuring the workflow (effort, §9) |
| (c) Categories of data subjects and personal data | §2: client staff and third parties named in documents (names, roles, statements); agency staff (names as actors, decisions, effort minutes); no special categories intended (§10) |
| (d) Recipients | The model provider as processor (§3, §8); nobody else: packages are released locally, nothing is sent automatically |
| (e) Transfers to third countries and safeguards | Per the account's terms: **OWNER/DPO TO CONFIRM** (§8) |
| (f) Erasure time limits | §6 retention schedule (D-07) |
| (g) Technical and organisational measures | §1 controls; run-directory access limited to the pilot location (D-04); hash-chained audit log; retention tool with tombstones |

## 13. Data minimisation of the model flow (options, not changes)

**Classify.** The classify stage decides one thing, the project type, and copies the tier from
the client config (`.claude/agents/classify.md` rules 1 and 4: "read enough to route"). Its work
order lists every source, so every source's full text reaches the provider at this stage (§3),
although every source reaches the provider again at extraction anyway. Options, none
implemented: (a) pass only the source headers (type, date, title) and the RFP; (b) pass the
first part of each source. Either reduces what one stage sends, not what the run sends. Both
could lower classification confidence and raise halts (`unclassified_ask_human`). Evaluation
before any change: the same graded fixtures classified both ways, compared on project type and
confidence. It is a prompt change under the routing and prompt-change rules, so it needs the
owner's decision. **OWNER/DPO TO CONFIRM** whether the reduction is worth that trade.

**Speaker pseudonymisation.** Replacing speaker names with role labels before extraction would
keep names away from the provider. It changes citations (`speaker_or_author`) and conflict
attribution, which is what makes a conflict checkable. Evaluation plan: pseudonymise one graded
fixture's sources, run it under the current routing, and compare harness recall, conflict
attribution and the lead's ability to act on the brief. Not started.
