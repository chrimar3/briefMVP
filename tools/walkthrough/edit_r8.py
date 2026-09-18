"""Round-8 editor pass (bounded hypothesis: answer the failed creative-director task and the three gaps the CMO, CFO and
engineer agree on; no restructuring). Asserting replacements."""
import pathlib
p = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html')
doc = p.read_text(encoding='utf-8'); orig = doc; log = []
def rep(old, new, tag, count=1):
    global doc
    assert doc.count(old) == count, (tag, doc.count(old), old[:90]); doc = doc.replace(old, new); log.append(tag)
# --- creative director (task failed) ---
rep('except three things for the creative lead to strike.</h1>', 'except three things to strike and one call for the creative lead.</h1>', 'E1 title count')
rep('<span class="lbl">Three things to strike</span>', '<span class="lbl">Three strikes, one call</span>', 'E2 margin label')
rep('Draft A&rsquo;s &ldquo;<mark class="flag">(&euro;80&ndash;85k)</mark>&rdquo; invents a budget total the brief never states.',
    'Draft A&rsquo;s budget line, &ldquo;Production budget: &lsquo;in the eighties&rsquo; <mark class="flag">(&euro;80&ndash;85k)</mark>&rdquo;, turns the words into a total the brief never states (creative_brief_sonnet.md, line 64).', 'E3 show the offence')
rep('Demo spec table: values are a pilot stub and need the traffic team&rsquo;s confirmation before delivery.',
    'Demo spec table: values are a pilot stub and need the traffic team&rsquo;s confirmation before delivery; the gate only checks that each spec token exists in the table, not that the row fits the deliverable.', 'E4 gate negative')
rep('''        <div class="ab">
          <p class="pencil">A/B on identical input. Both drafts flagged the natural-ingredients claim as unusable until the ingredient list arrives; only the key visual withholds it. Both kept the TikTok dance out; A positions the brand, B makes a product claim.</p>''',
    '''        <h4><span class="n">3&ndash;6</span>Feel, tone, reasons to believe <span class="pencil">&mdash; condensed; in full in the draft file</span></h4>
        <p>Feel: confident and refreshed, quietly proud it&rsquo;s Greek and genuinely premium, not a beach-party gimmick. Tone: confident, modern Greek with natural use of English category terms; humour welcome, sarcasm about competitors not. Reasons to believe: zero sugar, a permitted on-label claim; natural ingredients only once the approved ingredient list arrives. <span class="cite">[key_messages; mandatories; open_questions/mandatories]</span></p>

        <div class="ab">
          <p class="pencil">A/B on identical input: both flag the natural-ingredients claim as unusable until the ingredient list arrives and keep the TikTok dance out; A positions the brand, B makes a product claim.</p>''', 'E5 sections 3-6 condensed')
rep('One drawing, two crops, drawn for this walkthrough, and one packaging application from an image model; the pipeline emits text only. The mark is the meltemi, the north wind, drawn as one stroke that releases the fizz; &ldquo;zero sugar&rdquo; stays a written claim in the line.',
    'One drawing, two crops, and one packaging application from an image model; the pipeline emits text only. The mark is the meltemi, the north wind, one stroke that releases the fizz; &ldquo;zero sugar&rdquo; stays a written claim.', 'E5b slug trim')
rep('Packaging application &middot; raster mock-up on a standard 330&thinsp;ml can &middot; generated for this walkthrough by an image model (gpt-6-astra, built-in image tool) from the lockup above; packaging is an undefined context in the brief',
    'Packaging application &middot; raster mock-up on a standard 330&thinsp;ml can, generated for this walkthrough by an image model from the lockup above; packaging is an undefined context in the brief', 'E5c plate slug trim')
# --- CMO ---
rep('Stage one of the graded run: 0.53 M on Haiku 4.5, 0.45 M on Sonnet 5; five-sixths of it context, not new writing: 56% re-read from cache, 27% written to it.',
    'One brief used about a million tokens; a token is roughly three-quarters of a word the model reads or writes. At 15 briefs a month that is about 15 million, the figure to hold against a plan&rsquo;s usage window.', 'E6 token tile plain')
