#!/usr/bin/env bash
# Owner decisions for runs/r2-live/nl-r1, part 1 (prepared for Christos Maragkoudakis).
#
# Prepared by an AI coding agent as SUGGESTIONS. Nothing here has been run against the real run.
# Read OWNER_DECISIONS.md beside this file first, edit any line you disagree with, then run it
# yourself from any directory:
#
#     bash runs/r2-live/nl-r1/owner_decisions_part1.sh            # the real run
#     bash runs/r2-live/nl-r1/owner_decisions_part1.sh /tmp/copy  # a copy, to rehearse
#
# Part 1 does NOT resolve the three conflicts: you do that yourself first (`agency resolve`,
# indexes 0, 1, 2). The guard below stops if any of them is still open, because the coverage
# exclusions bind to the brief content as it stands after your resolutions.
#
# Part 1 records: 17 question triages, 2 coverage exclusions, 7 campaign-checklist answers
# (profile paid_campaign) and 1 deliverables-matrix row. It clears every audit blocker except
# the bilingual attestation and the render-citation blockers (the re-render fixes those; then
# part 2 = attest + approve, see OWNER_DECISIONS.md).
#
# Source line numbers cite fixtures/northlight_01/*.md; FIELD:INDEX refs cite brief.json entries.

set -e

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
RUN="${1:-$REPO/runs/r2-live/nl-r1}"
RUN="$(cd "$RUN" && pwd)"
ACTOR="Christos Maragkoudakis"
OWNER="Christos Maragkoudakis"
cd "$REPO"

# Guard: the three conflicts must already carry your resolution (resolved_by_human, with text and name).
python3 - "$RUN" <<'PY'
import json, sys
from pathlib import Path
brief = json.loads((Path(sys.argv[1]) / "brief.json").read_text(encoding="utf-8"))
conflicts = brief.get("conflicts") or []
open_ = [i for i, c in enumerate(conflicts)
         if c.get("status") != "resolved_by_human"
         or not str(c.get("resolution") or "").strip() or not str(c.get("resolved_by") or "").strip()]
if len(conflicts) != 3 or open_:
    sys.exit(f"STOP: part 1 needs all three conflicts resolved by you first; still open: {open_ or 'expected 3 conflicts'}.\n"
             f"Run `python3 -m pipeline.agency resolve {sys.argv[1]} --index N --actor ... --text ...` for each, "
             f"then run this script again. Nothing was recorded.")
print("guard: conflicts 0, 1, 2 are resolved_by_human — recording part 1")
PY

# ---------------------------------------------------------------------------------------------
# A. Question triage (17) — `agency answer`. Open questions stay in the brief and go to the client;
#    "nonblocking" means they do not block the agency's approval of this brief. Flip any to
#    `--priority blocking` if you want it answered before you approve (that blocker then stays).
# ---------------------------------------------------------------------------------------------

# Q1 objectives/KPI — open, nonblocking: no measurable goal exists; RFP §2 (rfp_meltemi.md:9) says only "successful launch", CMO at [00:18:52] (transcript_kickoff.md:37) "Όχι ακόμα κάτι γραμμένο. Ας το δούμε μαζί."
python3 -m pipeline.agency answer "$RUN" --id 381eba97c569d0cb544c --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "rfp_meltemi ## 2. Στόχος (line 9); transcript_kickoff [00:18:52] (line 37); brief objectives[0]" \
  --text "Real question for the client. No KPI or success metric exists in any source: the RFP says only 'successful launch' and the CMO said nothing is written yet and proposed defining it together. Does not block the brief; to agree with the client before strategy sign-off."

# Q2 objectives/brand awareness — open, nonblocking: the objective was heard as the garbled «μπραντ αγουέρνες» [00:02:05] (transcript_kickoff.md:7); proposed match unconfirmed.
python3 -m pipeline.agency answer "$RUN" --id 5cd5f6de3c8403eddfa6 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:02:05] (line 7); brief objectives[1]" \
  --text "Real question. The primary objective rests on the garbled token «μπραντ αγουέρνες»; 'brand awareness' is a proposed match, not confirmed. Ask the client to confirm; the brief keeps the token visible meanwhile."

