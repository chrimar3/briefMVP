from pathlib import Path
import re, collections, hashlib
SOURCE=Path(__file__).resolve().parent/'source_snapshot.html'
s=SOURCE.read_text()
def element(s,start):
    m=re.match(r'<(\w+)\b',s[start:]); tag=m[1]; depth=0
    for t in re.finditer(r'</?'+tag+r'\b[^>]*>',s[start:]):
        depth+= -1 if t[0].startswith('</') else 1
        if depth==0:return s[start:start+t.end()]
    raise ValueError(tag)
def take(s,pattern):
    m=re.search(pattern,s); e=element(s,m.start());return s[:m.start()]+s[m.start()+len(e):],e

titles=[
'Approve a conditional four-week pilot to test whether cited drafts reduce briefing effort.',
'Nine steps prepare the work; a person authorizes the move into shadow creative.',
'The readiness gate checks the input folder before AI classification.',
'Thirty-three facts retain receipts; garbled terms stay flagged.',
'Three contradictions remain open until a person decides.',
'One master record supports both languages; Greek quality still needs review.',
'A named account lead resolves three conflicts and signs the record.',
'Seventeen checks passed on one synthetic project; usefulness remains to be tested.',
'Shadow creative needs three corrections and a creative lead’s judgement.',
'Approve the pilot conditionally; resolve operating cost and capacity before commitment.']
implications=[
'Live use in week 4 depends on the retrospective. Cost and workspace terms remain unresolved; the sponsor owns the conditions.',
'Six AI steps, two plain-code steps, one person. Static review pages support command-line operation; the signature controls the handover.',
'Sufficient inputs proceed to classification. A missing RFP stops the run before a model drafts.',
'Exact quotations are checked by code. The transcript was sent back once; the two garbles remain evidence, not silent repairs.',
'Audience, budget and launch date each need a human decision. Both source positions remain visible.',
'25 cited entries, 3 conflicts, 10 questions. No translation step: Greek and English are rendered from the same object.',
'The account lead records resolutions and signature in brief.json. brief_review.html displays those recorded decisions.',
'Citation presence does not prove semantic support or natural Greek. The pilot must test usefulness beyond these checks.',
'A or B, or neither: a creative lead must evaluate the shadow drafts. Owner and decision date remain unassigned.',
'The capacity case is a target, not measured savings. Plan, spending ceiling, training and operator effort remain unpriced.']
labels=['The decision','The operating boundary','Inputs and readiness','Evidence fidelity','Unresolved conflicts','One bilingual record','Human sign-off','Evaluation scope','Creative review','Pilot conditions']
new=[]
for i,ms in enumerate(re.finditer(r'<section class="sheet[^>]*>.*?</section>',s,re.S),1):
    old=ms[0]; aside=re.search(r'<aside.*?</aside>',old,re.S)[0]
    start=old.index('<div class="body">'); body=element(old,start)[len('<div class="body">'):-6]
    ledgers=[]
    while '<details' in body:
        body,d=take(body,r'<details\b');ledgers.append(d)
    # Keep explanatory support, but no repeated role stamps on each face.
    aside=re.sub(r'<div class="stamps">.*?</div>','',aside,flags=re.S)
    oldnotes=''
    if i==1:
        body=re.sub(r'<p class="kicker">.*?</p>|<h1.*?</h1>|<p class="ask">.*?</p>','',body,flags=re.S)
        body=re.sub(r'<p class="narr">.*?</p>','<p class="narr">Brief Builder turns a client’s documents into a Greek and English brief: claims carry receipts, disagreements remain visible, and gaps become questions.</p>',body,count=1,flags=re.S)
        body=re.sub(r'<p class="howto">.*?</p>','<p class="howto">Executive route: <a href="#ch01">01 · Decision</a> → <a href="#ch02">02 · Operation</a> → <a href="#ch10">10 · Conditions</a>. Read the evidence on sheets 03–09.</p>',body,flags=re.S)
        body=body.replace('One brief used about a million tokens; a token is roughly three-quarters of a word the model reads or writes. At 15 briefs a month that is about 15 million, the figure to hold against a plan&rsquo;s usage window.','Stage-one usage. Tokens are units of text processed; counts include cached text. Capacity must be re-measured under the changed routing.')
        ledgers[0]=ledgers[0].replace('<div class="cols2">','<p class="foot">Stage one: 0.53 M Haiku 4.5 and 0.45 M Sonnet 5; 56% cache reads, 27% cache writes. Source: run_manifest.json.</p><div class="cols2">',1)
    if i==2:
        aside,oldnotes=take(aside,r'<p class="marginalia">')
        body=body.replace('<p class="note"><b>Where the documents go</b>', '<p class="note"><b>Where the documents go</b>')
        body=body.replace('only clients at the two lowest sensitivity tiers in the pilot','S0–S1 clients only in the pilot')
        body+='<p class="note"><b>Operating owners.</b> The AI specialist operates; two champions train by week 4. Traffic owns the spec table, a pilot stub requiring confirmation. Account lead records resolutions/signature in the brief object; creative lead evaluates. <span class="cite">PRD §8</span></p>'
    if i==3:
        body += '<p class="note"><b>Four checks, no AI:</b> RFP present; at least two substantive sources; money mentioned; date mentioned. With sufficient input, classification is advertising creative, high confidence, S1 (second-lowest sensitivity tier). <span class="cite">run_manifest.json; classification.json</span></p>'
        body=body.replace('Without the RFP the run stops with a request; a small model then classifies: advertising creative, high confidence, S1.','Missing RFP: STOP. Sufficient input: advertising creative, high confidence, S1 (second-lowest sensitivity tier).')
    if i==4:
        body=body.replace('The transcriber garbled two English terms; the machine flags and proposes; the finished documents print the glossary term, flag cited.','Two garbles stay flagged; renders print the glossary term with the flag cited.')
        body=body.replace('What the machine wrote, with its receipt &mdash; the repair record and the second reader are in the extraction ledger','Extracted facts and their receipts')
        # Move the speculative example, intact, to the extraction ledger.
        match=re.search(r'<div class="receipt"><figure class="inner">\s*<blockquote lang="en">',body)
        receipt=element(body,match.start());body=body.replace(receipt,'');oldnotes+=receipt
        row=re.search(r'<tr><td>4b verify-extract.*?</tr>',ledgers[1],re.S)[0]
        ledgers[1]=ledgers[1].replace(row,'')
        ledgers.append('<details class="ledger"><summary>Later verifier · not in the graded totals</summary><div class="ledger-wrap"><table class="ledger-table"><caption>Validated 29 July; adopted 30 July · separate comparison</caption><tr><th>Step / date</th><th>Agent</th><th>Model / reason</th><th>Tokens</th><th>Time</th><th>Result</th></tr>'+row+'</table></div></details>')
    if i==6:
        body += '<p class="note">Greek register is a pilot metric; code cannot judge natural agency Greek. <span class="cite">PRD §7</span></p>'
        aside,note=take(aside,r'<p class="marginalia"><span class="lbl">Glossary');oldnotes+=note
        body=re.sub(r'<p class="note">The extract shows.*?</p>','<p class="note">The extract shows two of four key messages. Source paths: runs/tier3/brief_en.html, brief_el.html and brief_review.html. Embedded extracts are shown here; complete source documents remain in the repository.</p>',body,flags=re.S)
    if i==7:
        aside,note=take(aside,r'<p class="marginalia"><span class="lbl">What the account lead');oldnotes+=note
        body=body.replace('Review time was not timed on this run; it is the first pilot measurement (target: under 30 minutes of account-lead attention, PRD &sect;7).','Review was untimed. The &lt;30-minute review target needs definition agreement: PRD §7 measures time-to-first-draft attention. Sponsor to reconcile before measurement.')
    if i==8:
        body=body.replace('Every check is a yes or a no; none is an opinion.','Checks return pass or fail; human review still judges support and Greek register.')
        body=body.replace('T3 / X','T3+X')
        ledgers=[x.replace('No invented or resolved total in the brief or either render','no invented or resolved total in the brief or either render') for x in ledgers]
    if i==9:
        # Keep art and original image bytes untouched, following the decision material.
        body,art=take(body,r'<div class="hero">')
        body,brief=take(body,r'<article class="brief"')
        brief,ab=take(brief,r'<div class="ab">')
        ab=ab.replace('Signed as the account lead&rsquo;s was: in the run, by a named person, due before week 4 goes live.','Creative lead signature pending. Owner/date unassigned; evaluation authorizes no delivery.')
        aside,strikes=take(aside,r'<p class="marginalia"><span class="lbl">Three strikes')
        strikes=strikes.replace('class="marginalia"','class="corrections"').replace('<span class="lbl">Three strikes, one call</span>','<b>Three corrections and one judgement call.</b> ')
        # Remove duplicate proposition on face, retain verbatim draft excerpt in ledger.
        pstart=brief.index('        <h4>'); pend=brief.index('        <h4><span class="n">2')
        oldnotes+=brief[pstart:pend];brief=brief[:pstart]+brief[pend:]
        # Readiness is supporting sign-off evidence on 07, retained here in ledger.
        pstart=brief.index('        <h4><span class="n">8')
        oldnotes+=brief[pstart:brief.rindex('</article>')];brief=brief[:pstart]+'</article>'
        body+=ab+strikes+brief+art
        ledgers=[x.replace('ring, leaf and name','wind stroke, bubbles and name') for x in ledgers]
        # Remove coloured UI swatches; retain palette specification as plain text.
        for j,l in enumerate(ledgers):
            if '<div class="swatches">' in l:
                l,sw=take(l,r'<div class="swatches">');l+='' # preserve the palette facts below
                l=l.replace('</details>','<p class="foot">Artwork palette: Aegean Blue #1B4F8A, Citrus Yellow #F5C518, white; flat fills only.</p></details>')
                ledgers[j]=l
    if i==10:
        body=body.replace('Targets: question precision &gt;80%, draft survival &gt;70%, review &lt;30 minutes; Greek-language quality and voluntary adoption.','Targets: question precision &gt;80%, survival &gt;70%, review &lt;30 minutes pending definition agreement; Greek quality 1–5 plus EL/EN edits; voluntary adoption 2/2 and ≥3 additional leads in month 2.')
        body=body.replace('conditional on the retrospective results.','conditional on the retrospective results. Alternative: defer until capacity and terms are confirmed.',1)
        body=body.replace('Nine model calls (four documents, one sent back once).','Nine recorded stage-one model calls, including the repair; agent attempts/sessions, not necessarily nine API requests.')
        body=re.sub(r'<p class="lastline">.*?</p>','<p class="note"><a href="#ch01">Return to the decision on sheet 01</a>.</p>',body,flags=re.S)
        ledgers[0]=ledgers[0].replace('<h2 class="sub">Measured usage','<p class="foot">Attention definitions require sponsor agreement: PRD §7 concerns time to first draft, while the review target here is &lt;30 minutes. The 50-minute total-attention target is separate. Week 1 establishes the baseline.</p><h2 class="sub">Measured usage')
        row=re.search(r'<tr><td>transcript extraction under the 30 July routing.*?</tr>',ledgers[0],re.S)[0]
        ledgers[0]=ledgers[0].replace(row,'').replace('<p class="foot"><b>Dollars,','<div class="ledger-wrap"><table class="ledger-table"><caption>Usage comparison · tokens, not time</caption><tr><th>Stage</th><th>Model / attempts</th><th>Tokens</th><th>Comparison</th></tr>'+row+'</table></div><p class="foot"><b>Dollars,')
        ledgers[0]=re.sub(r'<p class="foot"><b>Links and sources:</b>.*?</p>','<p class="foot"><b>Source paths:</b> runs/tier3, harness_report.json, docs/COST_MODEL.md, runs/routing-validate-01, docs/EVIDENCE.md and fixtures/northlight_01. All essential exhibits are embedded; full unseen drafts are not included. Synthetic data throughout.</p>',ledgers[0],flags=re.S)
    # Takeaways remain accessible in the ledger; the implication gives the face one clear reading path.
    body,tw=take(body,r'<ul class="takeaways">')
    if oldnotes:
        ledgers[0]=ledgers[0].replace('</details>','<div class="supporting">'+oldnotes+'</div></details>')
    # Compact provenance on the right, after the exhibit in DOM order.
    if i==9: aside=re.sub(r'<p class="marginalia">.*?</p>','',aside,flags=re.S)
    fol=re.search(r'<div class="folio">.*?</div>',aside,re.S)[0]
    aside=aside.replace(fol,'')
    header=f'<header class="slide-head"><p class="kicker">{i:02d} / {labels[i-1]} · Brief Builder</p><h1 class="title action" id="t{i:02d}" tabindex="-1">{titles[i-1]}</h1><p class="implication">{implications[i-1]}</p></header>'
    # Preserve the takeaways as a short ledger intro on dense creative sheet.
    ledgers[0]=ledgers[0].replace('</summary>','</summary>'+tw,1);tw=''
    new.append(f'<section class="sheet'+(' cover' if i==1 else '')+f'" id="ch{i:02d}" data-n="{i}" aria-labelledby="t{i:02d}">\n'+header+'\n<div class="sheet-tools">'+fol+'</div>\n'+(f'<div class="implications">{tw}</div>' if tw else '')+'\n<div class="body">'+body+'</div>\n'+aside+'\n<div class="ledgers">'+''.join(ledgers)+'</div>\n</section>')
