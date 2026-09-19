# Agency benchmark protocol

The corpus adds three synthetic campaign types, each with an RFP, follow-up email and
explicit client glossary. They are not answer keys for the frozen harness and do not change it.

| Fixture | Campaign profile | Quality challenge |
|---|---|---|
| `fixtures/agency_paid_01` | paid_campaign | Conversion versus clicks; landing-page deadline conflict; unresolved production budget |
| `fixtures/agency_organic_01` | organic_social | Additional language scope; already-supplied approval owner; distinguish organic goals from paid metrics |
| `fixtures/agency_production_01` | creative_production | Concepts versus variants; missing approved logo; speculative packaging and requested date changes |

`python3 eval/agency_benchmark.py` runs 12 deterministic fault injections, with explicit
positive controls, and checks the three corpus input folders. No models are called.
A green result proves the tested safeguards and input contracts, not output fidelity.

For a separately authorized model evaluation, run each fixture under the unchanged current
routing with its own glossary and a unique run ID. Do not use the frozen harness on these
fixtures. It depends on its own exam contract. Use `pipeline.agency init` with the matching
profile, then audit and have an account lead/bilingual reviewer assess raw-source completeness,
question usefulness, qualifiers, EL/EN meaning and tone. Include at least two runs per fixture;
retain both successful and refused runs. Report outcome variability, repairs, elapsed time,
tokens, operator attention and critical errors, not just the best run.

This release does not execute those model runs: the current session requested Astra-only work
while the existing pipeline deliberately retains its human-chosen Claude routing. No routing
change or model-quality result is implied. Human ratings and actual agency time are unmeasured.

For historical Voreas, replay the existing regression suite and retain its strict expected
failures until fresh outputs genuinely resolve them. Never remove an xfail merely because a
new gate now catches one historical symptom.