# Q3 audiences — duplicate of conflict 0: your resolution of conflict 0 settles the audience (25-40 urban professionals, [00:03:41], transcript_kickoff.md:9, over RFP §3, rfp_meltemi.md:12).
python3 -m pipeline.agency answer "$RUN" --id 32426f78fbf9e1b77ee2 --status duplicate --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "conflicts[0] resolution; transcript_kickoff [00:03:41] (line 9); rfp_meltemi ## 3. Κοινό-στόχος (line 12)" \
  --text "Duplicate of conflict 0, which the owner resolved: primary audience 25-40 urban professionals per the CMO at kickoff; the RFP's Gen Z 18-24 is superseded. The TikTok-first follow-up from that resolution is carried by question 15 (open_questions[14])."

# Q4 key_messages claim wording — open, nonblocking: kickoff says «φυσικά υλικά» [00:06:02] (transcript_kickoff.md:13); guidelines permit only «φυσικά συστατικά» per approved ingredient list (background_brand_guidelines.md:12).
python3 -m pipeline.agency answer "$RUN" --id 51395488a09dab1368e4 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:06:02] (line 13); background_brand_guidelines ## Claims — hard rules (line 12); brief key_messages[0], mandatories[6]" \
  --text "Real question. The spoken wording «φυσικά υλικά» differs from the only permitted claim «φυσικά συστατικά». Does not block the brief; must be settled before any copy uses the claim (hard brand rule)."

# Q5 deliverables quantities/formats — open, nonblocking: RFP §4 lists "βίντεο, key visuals" with no quantities (rfp_meltemi.md:17); CMO [00:10:22] "θα μας πείτε κι εσείς" (transcript_kickoff.md:19).
python3 -m pipeline.agency answer "$RUN" --id 0144b3fccc1c0a0e83c1 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "rfp_meltemi ## 4. Απαιτήσεις καμπάνιας (lines 16-17); transcript_kickoff [00:10:22] (line 19); brief deliverables[0], deliverables[1], deliverables[2]" \
  --text "Real question. No source gives quantities, formats, lengths or channels beyond TikTok; the CMO expects the agency to propose formats. The deliverables matrix holds only a sourced minimum (one key visual master) until the client answers."

# Q6 deliverables TikTok dance — not worth asking: the CMO said "Don't hold me to it" [00:11:47] (transcript_kickoff.md:21) and Eleni recorded it "ως ιδέα, όχι ως απόφαση" [00:13:05] (line 23).
python3 -m pipeline.agency answer "$RUN" --id 026f60acff6388c032dc --status not_worth_asking --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:11:47] (line 21), [00:13:05] (line 23); brief deliverables[3]" \
  --text "Not worth asking: the sources already answer it. The CMO floated the idea as thinking out loud ('Don't hold me to it') and the account lead recorded it at the call as an idea, not a decision. The brief keeps it as a non-commitment (deliverables[3]); creative may propose it, nobody should ask the client to re-confirm a passing thought."

# Q7 timeline launch date — duplicate of conflict 1: your resolution sets 15 September per the board decision in the 14 July email (emails_thread.md:11) over RFP §5 (rfp_meltemi.md:20).
python3 -m pipeline.agency answer "$RUN" --id aa881057535d4c51c533 --status duplicate --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "conflicts[1] resolution; emails_thread Message 2 (line 11); rfp_meltemi ## 5. Χρονοδιάγραμμα (line 20)" \
  --text "Duplicate of conflict 1, which the owner resolved: launch 15 September 2026 per the board decision in Dimitris's email of 14 July, superseding the RFP's first week of October. The point-of-sale placement deadline this question also asked about is carried by question 8 (open_questions[7])."

# Q8 timeline milestones — open, nonblocking: no milestones in any source; Eleni promised a revised plan (emails_thread.md:16, Message 3).
python3 -m pipeline.agency answer "$RUN" --id 63b9958b2969e37cb175 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "emails_thread Message 2 (line 11), Message 3 (line 16); brief timeline[0]" \
  --text "Real question, and it now also carries the point-of-sale placement deadline (from question 7). No source states concept, production, approval or delivery dates; the agency owes the client a revised plan (Message 3). Does not block the brief."

# Q9 timeline board meeting — open, nonblocking: kickoff [00:17:03] says the board finalises timing at "τέλη του μήνα" (transcript_kickoff.md:33); the 14 July email reports a board decision (emails_thread.md:11); no source says that decision is final.
python3 -m pipeline.agency answer "$RUN" --id e9d752ec25a822512831 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:17:03] (line 33); emails_thread Message 2 (line 11); brief timeline[3]" \
  --text "To confirm with client: whether the board decision reported on 14 July (launch 15 September) is final, or whether the end-of-month board meeting mentioned at kickoff can still change it. The working date is the owner's resolution of conflict 1."