# Accessible offline links and table metadata without touching evidence HTML.
doc='\n'.join(new)
doc=re.sub(r'<a class="repo" href="([^"]+)"[^>]*>(.*?)</a>',r'<span class="source-path">\1</span>',doc,flags=re.S)
doc=re.sub(r'<button type="button" class="jump" data-go="(\d+)">(.*?)</button>',lambda m:f'<a class="jump" href="#ch{int(m[1]):02d}">{m[2]}</a>',doc,flags=re.S)
doc=doc.replace('Full documents in the repository:','Source paths:').replace('Sections 3&ndash;6 in full, and the further spec rows:','Source for full sections 3–6 and further spec rows (not embedded):')
doc=doc.replace('gloss &mdash;','interpretation &mdash;')
# This modifies captions only; clippings themselves remain byte-identical.
doc=doc.replace('<th>','<th scope="col">').replace('<th class="r">','<th scope="col" class="r">')
doc=re.sub(r'(<table[^>]*>)(\s*)(<tr><th.*?</tr>)',r'\1\2<thead>\3</thead>',doc,flags=re.S)
doc=re.sub(r'(</caption>)(\s*)(<tr><th.*?</tr>)',r'\1\2<thead>\3</thead>',doc,flags=re.S)
count=0
def ledger_id(m):
    global count
    count+=1;return f'<details class="ledger" id="ledger-{count:02d}">'
