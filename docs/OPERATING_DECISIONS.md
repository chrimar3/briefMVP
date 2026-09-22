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