# Q10 budget amount/currency/scope — duplicate of conflict 2: your resolution records "around eighty ... excluding media" (transcript_kickoff.md:25) and sends units, currency and the RFP's €90.000 (rfp_meltemi.md:23) back to the client.
python3 -m pipeline.agency answer "$RUN" --id 8dab14300ab46d28c7f5 --status duplicate --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "conflicts[2] resolution; transcript_kickoff [00:14:32] (line 25); rfp_meltemi ## 6. Προϋπολογισμός (line 23)" \
  --text "Duplicate of conflict 2, which the owner resolved: production budget around eighty, units and currency to be confirmed with the CFO, excluding media; the RFP's 90.000 including media is not reconciled and goes back to the client. The resolution itself carries the follow-up to the client."

# Q11 budget media spend — open, nonblocking: CFO [00:14:32] "Το media το βλέπουμε ξεχωριστά με τον media shop μας" (transcript_kickoff.md:25) and [00:15:26] "δεν είναι δικό μου κομμάτι το νούμερο αυτό ακόμα" (line 29).
python3 -m pipeline.agency answer "$RUN" --id 45806f7baae55ab876e0 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:14:32] (line 25), [00:15:26] (line 29); brief budget[2]" \
  --text "Real question. Media spend is handled by the client's media shop and the figure is not known yet (CFO). It stays separate from the production budget (glossary: never merge media spend and production). Does not block the production brief."

# Q12 mandatories which brand rules bind — open, nonblocking: RFP §7 "Ισχύουν οι οδηγίες brand" (rfp_meltemi.md:26); email "ισχύει η έκδοση 3.1" (emails_thread.md:10); we hold only an excerpt (background_brand_guidelines.md:1).
python3 -m pipeline.agency answer "$RUN" --id 5aeaa1133230a7a55613 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "rfp_meltemi ## 7. Λοιπά (line 26); emails_thread Message 2 (line 10); brief mandatories[1]" \
  --text "Real question. Sources say guidelines v3.1 apply but not whether every rule binds or whether there are exceptions; the agency holds only an excerpt. Until answered, every rule in the excerpt is treated as applying (RFP §7). Does not block the brief."

# Q13 mandatories approved ingredient list — open, nonblocking: «φυσικά συστατικά» is permitted only "per approved ingredient list", which is not in the excerpt (background_brand_guidelines.md:12).
python3 -m pipeline.agency answer "$RUN" --id c44f154ec6818040a1b1 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "background_brand_guidelines ## Claims — hard rules (line 12); brief mandatories[6]" \
  --text "Real request to the client: send the approved ingredient list. Needed before any copy uses «φυσικά συστατικά»; does not block the brief."

