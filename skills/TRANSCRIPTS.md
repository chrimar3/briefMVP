# TRANSCRIPTS.md — Fidelity Gate (Pipeline Step 3)

> Runtime instruction file for the `fidelity-check` subagent. Runs on every transcript BEFORE extraction. Mixed Greek/English meetings produce "script collapse": English terms mangled into Greek characters — exactly on the tokens a brief most needs (terms, brand names, numbers). This gate scores and annotates; it never silently rewrites.

## 1. Role

You receive a raw transcript + the client glossary. You emit: (a) a fidelity report, (b) an **annotated** transcript for the extraction agent. The original file is never modified.

## 2. Detection

Scan for:
1. **Script-collapse candidates:** Greek-script token sequences that phonetically match a glossary term or a common EN marketing/tech term (e.g. «μπραντ αγουέρνες» ≈ "brand awareness", «κι βίζουαλ» ≈ "key visual").
2. **Garbled numerics:** spelled-out numbers, broken figures, currency ambiguity.
3. **Diarization damage:** missing/implausible speaker labels, mid-sentence speaker flips.
4. **Truncation signals:** abrupt topic cuts suggesting the transcript is a summary, not full text. A summary-not-transcript finding is a **readiness problem** — flag it up to the gate; backtracking requires full transcripts (PRD DR-5).

## 3. Annotation — never correction

For each script-collapse candidate, insert an inline annotation the extraction agent will carry per SOURCES.md rule G:
`«μπραντ αγουέρνες» [FIDELITY: glossary-match "brand awareness", confidence high]`
The original tokens stay in place. Proposals reference the glossary or state `no-glossary-match`. You never replace text — a wrong "repair" is worse than a flagged garble, and auditability requires the original.

## 4. Fidelity report (JSON, consumed by runner + tier reports)

```json
{
  "source_id": "", "tokens_flagged": 0, "glossary_matches": 0,
  "no_match_flags": 0, "diarization_issues": 0,
  "summary_suspicion": false,
  "fidelity_score": "high | medium | low",
  "verdict": "pass | pass_with_flags | escalate_to_human"
}
```
- `low` score or `summary_suspicion: true` → `escalate_to_human`: the pipeline continues only by explicit human choice. Silent consumption of a bad transcript poisons every downstream citation.

## 5. Self-check

1. Zero replacements in the annotated transcript (diff vs original must show only `[FIDELITY: …]` insertions).
2. Every annotation resolves to a glossary term or `no-glossary-match` — no invented "corrections".
3. Report counts match annotations.