rep('''<details class="ledger">
        <summary><span>Ledger &mdash; where each part lives</span></summary>''',
    '''<p class="note"><b>Where the documents go</b>, as the PRD assumes it: the agency&rsquo;s own workspace under a data-processing agreement, EU processing, zero retention; only clients at the two lowest sensitivity tiers in the pilot, and the runner refuses higher tiers before drafting. The subscription direction leaves the commercial terms to confirm before week 1 (decision 3). <span class="cite">docs/PRD.md &sect;8&ndash;9 &middot; pipeline/gates.py</span></p>
<details class="ledger">
        <summary><span>Ledger &mdash; where each part lives</span></summary>''', 'E7 where documents go')
rep('Worth about &euro;4.0&ndash;4.2k before operating costs. Assumptions: (120 &minus; 50) minutes saved per brief &times; 180 briefs/year &divide; 60 &times; &euro;19&ndash;20/hour. PRD A1, A2, A4: validate baseline, volume and rate in week 1. Pilot effort and operating costs are still to be estimated.',
    'A brief takes an account lead about two hours today (PRD A1); the target is fifty minutes (&sect;2). Across 180 briefs a year (A2) that is about 210 hours, worth &euro;4.0&ndash;4.2k at &euro;19&ndash;20 an hour (A4), before running and support costs, which are not yet estimated; all three inputs are validated in week 1.', 'E8 savings in prose')
rep('Approve the four-week pilot; re-baseline usage before week 1: the graded run&rsquo;s 1.13 million tokens measure usage, not price.</h1>',
    'Approve the four-week pilot: usage is measured in tokens, the cost of running it is not yet, and week 1 settles both.</h1>', 'E9 sheet 10 headline')
# --- CFO ---
rep('measure the plan&rsquo;s usage window against roughly 15 M tokens a month before week 1',
    'measure the plan&rsquo;s usage window against roughly 15 M tokens a month before week 1 (15 M under the graded routing; higher under the 30 July routing until decision 2 re-measures it)', 'E10 decision 3 caveat', count=2)
# --- engineer ---
rep('The pilot enforces S0&ndash;S1 in code (exam check T2.2).', 'The pilot enforces S0&ndash;S1 at run time: pipeline/gates.py refuses S2&ndash;S3 before drafting, and exam check T2.2 re-checks it afterwards.', 'E11 tier gate precise')
rep('The account lead records resolutions and the signature in the brief object itself; the pilot runbook covers how.',
    'The account lead writes each resolution into brief.json (conflicts[n].resolution and resolved_by) and the sign-off block (signoff: status, signed_by, signed_ts, edits_summary), a schema-validated edit in v1; a one-page runbook is a week-1 deliverable (PRD &sect;8).', 'E12a mechanism (sheet 02 ledger)')
rep('then records resolutions and the signature in the brief object itself; the pilot runbook covers how; onboards', 'then records resolutions and the signature in the brief object (fields in the sheet-07 ledger); onboards', 'E12b sheet 02 bullet')
rep('a review view with recorded resolutions and signature, language toggle and copyable questions. The account lead records decisions in the brief object itself; the pilot runbook covers how.',
    'a review view with recorded resolutions and signature, language toggle and copyable questions. The account lead records decisions in the brief object itself (how: sheet 07).', 'E12c sheet 06 note')
rep('is a review view: recorded resolutions and signature, language toggle and copyable questions. The account lead records decisions in the brief object itself; the pilot runbook covers how.',
    'is a review view: recorded resolutions and signature, language toggle and copyable questions. The account lead writes each resolution into brief.json (conflicts[n].resolution, resolved_by) and the sign-off block (status, signed_by, signed_ts, edits_summary): a schema-validated edit in v1, a one-page runbook by week 1 (PRD &sect;8).', 'E12d sheet 07 marginalia')
rep('<p class="stage-lbl">Stage 1 &middot; the client brief &middot; every AI step is gated: sent back once, then stop', '<p class="stage-lbl">Stage 1 &middot; the client brief &middot; extraction, synthesis and render are gated: sent back once, then stop', 'E13 which steps are gated')
assert doc != orig; p.write_text(doc, encoding='utf-8'); print(f'{len(log)} edits applied:', ', '.join(log))
