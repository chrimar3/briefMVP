"""Round-7 editor pass (bounded hypothesis: fix every verified hard failure and the auditors' factual-precision
and cheap rendered-UX findings; no restructuring, no new prose beyond a clause). Asserting replacements."""
import pathlib
p = pathlib.Path('/Users/chrism/AI-transformation-assignment/brief-builder/WALKTHROUGH.html')
doc = p.read_text(encoding='utf-8'); orig = doc; log = []
def rep(old, new, count=1, tag=''):
    global doc
    assert doc.count(old) == count, (tag, doc.count(old), old[:90])
    doc = doc.replace(old, new); log.append(tag)

# ---- HARD FAILURES ----
rep('&times; 180 briefs a year &times; &euro;19&ndash;20 an hour;', '&times; 180 briefs a year &divide; 60 = 210 hours, &times; &euro;19&ndash;20 an hour;', tag='H1 ledger formula ÷60')
rep('Every quote in the brief exists word for word in its source; a failing output is sent back once, then the run stops.',
    'Every cited anchor in the brief object exists word for word in its source (the documents may quote in translation); a failing output is sent back once, then the run stops.', tag='H2 scoped guarantee')
MARK = '<svg class="mark" viewBox="0 0 18 18" aria-hidden="true"><path d="M3 9.5l4 4 8-9"/></svg>'
rep('<li><span>T1</span><span>4 checks</span><span>Evidence: shape, exact citations and two flagged garbles.</span><span class="res">pass</span></li>',
    f'<li>{MARK}<span class="id">T1</span><span>Evidence layer, 4 checks: shape, exact citations and two flagged garbles.</span><span class="res">pass</span></li>', tag='H3a exam row')
rep('<li><span>T2</span><span>6 checks</span><span>Brief and renders: structure, sensitivity, citations, glossary and readiness.</span><span class="res">pass</span></li>',
    f'<li>{MARK}<span class="id">T2</span><span>Brief and both documents, 6 checks: structure, sensitivity, citations, glossary and readiness.</span><span class="res">pass</span></li>', tag='H3b exam row')
rep('<li><span>T3 / X</span><span>7 checks</span><span>Seeded contradictions and gaps found; retraction, speculation and budget traps contained.</span><span class="res">pass</span></li>',
    f'<li>{MARK}<span class="id">T3 / X</span><span>Seeded traps, 7 checks: contradictions and gaps found; retraction, speculation and budget traps contained.</span><span class="res">pass</span></li>', tag='H3c exam row')

# ---- FACTUAL PRECISION (verified against the repository) ----
rep('83% context rather than new writing: 56% re-read from cache, 27% written to it', 'five-sixths of it context, not new writing: 56% re-read from cache, 27% written to it', tag='S1 cache share')
rep('Traffic team: owns the spec table.', 'Traffic team: owns the spec table (a pilot stub in this demo).', tag='S2 stub caveat')
rep('One folder, one command: about 25 minutes of machine time, about 50 of account-lead attention',
    'One folder, one command: about 25 minutes of machine time (measured before the 30 July routing change; re-baseline pending), about 50 of account-lead attention', tag='S3 timing scope')
rep('a page of plain English handed to the model unchanged every run', 'a few pages of plain English handed to the model unchanged every run', tag='S4 rule files size')
rep('about 2&thinsp;500 non-blank lines across the eight pipeline modules in the ledger below', 'about 2&thinsp;500 non-blank lines, counted across the eight pipeline modules in the ledger below', tag='S5 line count method')
rep('model (resolved id)', 'model id as recorded', count=7, tag='S6 model column header')
rep('Answer key sealed 23 July, before the pipeline ran on 24 July; the grader',
    'Answer key written 23 July and committed at 00:27 on 24 July, sixteen hours before the run started; the grader', tag='S7 answer key timing')
rep('<h3>Launch date <span>rfp_meltemi &sect;5 &middot; emails_thread Message 2</span></h3>',
    '<h3>Launch date <span>rfp_meltemi &sect;5 &middot; emails_thread Message 2 &middot; two of four recorded positions</span></h3>', tag='S8 timeline positions')
