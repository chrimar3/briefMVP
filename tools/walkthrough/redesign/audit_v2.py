"""Offline structural and source-preservation audit; supplements the unmodified gate."""
from pathlib import Path
import re, collections, hashlib, json, html, subprocess
from bs4 import BeautifulSoup
root=Path(__file__).resolve().parent
source=root/'source_snapshot.html'
a=source.read_text();b=(root/'WALKTHROUGH_v2.html').read_text(); soup=BeautifulSoup(b,'html.parser')
checks={}
def check(name,condition):
 checks[name]=bool(condition)
 if not condition: raise AssertionError(name)
check('frozen_snapshot_sha256',hashlib.sha256(a.encode()).hexdigest()=='ca5f7d8a791515ab108c3d98e17269a29438e69bd2133fd7acf32a25d08e0d8b')
for name,pattern in [('blockquotes',r'<blockquote[^>]*>.*?</blockquote>'),('cited_marks',r'<mark class="cited">.*?</mark>'),('key_visual',r'<g id="kv-art">.*?</g>\s*</defs>'),('packaging_image',r'<img[^>]+>')]:
 check(name+'_byte_identical',collections.Counter(re.findall(pattern,a,re.S))==collections.Counter(re.findall(pattern,b,re.S)))
sa=BeautifulSoup(a,'html.parser')
check('every_original_table_data_row_preserved',collections.Counter(tuple(td.get_text(' ',strip=True) for td in row.find_all('td')) for row in sa.select('tr') if row.find('td'))==collections.Counter(tuple(td.get_text(' ',strip=True) for td in row.find_all('td')) for row in soup.select('tr') if row.find('td')))
check('ten_labelled_sheets',len(soup.select('section.sheet[aria-labelledby]'))==10)
check('ten_conclusion_titles',len(soup.select('h1.title.action'))==10)
check('no_nested_disclosures',not soup.select('details details'))
check('table_headers_repeat_in_print',all(t.find('thead') for t in soup.find_all('table')))
check('table_headers_scoped',all(t.get('scope') for t in soup.find_all('th')))
check('real_offline_links_only',all(x.get('href','').startswith('#') for x in soup.select('a[href]')))
check('no_external_resources',not re.search(r'<link\b|@import|url\(|(?:src|href)=["\']https?://',b))
check('one_embedded_JPEG',len(soup.find_all('img'))==1 and soup.img['src'].startswith('data:image/jpeg;base64,'))
check('exactly_three_decisions',len(soup.select('ol.decisions > li'))==3)
check('seventeen_individual_checks',len(soup.select('#ch08 details .exam li:not(.tier)'))==17)
check('X3_exact', 'no invented or resolved total in the brief or either render' in soup.select_one('#ch08').get_text())
check('three_blank_conflict_lines',len(soup.select('#ch05 .resolve .line'))==3 and all(not x.get_text(strip=True) for x in soup.select('#ch05 .resolve .line')))
check('three_initialled_human_resolutions',len(soup.select('#ch07 .line.written'))==3 and [x.text for x in soup.select('#ch07 .init')]==['CM']*3)
check('EL_EN_two_sections_each',all(len(soup.select(f'#ch06 .page[lang="{lang}"] h4'))>=2 for lang in ['el','en']))
words={}
for m in re.finditer(r'<section class="sheet[^>]*" id="(ch\d\d)"(.*?)</section>',b,re.S):
 v=re.sub(r'<details.*?</details>','',m[2],flags=re.S);v=re.sub('<span class="sic">sic</span>','',v);v=re.sub('<[^>]+>','',v)
 words[m[1]]=len(html.unescape(v).strip().split())
check('visible_word_caps',all(n<= (750 if k=='ch09' else 650) for k,n in words.items()))
gate=subprocess.run(['python3','/Users/chrism/AI-transformation-assignment/brief-builder/tools/walkthrough/checks.py','--file',str(root/'WALKTHROUGH_v2.html')],capture_output=True,text=True)
check('unmodified_checks_py_passes',gate.returncode==0)
report={'checks':checks,'visible_words':words,'bytes':len(b.encode()),'source_bytes':len(a.encode()),'gate':json.loads(gate.stdout),'browser_verification':'BLOCKED: Chrome aborts; Chromium reports macOS bootstrap_check_in Permission denied (1100). No screenshots produced.'}
(root/'audit_results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
(root/'checks_output.json').write_text(gate.stdout)
print(json.dumps(report,ensure_ascii=False,indent=2))
