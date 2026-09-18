"""Render the requested Chrome viewports, then audit full-page layouts and interaction.
Run from an environment that permits Chrome's macOS process registration.
All outputs and the browser profile stay beside this script.
"""
from pathlib import Path
import subprocess, json, sys
ROOT=Path(__file__).resolve().parent
CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
PAGE=(ROOT/'WALKTHROUGH_v2.html').as_uri()
SCREEN=ROOT/'screens';SCREEN.mkdir(exist_ok=True)
log=[]
for width,height in [(1440,2400),(390,844)]:
 for n in range(1,11):
  args=[CHROME,'--headless=new','--disable-gpu','--hide-scrollbars','--user-data-dir=./chrome',f'--window-size={width},{height}',f'--screenshot=./screens/s{n:02d}-{width}.png',PAGE+f'#{n}']
  run=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=60)
  log.append({'sheet':n,'viewport':[width,height],'command':args,'exit_code':run.returncode,'stderr':run.stderr[-4000:]})
  (SCREEN/'render_log.json').write_text(json.dumps(log,indent=2)+'\n')
  if run.returncode:
   sys.exit('Chrome could not launch. See screens/render_log.json. No visual review is claimed.')
# Full-page captures are needed because long sheets extend below the requested viewport.
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=CHROME,headless=True,args=['--disable-gpu','--hide-scrollbars'],downloads_path=str(SCREEN))
 page=browser.new_page();errors=[];network=[];checks=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.on('request',lambda r: network.append(r.url) if r.url.startswith(('http:','https:')) else None)
 for width,height in [(1440,2400),(390,844),(320,844),(375,844),(768,1100),(1280,1500)]:
  page.set_viewport_size({'width':width,'height':height})
  for n in range(1,11):
   page.goto(PAGE+f'#{n}');page.wait_for_timeout(120)
   assert page.locator('section.sheet:visible').count()==1
   assert page.locator(f'#ch{n:02d}').is_visible()
   overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth')
   checks.append({'sheet':n,'width':width,'page_overflow':overflow})
   assert not overflow,checks[-1]
   if width in (1440,390):page.screenshot(path=str(SCREEN/f's{n:02d}-{width}-full.png'),full_page=True)
 # Verify direct ledger fragments reveal both the containing sheet and disclosure.
 for d in page.locator('details').evaluate_all('(ds)=>ds.map(d=>({id:d.id,sheet:d.closest("section").id}))'):
  page.goto(PAGE+'#'+d['id']);page.wait_for_timeout(100)
  assert page.locator('#'+d['id']).evaluate('(d)=>d.open')
  assert page.locator('#'+d['sheet']).is_visible()
 page.set_viewport_size({'width':1440,'height':2400});page.goto(PAGE+'#ch03');page.wait_for_timeout(100)
 page.evaluate('scrollTo(0,300)');page.wait_for_timeout(150)
 page.locator('#next').click();page.wait_for_timeout(100)
 assert page.locator('#t04').evaluate('(e)=>e===document.activeElement')
 page.go_back();page.wait_for_timeout(150);assert page.locator('#ch03').is_visible();assert abs(page.evaluate('scrollY')-300)<3
 page.go_forward();page.wait_for_timeout(100);assert page.locator('#ch04').is_visible()
 page.locator('#fol').click();assert page.locator('#main').evaluate('(e)=>e.inert')
 page.locator('#contents-close').focus();page.keyboard.press('Shift+Tab');assert page.locator('#contents-list a').last.evaluate('(e)=>e===document.activeElement')
 page.keyboard.press('Tab');assert page.locator('#contents-close').evaluate('(e)=>e===document.activeElement')
 page.keyboard.press('Escape');assert not page.locator('#contents').is_visible();assert page.locator('#fol').evaluate('(e)=>e===document.activeElement')
 page.locator('#main').focus();page.keyboard.press('c');assert not page.locator('#contents').is_visible()
 page.locator('#fol').focus();page.keyboard.press('c');assert page.locator('#contents').is_visible();page.keyboard.press('Escape')
 page.locator('#read-all').click();assert page.locator('section.sheet:visible').count()==10
 page.locator('#expand-ledgers').click();assert page.locator('details:not([open])').count()==0
 page.emulate_media(reduced_motion='reduce');assert page.locator('.sheet').first.evaluate('(e)=>getComputedStyle(e).animationName')=='none'
 # 200% text resizing at a narrow viewport.
 page.set_viewport_size({'width':390,'height':844});page.add_style_tag(content='html{font-size:200%}')
 assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
 page.goto(PAGE+'#ch01');page.emulate_media(media='print');page.pdf(path=str(SCREEN/'walkthrough-a4.pdf'),prefer_css_page_size=True,print_background=True)
 context=browser.new_context(java_script_enabled=False,viewport={'width':390,'height':844})
 plain=context.new_page();plain.goto(PAGE+'#ch06');assert plain.locator('section.sheet:visible').count()==10
 plain.emulate_media(media='print')
 assert plain.locator('details .ledger-table').first.is_visible()
 plain.pdf(path=str(SCREEN/'walkthrough-a4-no-js.pdf'),prefer_css_page_size=True,print_background=True)
 browser.close()
 assert not errors,errors
 assert not network,network
 (SCREEN/'browser_audit.json').write_text(json.dumps({'layout_checks':checks,'js_errors':errors,'external_requests':network,'interaction_checks':'passed','manual_screenshot_review':'still required'},indent=2)+'\n')
print('Captures and browser checks complete. Inspect every viewport/full-page PNG and both PDFs before claiming visual acceptance.')