# Q14 mandatories beach-party/tone firmness — open, nonblocking: guidelines say "Avoid generic 'beach party' clichés" under Category no-gos (background_brand_guidelines.md:17) and label tone "(guidance)" (line 19-20).
python3 -m pipeline.agency answer "$RUN" --id 6ca02bbb57bed1d71924 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "background_brand_guidelines ## Category no-gos (line 17), ## Tone (guidance) (lines 19-20); brief mandatories[10], mandatories[11]" \
  --text "Real question. The guidelines' own wording is mixed ('avoid' under a no-gos heading; tone marked 'guidance'). Until answered, creative treats both as written in the guidelines. Does not block the brief."

# Q15 mandatories TikTok-first — open, nonblocking: RFP §4 mandates TikTok-first (rfp_meltemi.md:15) for the Gen Z audience your conflict-0 resolution supersedes; that resolution asks to raise it with the client.
python3 -m pipeline.agency answer "$RUN" --id 2a0ad152dd2a3c60e3cd --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "rfp_meltemi ## 4. Απαιτήσεις καμπάνιας (line 15); conflicts[0] resolution; brief mandatories[0]" \
  --text "Real question, now sharpened by the owner's resolution of conflict 0: ask the client whether TikTok-first still fits the 25-40 urban-professional audience, and whether it is a hard constraint or a preference. The RFP mandate stands until the client answers."

# Q16 mandatories key visual/premium summer — open, nonblocking: heard as the garbled «κι βίζουαλ» [00:06:02] (transcript_kickoff.md:13); "premium καλοκαίρι" undefined.
python3 -m pipeline.agency answer "$RUN" --id 6a269c4f132101c09cfa --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "transcript_kickoff [00:06:02] (line 13); brief mandatories[12]" \
  --text "Real question. The only creative constraint from kickoff rests on the garbled token «κι βίζουαλ» (proposed match 'key visual', unconfirmed) and an undefined 'premium summer'. Ask the client to confirm and give examples. Does not block the brief."

# Q17 mandatories client approver — open, nonblocking: asked in Message 1 (emails_thread.md:6), "Για το approval θα επανέλθω" in Message 2 (line 12), still awaited in Message 3 (line 16).
python3 -m pipeline.agency answer "$RUN" --id 0b1d3d0223d700fa1130 --status open --priority nonblocking --owner "$OWNER" --actor "$ACTOR" \
  --evidence "emails_thread Message 1 (line 6), Message 2 (line 12), Message 3 (line 16)" \
  --text "Real question, already asked twice by email and still unanswered: who approves the brief on the client side. Needed for the client's sign-off, not for the agency's internal approval of this draft; chase it when the brief goes out."

# ---------------------------------------------------------------------------------------------
# B. Coverage exclusions (2) — `agency exclude`. Both facts are the metro OOH idea and its retraction
#    in the same turn at [00:08:15]/[00:08:34] (transcript_kickoff.md:15). Must run AFTER your
#    resolutions: an exclusion binds to the brief content it was decided against.
# ---------------------------------------------------------------------------------------------

# Exclude fact 5767ac568d35a72da201 (metro OOH idea, [00:08:15]): the CMO withdrew it seconds later — "actually scratch that ... Ξεχάστε το" [00:08:34] (transcript_kickoff.md:15).
python3 -m pipeline.agency exclude "$RUN" --fact 5767ac568d35a72da201 --actor "$ACTOR" \
  --reason "Retracted by the client in the same turn: at [00:08:34] the CMO says 'actually scratch that, το μετρό είναι πανάκριβο φέτος ... Ξεχάστε το' (transcript_kickoff.md line 15). Not a deliverable; excluded so the metro OOH idea cannot reach creative as a request."