rep('the record above is quoted from the run as written', 'the record above is quoted from the run', tag='S9 as written')
rep('Draft B also calls the TikTok dance &ldquo;retracted&rdquo;; it was speculative, while metro posters were retracted.',
    'Draft B also calls the TikTok dance &ldquo;floated speculatively and retracted&rdquo;; it was speculative, while metro posters were retracted.', tag='S10 third strike quote')
rep('Two trained brief champions run the command from a one-page runbook after the pilot.',
    'Two brief champions, trained by week 4, run the command from a one-page runbook thereafter.', tag='S11 champions timing')

# ---- RENDERED UX / ACCESSIBILITY (cheap, from the UX auditor) ----
rep("    var title = CH[cur === N ? 0 : cur].t;\n    next.setAttribute('aria-label', 'Next sheet: ' + title);",
    "    next.setAttribute('aria-label', cur === N ? 'Back to the cover' : 'Next sheet: ' + CH[cur].t);", tag='U1 last-sheet label')
rep("    if (n < 1) n = 1; if (n > N) n = N;\n    scrollPos[cur] = window.scrollY;",
    "    if (n < 1) n = 1; if (n > N) n = N;\n    if (n === cur) { render(focusTitle !== false, false); return; }\n    scrollPos[cur] = window.scrollY;", tag='U2 go() no-op guard')
rep('.ledger summary { list-style: none; cursor: pointer; display: flex; justify-content: space-between;', '.ledger summary { list-style: none; cursor: pointer; display: flex; justify-content: flex-start;', tag='U3a summary alignment')
rep('.ledger summary .key { color: var(--pencil);', '.ledger summary .key { margin-left: auto; color: var(--pencil);', tag='U3b summary key')
rep("  [].slice.call(document.querySelectorAll('.jump')).forEach(function (b) { b.addEventListener('click', function () { go(+b.getAttribute('data-go')); }); });",
    "  [].slice.call(document.querySelectorAll('.jump')).forEach(function (b) { if (/^\\d+$/.test(b.textContent.trim())) b.setAttribute('aria-label', 'Go to sheet ' + b.textContent.trim()); b.addEventListener('click', function () { go(+b.getAttribute('data-go')); }); });\n"
    "  [].slice.call(document.querySelectorAll('.ledger-wrap')).forEach(function (w) { w.setAttribute('tabindex', '0'); w.setAttribute('role', 'region'); w.setAttribute('aria-label', 'Table, scrolls sideways'); });", tag='U4+U9 jump labels, scroll regions')
rep('@media print {\n  html.js .sheet:not(.active) { display: grid; }',
    '@media print {\n  html.js .sheet:not(.active) { display: grid; }\n  .ledger-wrap { overflow: visible; }\n  .desk { padding: 0 0 24px; max-width: none; }', tag='U5 print')
rep('@media (max-width: 600px) {', '@media (max-width: 600px) {\n  .cover .title { font-size: 34px; line-height: 38px; }\n  .cover .title .el { font-size: 20px; line-height: 27px; }', tag='U6 cover title phones')
rep('  .ruler { min-width: 0; overflow-x: auto; }', '  .ruler { min-width: 0; overflow-x: auto; padding: 4px 0; }', tag='U7 ruler focus room')
rep('html.js .sheet:not(.active) { display: none; }', 'html.js .sheet:not(.active) { display: none; }\nhtml:not(.js) .nav { display: none; }', tag='U8 no-JS nav')
rep('  .ruler .fol { border: 1.5px solid var(--ink); padding: 8px 10px; text-decoration: none; flex: none; }',
    '  .ruler .fol { border: 1.5px solid var(--ink); padding: 8px 10px; text-decoration: none; flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }', tag='U10 folio ellipsis')

assert doc != orig
p.write_text(doc, encoding='utf-8')
print(f'{len(log)} edits applied:', ', '.join(log))
