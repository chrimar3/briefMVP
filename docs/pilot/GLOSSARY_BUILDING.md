# Building a client glossary with the account leads (week 1)

PRD §8 names co-building the per-client glossary with the leads as adoption lever #1: the leads
see their own vocabulary protected in both languages from the first draft. This is the week-1
procedure. Examples are synthetic; a real glossary lives in the pilot location, outside this
repository (`OPERATING_TERMS.md` §e).

## What the glossary is and what it controls

`pipeline/intake.py --client ID --tier S0|S1 --glossary-dir $PILOT/clients` scaffolds
`client_<id>.json` with `client_id`, `sensitivity_tier` and five generic starter `terms`. Each
term is `{"term": "...", "rule": "keep_latin", "note": "..."}`. The pipeline uses it in three
places, so each entry has consequences:

| Where | What the term does |
|---|---|
| Render (`skills/TRANSLATION.md` rule 3; `pipeline/stages.py` render check) | Must appear character-exact in both the Greek and the English brief; Latin-script terms stay Latin inside Greek text. |
| Extraction (`pipeline/gates.py` `find_unsourced_glossary_terms`) | If a term appears in an extracted value but the source never writes it in Latin script, the extract is refused as a silent repair or translation, and repaired. |
| Greek lint (`pipeline/stages.py` language warnings) | A term whose `note` says "company" is treated as an organisation name for Greek article checks. |

The `sensitivity_tier` is set at onboarding and never inferred (DR-11; D-08). The optional
`brief_template` key picks a per-client template set in `templates/`.

## The session (about one hour per lead, week 1)

1. **Before:** the operator runs intake once per client and prints the scaffold; each lead brings
   two or three recent briefs and one client e-mail thread for that client.
2. **Collect** (lead speaks, operator types), in this order:
   - product and brand names exactly as the client writes them (`Aurora Bloom`, not «Αουρόρα
     Μπλουμ»), and the company name with a note containing "company";
   - campaign taglines and mandatory lines, character-exact;
   - English marketing terms this agency writes in Latin script inside Greek text
     (`key visual`, `KPI`, `launch`), only if the leads actually write them that way;
   - pairs that must never be merged (for example `media spend` versus production budget), with
     the distinction in the `note`.
3. **Leave out** anything the client never writes in Latin script. A term added "to be safe"
   makes extraction refuse a source that writes the Greek word, and causes needless repairs.
   Leave out people's names: the glossary is not a contact list.
4. **Check** each entry against one real source line: would the brief reader expect exactly this
   spelling in both languages? If the leads disagree, the account lead who owns the client decides.

## Approval and versions

- The owning account lead approves the glossary (A in `ROLES.md`); the bilingual reviewer is
  consulted on Latin-versus-Greek choices; the operator saves it and records version, approver
  and date in the pilot's glossary log, not in the file: runtime agents read the whole file, so
  it carries terms and no names.
- A change after a run is an input change: the runner refuses to resume a run whose glossary
  changed (`input_snapshot.json`), so a new glossary version means a new `--run-id`.
- Keep old versions beside the current one (`client_<id>.v1.json`, …) so a past run can be
  explained. A glossary is client reference data and follows the pilot retention rule (D-07).

## Synthetic example

```json
{
  "client_id": "synthetic_helios",
  "sensitivity_tier": "S1",
  "terms": [
    {"term": "Helios Spark", "rule": "keep_latin", "note": "Product name — never transliterate, never translate."},
    {"term": "Helios Foods", "rule": "keep_latin", "note": "Company name."},
    {"term": "key visual", "rule": "keep_latin", "note": "Standard EN creative term."},
    {"term": "media spend", "rule": "keep_latin", "note": "Budget term; distinct from production budget — never merge the two."}
  ]
}
```
