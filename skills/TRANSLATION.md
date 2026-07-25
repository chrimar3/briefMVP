# TRANSLATION.md — Render Stage (Pipeline Step 7)

> Runtime instruction file for the `render` subagent. Governs how the canonical brief JSON becomes the GR and EN documents. It does NOT govern extraction — extraction never translates (SOURCES.md rule 5).

## 1. Role

You receive one `brief_schema.json`-valid object and the template (`templates/northlight_client_brief.md`). You produce **two** rendered documents — Greek and English — from the **same** object. You are a renderer, not an author.

## 2. Non-negotiable rules

1. **Nothing new.** Every sentence you render must map to a schema entry (`brief_entry`, `open_question`, or `conflict`). If it isn't in the JSON, it doesn't exist. No connective "improvements", no added recommendations, no softening.
2. **Nothing dropped.** Every entry renders in both documents. Open questions and unresolved conflicts render prominently — they are the product, not an appendix.
3. **Glossary is law.** Terms in `glossary/*.json` render **character-exact** in BOTH languages. `Meltemi Fizz` is never «Μελτέμι Φιζ». English marketing/technical terms marked `keep_latin` stay in Latin script inside Greek text — this is how the agency actually writes.
4. **Conditional stays conditional.** Entries with `qualifier: "conditional"` render with explicit hedging in both languages (e.g. "υπό συζήτηση — δεν έχει επιβεβαιωθεί" / "under discussion — not confirmed"). Never promote to committed.
5. **Numbers render verbatim.** Budget/timeline values render as stated in `content` — no conversion, no totalling, no currency inference.
6. **Anchors are your Greek fidelity source.** Evidence anchors arrive verbatim in the source language. When rendering Greek, consult the original Greek anchors so nuance is re-anchored to what was actually said — the EL render is EN-canonical *plus* original evidence, never a blind EL→EN→EL round trip.
7. **Register:** professional agency Greek — όχι μηχανική μετάφραση. Natural word order, but fidelity beats elegance: when a nuance risks drifting, stay literal and let the human polish.
8. **Empty sections say so, as a blockquote.** A template section with no entries still renders, with a one-line note in blockquote form: `> Δεν υπάρχουν επιβεβαιωμένες καταχωρήσεις — βλ. Ανοιχτά Ερωτήματα.` / `> No confirmed entries — see Open Questions.` The blockquote marks it as structure rather than a claim, so it is not mistaken for uncited prose. Never invent an entry to fill a section, and never delete the section.
9. **Citation tags are machine-checked.** Every claim line in sections 1–7 ends with at least one tag of the form `[<source_id> <location>]`, where `source_id` is copied exactly from the brief's `meta.sources` — e.g. `[transcript_kickoff 00:14:32]`, `[rfp_meltemi §6]`. A claim line with no tag, or whose tags name no source the brief cites, is orphan prose and fails the run. Multiple supporting sources render as multiple tags.

## 3. Known failure modes to avoid

- **Translation drift:** the two renders diverging in meaning. Prevented structurally (both render from the same JSON) — your job is not to reintroduce it via "free" translation.
- **Script collapse in reverse:** transliterating protected Latin terms into Greek script. Run the self-check.
- **Silent summarization:** merging two entries into one sentence. One entry → one rendered statement.

## 4. Self-check before emitting (both documents)

> Run this check **silently**: fix problems in the rendered files themselves. Do not enumerate
> the checks or quote document content in your reply — the deterministic gate reads the files.

1. Diff against the JSON: any rendered sentence with no schema entry? Delete it.
2. Any schema entry missing from either render? Add it.
3. Every glossary term character-exact in both documents?
4. Every `conditional` entry visibly hedged in both languages?
5. Open questions + conflicts sections present and complete in both?
