(function () {
  'use strict';
  var CH = [
    { t: 'The decision' },
    { t: 'The operating boundary' },
    { t: 'Inputs and readiness' },
    { t: 'Evidence fidelity' },
    { t: 'Unresolved conflicts' },
    { t: 'One bilingual record' },
    { t: 'Human sign-off' },
    { t: 'Evaluation scope' },
    { t: 'Creative review' },
    { t: 'Pilot conditions' }
  ];
  var root=document.documentElement, sheets=Array.from(document.querySelectorAll('.sheet'));
  var main=document.getElementById('main'),nav=document.querySelector('.nav');
  var contents=document.getElementById('contents'),list=document.getElementById('contents-list');
  var back=document.getElementById('back'),next=document.getElementById('next'),fol=document.getElementById('fol');
  var nextTitle=document.getElementById('next-title'),announce=document.getElementById('announce');
  var all=document.getElementById('read-all'),expand=document.getElementById('expand-ledgers');
  var cur=1,opener=null,allMode=false,positions={},printing=false,lastURL='',restoring=false;
  function pad(n){return String(n).padStart(2,'0');}
  function targetFromHash(){
    var hash=decodeURIComponent(location.hash.slice(1)),legacy=/^(?:ch)?(\d{1,2})$/.exec(hash);
    if(legacy)return document.getElementById('ch'+pad(Math.max(1,Math.min(10,+legacy[1]))));
    return document.getElementById(hash)||sheets[0];
  }
  function paint(){
    sheets.forEach(function(s,i){s.classList.toggle('active',i+1===cur);});
    fol.textContent=pad(cur)+' / 10 · Contents';back.disabled=cur===1;
    nextTitle.textContent=cur===10?'The decision':CH[cur].t;
    next.setAttribute('aria-label',cur===10?'Return to sheet 01':'Next sheet: '+CH[cur].t);
    list.querySelectorAll('a').forEach(function(a,i){if(i+1===cur)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');});
    announce.textContent='Sheet '+cur+' of 10: '+CH[cur-1].t;
  }
  function reveal(target){
    var sheet=target.closest('.sheet');if(sheet)cur=+sheet.dataset.n;
    var d=target.closest('details');if(d)d.open=true;
    paint();
  }
  function save(){if(restoring||printing)return;positions[location.hash]=window.scrollY;try{history.replaceState({y:window.scrollY},'',location.href);}catch(e){}}
  function navigate(target,focus){
    save();var hash='#'+target.id;
    if(location.hash!==hash)history.pushState({y:0},'',hash);
    lastURL=location.href;reveal(target);
    requestAnimationFrame(function(){
      if(target.matches('.sheet')){if(allMode)target.scrollIntoView();else window.scrollTo(0,0);if(focus)target.querySelector('h1').focus({preventScroll:true});}
      else{target.scrollIntoView({block:'start'});if(focus){if(target.matches('details'))target.querySelector('summary').focus({preventScroll:true});else target.focus({preventScroll:true});}}
      save();
    });
  }
  function restore(){
    if(lastURL===location.href)return;
    lastURL=location.href;restoring=true;var target=targetFromHash();reveal(target);
    requestAnimationFrame(function(){
      var y=history.state&&history.state.y;
      if(typeof y==='number')window.scrollTo(0,y);
      else if(positions[location.hash]!==undefined)window.scrollTo(0,positions[location.hash]);
      else if(!target.matches('.sheet')||allMode)target.scrollIntoView();else window.scrollTo(0,0);
      restoring=false;
    });
  }
  function openContents(){opener=document.activeElement;contents.hidden=false;main.inert=true;nav.inert=true;document.querySelector('.skip').inert=true;document.body.style.overflow='hidden';(list.querySelector('[aria-current]')||list.querySelector('a')).focus();}
  function closeContents(){contents.hidden=true;main.inert=false;nav.inert=false;document.querySelector('.skip').inert=false;document.body.style.overflow='';if(opener)opener.focus({preventScroll:true});}
  document.querySelectorAll('.open-contents').forEach(function(b){b.addEventListener('click',openContents);});
  document.getElementById('contents-close').addEventListener('click',closeContents);
  document.addEventListener('click',function(e){
    if(e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
    var a=e.target.closest('a[href^="#"]');if(!a)return;var target=document.getElementById(a.hash.slice(1));if(!target)return;
    e.preventDefault();if(!contents.hidden)closeContents();navigate(target,true);
  });
  back.addEventListener('click',function(){navigate(sheets[Math.max(0,cur-2)],true);});
  next.addEventListener('click',function(){navigate(sheets[cur===10?0:cur],true);});
  all.addEventListener('click',function(){allMode=!allMode;root.classList.toggle('read-all',allMode);all.setAttribute('aria-pressed',String(allMode));all.textContent=allMode?'Read one sheet':'Read all sheets';sheets[cur-1].scrollIntoView();save();});
  expand.addEventListener('click',function(){var on=expand.getAttribute('aria-pressed')!=='true';document.querySelectorAll('details').forEach(function(d){d.open=on;});expand.setAttribute('aria-pressed',String(on));expand.textContent=on?'Collapse ledgers':'Expand ledgers';});
  document.addEventListener('keydown',function(e){
    if(!contents.hidden){
      if(e.key==='Escape'){e.preventDefault();closeContents();return;}
      if(e.key==='Tab'){var f=Array.from(contents.querySelectorAll('button,a')),first=f[0],last=f[f.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}
      return;
    }
    if(e.altKey||e.ctrlKey||e.metaKey||e.target.closest('input,textarea,select,[contenteditable],summary,.ledger-wrap'))return;
    if(nav.contains(e.target)&&(e.key==='c'||e.key==='C')){e.preventDefault();openContents();return;}
    if(e.target.closest('button,a'))return;
    var n=null;if(e.key==='ArrowRight')n=cur===10?1:cur+1;else if(e.key==='ArrowLeft')n=Math.max(1,cur-1);
    if(n!==null){e.preventDefault();navigate(sheets[n-1],true);}
  });
  var tx=null,ty=null;
  document.addEventListener('touchstart',function(e){tx=ty=null;if(!contents.hidden||e.touches.length!==1||e.target.closest('button,a,summary,input,textarea,select,[contenteditable],.ledger-wrap,.nav'))return;tx=e.touches[0].clientX;ty=e.touches[0].clientY;},{passive:true});
  document.addEventListener('touchend',function(e){if(tx===null)return;var dx=e.changedTouches[0].clientX-tx,dy=e.changedTouches[0].clientY-ty;tx=ty=null;if(Math.abs(dx)>70&&Math.abs(dy)<40)navigate(sheets[dx<0?(cur===10?0:cur):Math.max(0,cur-2)],true);},{passive:true});
  document.addEventListener('touchcancel',function(){tx=ty=null;},{passive:true});
  var closed=[];
  window.addEventListener('beforeprint',function(){printing=true;closed=Array.from(document.querySelectorAll('details:not([open])'));closed.forEach(function(d){d.open=true;});});
  window.addEventListener('afterprint',function(){closed.forEach(function(d){d.open=false;});closed=[];printing=false;});
  window.addEventListener('popstate',restore);window.addEventListener('hashchange',restore);
  var timer;window.addEventListener('scroll',function(){clearTimeout(timer);timer=setTimeout(save,100);},{passive:true});
  function reserveNavigation(){root.style.setProperty('--nav-clearance',nav.getBoundingClientRect().height+'px');}
  if('ResizeObserver' in window)new ResizeObserver(reserveNavigation).observe(nav);
  window.addEventListener('resize',reserveNavigation);
  // Establish a usable active sheet before enabling single-sheet visibility.
  var initial=targetFromHash();reveal(initial);root.classList.add('js');reserveNavigation();lastURL=location.href;
  if('scrollRestoration' in history)history.scrollRestoration='manual';
  requestAnimationFrame(function(){if(history.state&&typeof history.state.y==='number')window.scrollTo(0,history.state.y);else if(!initial.matches('.sheet'))initial.scrollIntoView();else window.scrollTo(0,0);});
})();