doc=re.sub(r'<details class="ledger">',ledger_id,doc)
doc=doc.replace('<div class="ledger-wrap">','<div class="ledger-wrap" role="region" tabindex="0" aria-label="Evidence table; scroll horizontally if needed">')
# Build a static contents list so real anchors also work without script.
contents=''.join(f'<li><a href="#ch{i:02d}"><span class="n">{i:02d}</span><span>{labels[i-1]}</span></a></li>' for i in range(1,11))
glyphs=re.search(r'<svg width="0".*?</svg>',s,re.S)[0]
head='''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Brief Builder — a conditional pilot</title><style>'''+Path('v2.css').read_text()+'''</style></head><body>
<a class="skip" href="#main">Skip to the walkthrough</a>
'''+glyphs+'''<main class="desk" id="main" tabindex="-1"><div class="runhead"><span><b>Northlight Communications</b> · Brief Builder</span><span>Synthetic project · northlight_01 · graded 24 July 2026</span></div>
<div class="reading-controls"><button id="read-all" type="button" aria-pressed="false">Read all sheets</button><button id="expand-ledgers" type="button" aria-pressed="false">Expand ledgers</button><span>Evidence walkthrough · 10 sheets</span></div>'''
footer='''</main><div class="contents" id="contents" role="dialog" aria-modal="true" aria-labelledby="contents-h" hidden><div class="contents-in"><button class="close" id="contents-close" type="button">Close</button><h2 id="contents-h">Contents</h2><p>Decision → operating boundary → evidence → pilot conditions.</p><ol id="contents-list">'''+contents+'''</ol></div></div>
<nav class="nav" aria-label="Sheet navigation"><div class="nav-in"><button class="back" id="back" type="button">Back</button><div class="ruler" id="ruler"><button class="fol open-contents" id="fol" type="button">01 / 10 &middot; Contents</button></div><button class="next" id="next" type="button"><span>Next</span><b id="next-title">The operating boundary</b><span aria-hidden="true">→</span></button></div></nav><div class="vh" aria-live="polite" id="announce"></div>
<noscript><nav class="offline-contents" aria-label="All sheets"><h2>All sheets</h2><ol>'''+contents+'''</ol></nav></noscript><script>'''+Path('v2.js').read_text()+'''</script></body></html>'''
result=head+doc+footer
for pattern in [r'<blockquote[^>]*>.*?</blockquote>',r'<mark class="cited">.*?</mark>']:
    assert collections.Counter(re.findall(pattern,s,re.S))==collections.Counter(re.findall(pattern,result,re.S)),pattern
assert re.search(r'<g id="kv-art">.*?</g>\s*</defs>',s,re.S)[0]==re.search(r'<g id="kv-art">.*?</g>\s*</defs>',result,re.S)[0]
assert re.search(r'<img[^>]+>',s)[0]==re.search(r'<img[^>]+>',result)[0]
Path('WALKTHROUGH_v2.html').write_text(result)
print('Built',len(result.encode()),'bytes; all quotes, cited marks, kv-art and JPEG identical.')
