# Cost-audit tier C3 — render model A/B (sonnet vs haiku) · **EVIDENCE PACK — DECISION OPEN**

**Date:** 2026-07-25 · **Arms:** `runs/cost-c2` (sonnet @ `effort: low`, the adopted C2 config) vs `runs/cost-c3` (haiku, same brief) · **Preceding:** C2 (`6b0bed9`)

This tier produces the evidence for a routing decision and deliberately does not make it —
model routing is a human decision (CLAUDE.md). Nothing in the shipped configuration changed:
the render agent's frontmatter still says `sonnet`; the haiku arm ran through the same
`model_override` seam the Tier-4 creative A/B used (now threaded through `stages.render`,
`test_render_threads_the_model_override_to_the_invocation_seam`).

---

## 1. The A/B — identical brief, template, glossary and gates; only the model moves

| | sonnet @ low (`cost-c2`) | haiku (`cost-c3`) |
|---|---|---|
| Cost | $0.676 | **$0.322 (−52%)** |
| Output tokens | 19,560 | 35,852 (more tokens, one-fifth the rate) |
| Attempts | 1, clean | 1, clean |
| Harness | 17/17 | **17/17** |
| EL / EN size | 14,169 / 12,867 chars | 13,087 / 12,238 chars |

Every deterministic gate holds on both arms: citation tags, glossary character-exactness,
⚠ coverage counts, conflict-position sources, all three traps. Cost saving if adopted:
a further **~$0.35/brief** on top of C2.

## 2. What the gates cannot see — the same passage, both arms

The render gates verify mechanics, not register. Same open question, both Greek renders:

> **sonnet @ low:** «**Κενό:** Η αρμοδιότητα έγκρισης του brief παραμένει ανοιχτή — ο
> Δημήτρης δήλωσε ότι ο εγκρίνων «μπορεί να είμαι εγώ ή η διοίκηση» και δεσμεύτηκε να
> επανέλθει…»
>
> **haiku:** «**Η αρχή approval του brief παραμένει άλυτη.** Ο Dimitris δήλωσε ότι ο
> approver "μπορεί να είμαι εγώ ή management" και δεσμεύθηκε να επανέλθει…»

The haiku arm injects English where the glossary does **not** require Latin («approval»,
«management», «approver» are not protected terms), renders a Greek name in Latin script
inside Greek prose («Ο Dimitris»), and picks off-register vocabulary («αρχή approval» for
"approval authority"; «άλυτη» for "unresolved"). This is precisely TRANSLATION.md rule 7's
register requirement («professional agency Greek — όχι μηχανική μετάφραση») degrading — the
one dimension no deterministic gate checks. Full documents for side-by-side reading:
`runs/cost-c2/brief_el.md` vs `runs/cost-c3/brief_el.md` (gitignored run artifacts; regenerate
per §4).

## 3. Recommendation (mine, clearly labeled — the decision is the account lead's)

**Keep render on sonnet.** The C2 result (sonnet @ low: −49% with byte-identical output)
already banked most of the render saving at zero quality risk; the further −$0.35 from haiku
buys visible register degradation in the client-facing Greek document — the artifact the
agency's name goes on. If per-brief cost pressure ever justifies revisiting, the revisit
should include a Greek-speaking reviewer scoring blind samples, not gates alone.

## 4. Reproduction

```
# A-arm is the shipped config:      python pipeline/runner.py --stage render --run-id <run>
# B-arm (haiku), same brief:        stages.render(run_dir, brief, glossary, dirs, model_override="haiku")
python eval/harness.py runs/cost-c2   → 17/17
python eval/harness.py runs/cost-c3   → 17/17
python -m pytest                      → 270 passed, 6 skipped
```

Tier spend: $0.32 (one haiku render). Observed models: `claude-sonnet-5` (A),
`claude-haiku-4-5-20251001` (B); orchestrator `claude-fable-5`.

---

**C3 DoD: both arms graded 17/17, cost and register evidence assembled, shipped routing
untouched. The sonnet-vs-haiku render decision awaits the account lead. Proceeding to C4 per
the approved sequence.**