# Exclude fact 2c0483441abf06863030 (the retraction itself, [00:08:34]): it only withdraws the idea excluded above; nothing remains to carry.
python3 -m pipeline.agency exclude "$RUN" --fact 2c0483441abf06863030 --actor "$ACTOR" \
  --reason "The retraction of the metro OOH idea (transcript_kickoff [00:08:34], line 15). It withdraws the idea excluded under fact 5767ac568d35a72da201 and adds no deliverable. Account team note: if creative proposes OOH, remember the client ruled out metro OOH on cost."

# ---------------------------------------------------------------------------------------------
# C. Campaign checklist, profile paid_campaign (7) — `agency_edit checklist`. --ref FIELD:INDEX
#    copies that brief entry's evidence. Where no source answers, the value says "To confirm with client".
# ---------------------------------------------------------------------------------------------

# business_objective: launch in the Greek market (RFP §2, rfp_meltemi.md:9; objectives[0]); stated main aim brand awareness, heard garbled at [00:02:05] (transcript_kickoff.md:7; objectives[1]).
python3 -m pipeline.agency_edit checklist "$RUN" --key business_objective --owner "$OWNER" --actor "$ACTOR" \
  --ref objectives:0 --ref objectives:1 \
  --value "Launch of Meltemi Fizz, a zero-sugar sparkling tea and a new category for the client, in the Greek market (RFP §2). The client's stated main aim is brand awareness — heard as «μπραντ αγουέρνες», proposed match unconfirmed (question 2). No measurable business outcome is stated in any source."

# conversion_and_kpi: none exists — RFP says only "successful launch" (rfp_meltemi.md:9; objectives[0]); CMO [00:18:52] "Όχι ακόμα κάτι γραμμένο" (transcript_kickoff.md:37).
python3 -m pipeline.agency_edit checklist "$RUN" --key conversion_and_kpi --owner "$OWNER" --actor "$ACTOR" \
  --ref objectives:0 \
  --value "To confirm with client: no conversion, KPI or measurement period exists yet. The RFP states only a 'successful launch'; at kickoff the CMO said nothing is written yet and proposed defining it together (transcript [00:18:52]). Open question 1."

# audience_and_offer: audience per your conflict-0 resolution (audiences[1], transcript_kickoff.md:9, over audiences[0]); messages from [00:06:02] (key_messages[0], [1]); claim wording per mandatories[6]; no offer in any source.
python3 -m pipeline.agency_edit checklist "$RUN" --key audience_and_offer --owner "$OWNER" --actor "$ACTOR" \
  --ref audiences:1 --ref audiences:0 --ref key_messages:0 --ref key_messages:1 --ref mandatories:6 \
  --value "Audience: 25-40 urban professionals, per the CMO at kickoff and the owner's resolution of conflict 0; the RFP's Gen Z 18-24 is superseded. Messages stated by the CMO at kickoff (not yet approved in writing): 'refreshment without the sugar guilt — zero sugar, natural ingredients' and 'a Greek brand that makes the modern category its own'. Claim wording «φυσικά υλικά» vs the permitted «φυσικά συστατικά» to confirm with client (question 4). Offer: to confirm with client — no source states an offer or promotion."

# landing_page: no source mentions one; the RFP asks only for social/digital presence, channels unspecified (rfp_meltemi.md:16; deliverables[1]).
python3 -m pipeline.agency_edit checklist "$RUN" --key landing_page --owner "$OWNER" --actor "$ACTOR" \
  --ref deliverables:1 \
  --value "To confirm with client: no source names a landing page or who owns its readiness. The RFP asks only for presence on social media and digital channels, without specifying them."

# tracking_owner: no source names one; no KPI exists (objectives[0]); media is run by the client's media shop (budget[2], transcript_kickoff.md:25).
python3 -m pipeline.agency_edit checklist "$RUN" --key tracking_owner --owner "$OWNER" --actor "$ACTOR" \
  --ref objectives:0 --ref budget:2 \
  --value "To confirm with client: no source names who owns measurement or verifies tracking before launch, and no KPI exists yet. Media is handled separately by the client's media shop (CFO at kickoff); whether they own tracking is not stated."

