# Current operating decisions

## 2026-09-20 — Creative can proceed to delivery

Owner instruction: “dont keep creative as shadow only from now on”. This supersedes
shadow-only statements in the frozen MVP PRD and historical reports. Those records remain
unchanged as historical specifications/evidence; current operating code follows this decision.

Generated creative starts as a draft. After the client brief is signed off and the exact
creative files have a named creative lead's approval, the delivery command can create an
approved local delivery package. This is real release capability, not a renamed shadow mode.
It does not automatically send files, post content, buy media or approve work on anyone's behalf.

Specifications selected for release must come from a non-stub catalog with attributable,
dated verification. The shipped synthetic stub remains valid for development, but cannot
support a production-specification claim or pass the release gate.

Fixtures-only data handling remains in force. This release can exercise delivery with
synthetic material; real client onboarding still requires a separate data-policy decision.
No UI/integration, model-routing or frozen-schema change was authorized by this decision.

The Tier-4 `creative-shadow` identifier and legacy checker remain for compatibility with
historical evidence. Newly generated output uses CREATIVE DRAFT; it can become APPROVED FOR
DELIVERY through the new human approval/release workflow.

## 2026-09-22 — Whole-project review loop and four owner decisions

Owner instruction: rate every aspect of the project with independent judge panels, create a
baseline, then work in rounds of the ten highest-leverage moves until every aspect is above
8/10. The frozen rubric, panels and baseline live in `tools/project_review/` (6 layers, 17
aspects, 3 independent specialist judges per layer; baseline round `r0`, every aspect 5.0–7.0).
Loop judges and editors run on Claude because Codex was at its usage limit (owner's choice).

The owner decided, in answer to explicit questions:

1. **Live re-baseline authorized.** After graded-fixture text is removed from the runtime
   prompts, run 3 graded rolls on each of `northlight_01` and `voreas_02` under the current
   routing, on the owner's Claude subscription. This produces per-check pass rates and usage
   in tokens by model for the routing actually in use.
2. **One canonical walkthrough.** Correct `WALKTHROUGH.html` (v1) to match the current system
   (creative delivery after human approval, Tier 5–7 operations) and make it the canonical
   page. The v2 redesign is retired and kept as a historical record.
3. **Creative delivery is in the pilot from week 1**, under enforced separation of duties
   (a creative approver distinct from the person who registered the draft and from the brief
   signer) and the existing release, verification and withdrawal controls.
4. **Explicit data declaration is part of the input contract.** A project without a data
   declaration is refused. Fixtures declare `synthetic`; any non-synthetic project must carry a
   recorded approval reference. Real client data still requires the agency's data-policy
   approval; this decision adds the control, it does not grant that approval.

## 2026-09-23 — Round-2 owner decisions

After the round-1 re-score (every aspect 5.3–7.3), the owner decided:

1. **Garble carry-through rule adopted.** `skills/SYNTHESIS.md` gains the rule queued since the July
   voreas rehearsal: a garbled (rule-G) token stays visible in reader-facing content next to its proposed
   match, never silently normalised, with a deterministic synthesis check. Applied before the live
   re-baseline.
2. **Blind third keyed fixture.** A fresh author that has never seen the runtime prompts or gates writes
   a new synthetic keyed fixture with new trap classes. Its answer-key hash is committed before any run,
   and it gets one graded live run under the current routing. Pipeline developers do not open it before
   that run.
3. **Injection canary.** One live run on `tests/injection_project` under the current agent flags, to
   show that the CLI enforces the permission rules and that agents do not follow planted instructions.
4. **Coding agents are blocked from human-decision commands.** A tracked `.claude/settings.json` deny
   rule plus a hook prevent AI coding agents from running `agency approve|attest|resolve|apply` and
   `delivery approve|release`.
5. **Verifier routing is declared sonnet-only.** The risk classes route every stored extract to sonnet
   (0 of 66 take the haiku branch). Config, CLAUDE.md and cost documents are corrected to match what
   runs. No behaviour change; the re-baseline measures the true cost.
6. **The owner records the human decisions on the regenerated graded brief.** After the re-baseline,
   the owner runs the resolve/attest/approve commands prepared for them. Only then is the creative A/B
   regenerated. The system still never signs off on its own.