# budget_and_dates: your conflict-2 and conflict-1 resolutions; budget[0] rfp_meltemi.md:23, budget[1]/[2] transcript_kickoff.md:25, timeline[0] emails_thread.md:11, timeline[1] rfp_meltemi.md:20.
python3 -m pipeline.agency_edit checklist "$RUN" --key budget_and_dates --owner "$OWNER" --actor "$ACTOR" \
  --ref budget:1 --ref budget:0 --ref budget:2 --ref timeline:0 --ref timeline:1 \
  --value "Budget (owner's resolution of conflict 2): production around eighty, units and currency to be confirmed with the CFO, excluding media; the RFP's €90.000 including media is not reconciled and goes back to the client. Media spend: separate, via the client's media shop, figure not yet known. Dates (owner's resolution of conflict 1): launch 15 September 2026 per the board decision in the 14 July email (the email itself states no year), superseding the RFP's first week of October. Intermediate milestones and the point-of-sale placement deadline: to confirm with client (question 8)."

# assets_and_approvals: assets from RFP §4 (rfp_meltemi.md:16-17; deliverables[0],[1]) and [00:10:22]/[00:11:47] (deliverables[2],[3]); guidelines v3.1 (mandatories[1]); approver pending (emails_thread.md:12,16).
python3 -m pipeline.agency_edit checklist "$RUN" --key assets_and_approvals --owner "$OWNER" --actor "$ACTOR" \
  --ref deliverables:0 --ref deliverables:1 --ref deliverables:2 --ref deliverables:3 --ref mandatories:1 \
  --value "Assets: creative material for the launch — video and key visuals — plus social and digital presence (RFP §4); quantities, formats and lengths not set, and the CMO expects the agency to propose them (question 5). The TikTok dance idea is not a commitment. Rights: to confirm with client — no source mentions usage rights. Approvals: brand guidelines v3.1 apply; the client-side approver of the brief is not yet named (emails of 14 and 15 July; question 17)."

# ---------------------------------------------------------------------------------------------
# D. Deliverables matrix (1 row) — `agency_edit deliverable`. Only what the sources support:
#    "key visuals" (RFP §4, rfp_meltemi.md:17) → at least one key visual master, Greek market
#    (RFP §2), due no later than the launch date of your conflict-1 resolution. Owners are you:
#    no source names a production owner or a client approver.
# ---------------------------------------------------------------------------------------------

# Key visual digital master ×1 (a floor, not a quantity from the client), el, due 2026-09-15 (launch per your conflict-1 resolution); evidence deliverables[0] (rfp_meltemi.md:17), mandatories[12] ([00:06:02]), timeline[0] (emails_thread.md:11).
python3 -m pipeline.agency_edit deliverable "$RUN" --id kv-master-01 --spec-id key_visual_digital_master --quantity 1 \
  --language el --deadline 2026-09-15 --owner "$OWNER" --approval-owner "$OWNER" --actor "$ACTOR" \
  --ref deliverables:0 --ref mandatories:12 --ref timeline:0

# NOT recorded — a TikTok in-feed video row. TikTok-first (RFP §4, mandatories[0]) and "βίντεο" (deliverables[0]) support one,
# but the spec row needs a duration (9-60s) and a quantity that no source gives. After the client answers question 5, add e.g.:
#   python3 -m pipeline.agency_edit deliverable "$RUN" --id tiktok-video-01 --spec-id tiktok_infeed_video --quantity N \
#     --language el --deadline 2026-09-15 --owner "$OWNER" --approval-owner "$OWNER" --actor "$ACTOR" \
#     --ref deliverables:0 --ref mandatories:0 --ref timeline:0 --dependency kv-master-01 --duration-seconds SECONDS

echo "part 1 recorded. Next: python3 -m pipeline.agency audit \"$RUN\" — expect only the render-citation and language-review blockers."
