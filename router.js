'use strict';
// Hash router: one view at a time, so every page is short and phone-first.
(function () {
  const $ = id => document.getElementById(id);
  const AUD = {
    engineers: { name: 'Engineers', tag: 'engineers', clean: [], note: 'Read this first: the all-time cards (h300 onward) copy their thresholds from the older cards, so they are exploratory, not blind pre-registrations.' },
    vcs: { name: 'Deep-tech VCs', tag: 'deep-tech investors', note: 'How to read these: the theme cards (H319 onward) compare the latest 12 months with every earlier story since 2006, matched on title only. A falling share is not proof that adoption fell. Four older cards (H112, H113, H114, H119) stay frozen because they need comments or source domains, which the archive does not hold.' },
    geeks: { name: 'Curious geeks', tag: 'curious readers', note: 'Read this first: these cards are exploratory. The odd-and-fun word lists and thresholds were set while looking at earlier summaries, so they are not blind tests. Scores are a snapshot of a short window. Cards H135-H149 use a fixed snapshot window and do not refresh daily. Refuted cards stay on the page.' }
  };
  const views = ['aud', 'week', 'story', 'hyp', 'explore', 'submit', 'how', 'lesson', 'compare', 'topics', 'today', 'lens', 'rings', 'saga', 'phoenix', 'nf'];
  const tabOf = { nf: '', topics: 'home', today: 'home', lens: '', rings: 'home', phoenix: 'home', saga: 'home', compare: 'home', lesson: 'how', aud: '', week: '', story: '', hyp: '', explore: 'explore', submit: 'submit', how: 'how' };
  document.addEventListener('click', (e) => {
    const j = e.target.closest && e.target.closest('a[data-jump]'); if (!j) return;
    const t = document.getElementById(j.dataset.jump); if (!t) return;
    e.preventDefault(); t.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });
  let shareLoad;
  window.PreparePageShare=()=>shareLoad=shareLoad||new Promise((ok,no)=>{const s=document.createElement('script');s.src='page-share.js';s.onload=ok;s.onerror=()=>{shareLoad=null;no(new Error('Sharing could not load'));};document.head.appendChild(s);});
  document.addEventListener('click',async e=>{
    const b=e.target.closest&&e.target.closest('button[data-share]');if(!b)return;
    if(window.SharePage){window.SharePage(b);return;}
    try{await window.PreparePageShare();window.SharePage(b);}catch(err){b.textContent='Retry sharing';}
  });
  function skel() { const d = document.createElement('div'); d.className = 'skel'; d.setAttribute('aria-label', 'Loading'); $('aud_card').replaceChildren(d); }
  async function single(id, key) {
    $('aud_kicker').textContent = 'Hypothesis card';
    $('aud_back').href = '#/hypotheses';
    skel();
    try { const x = await HypCards.one(id); $('aud_card').replaceChildren(compact(HypCards.render(x.card, x.r))); }
    catch (e) { $('aud_card').textContent = 'Could not load this hypothesis: ' + e.message; }
  }
  const compact = c => HypCards.compact(c);
  async function counts() {
    try {
      const list = (await HypCards.tally()).filter(x => !x.error);
      document.querySelectorAll('.pick em').forEach(e => {
        const t = e.dataset.aud, rows = t === '*' ? list.filter(x => !x.audience) : list.filter(x => x.audience === t);
        e.textContent = rows.length + ' cards';
      });
    } catch (e) { }
  }
  counts();
  let weekLoad;
  function loadWeek(a, wk) {
    weekLoad = weekLoad || new Promise((ok, no) => { const s = document.createElement('script'); s.src = 'weekly.js'; s.onload = ok; s.onerror = () => no(new Error('weekly.js')); document.head.appendChild(s); });
    weekLoad.then(() => window.WeekInit(a, wk)).catch(e => { $('w_body').textContent = 'Could not load this screen: ' + e.message; });
  }
  async function homeWeek() {
    try {
      const jc = window.__jc || (window.__jc = {}), i = await (jc['data/weekly/index.json'] || (jc['data/weekly/index.json'] = fetch('data/weekly/index.json').then(r => r.json()))), w = i.weeks[i.weeks.length - 1], s = new Date(w.start_utc + 'T00:00:00Z'), e = new Date(s); e.setUTCDate(e.getUTCDate() + 6);
      const M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      $('homeweek_s').textContent = M[s.getUTCMonth()] + ' ' + s.getUTCDate() + ' to ' + M[e.getUTCMonth()] + ' ' + e.getUTCDate() + ' \u00b7 ' + w.week;
      $('homeweek').href = '#/w/engineers/' + w.week;
    } catch (x) { }
  }
  homeWeek();
  const BASE_TITLE = document.title, META = document.querySelector('meta[name="description"]'), BASE_DESC = META ? META.content : '';
  window.SetPageMeta = (t, d) => { document.title = t + ' | ' + BASE_TITLE; if (META) META.content = d; };
  const TITLES = {
    home: ['Hacker News, counted', 'Every Hacker News story since 2006, asked one question at a time. 543,588 sites, and the top 1% hold about two thirds of the points.'],
    rings: ['What HN rewarded, year by year', '12 themes, top sites and story types for each of 21 years of Hacker News.'],
    phoenix: ['Quiet, then back', '285 times a word or site on Hacker News went quiet for a year or more and came back. Only 13 held.'],
    how: ['Method', 'Where the data comes from and how every number on this site is computed.'],
    explore: ['Explorer', 'Search every Hacker News story since 2006 and see where points and attention sit.'],
    submit: ['Submit a hypothesis', 'Propose a hypothesis for the full Hacker News archive to test.'],
    story: ['Where the attention lives', 'How points are spread across every Hacker News story since 2006.'],
    lesson: ['How to read trends', 'Why a fall from a peak is not a return to the past.'],
    compare: ['Compare topics', 'Pick from 52 topics and compare their share of Hacker News story titles over time.'],
    topics: ['Topics', '52 topics, one chart each, across every Hacker News story since 2006.'],
    hypotheses: ['Hypotheses, tested', 'Every card on this site, each checked against the full Hacker News archive. Wrong guesses stay on the page.']
  };
  window.PageTitles=TITLES;
  let cur;
  function sagaBar() {
    const b = $('saga_bar'); if (b.dataset.on) return; b.dataset.on = '1';
    const upd = () => { const m = document.documentElement.scrollHeight - innerHeight; b.style.width = (m > 0 ? Math.min(100, scrollY / m * 100) : 0) + '%'; };
    document.querySelector('.sg_more').addEventListener('click', e => { e.preventDefault(); location.hash='#/saga?beat=sg2'; });
    addEventListener('scroll', upd, { passive: true }); addEventListener('resize', upd); upd();
  }
  function route() {
    const p = (location.hash || '#/').replace(/^#\/?/, '').split('?')[0].split('/');
    let v = 'saga';
    if (p[0] === 'a' && AUD[p[1]]) { location.replace('#/hypotheses'); return; } else if (p[0] === 'c' && /^h\d+$/.test(p[1] || '')) v = 'aud'; else if (p[0] === 'w' && AUD[p[1]]) v = 'week'; else if (p[0] === 's' && /^\d{4}-\d{2}-\d{2}$/.test(p[1] || '')) v = 'today'; else if (p[0] === 'l' && p[1]) v = 'lens'; else if (p[0] === 'hypotheses') v = 'hyp'; else if (['story', 'explore', 'submit', 'how', 'lesson', 'compare', 'topics'].includes(p[0])) v = p[0]; else if (p[0] === 't') v = 'compare'; else if (p[0] === 'rings') v = 'rings'; else if (p[0] === 'phoenix') v = 'phoenix'; else if (p[0] === 'hypotheses') v = 'hyp';
    if (v === 'saga' && p[0] !== '' && p[0] !== 'saga') v = 'nf';
    if (v !== 'week') { document.title = BASE_TITLE; if (META) META.content = BASE_DESC; }
    const tk = v === 'hyp' ? 'hypotheses' : v; if (v === 'compare' && !/^#\/compare/.test(location.hash)) { /* topic pages keep their own title */ } else if (TITLES[tk]) window.SetPageMeta(TITLES[tk][0], TITLES[tk][1]);
    views.forEach(n => $('v_' + n).hidden = n !== v);
    document.querySelectorAll('#tabs a').forEach(a => a.classList.toggle('on', a.dataset.t === tabOf[v]));
    if (v === 'hyp') HypCards.initList();
    if (v === 'saga') { sagaBar(); const go = () => window.SagaInit(); if (window.SagaInit) go(); else { const sc = document.createElement('script'); sc.src = 'saga.js'; sc.onload = go; document.head.appendChild(sc); } }
    if (v === 'compare') window.CompareInit && window.CompareInit();
    if (v === 'rings') { const go = () => window.RingsInit(); if (window.RingsInit) go(); else { const sc = document.createElement('script'); sc.src = 'rings.js'; sc.onload = go; document.head.appendChild(sc); } }
    if (v === 'how') window.HowInit && window.HowInit();
    if (v === 'lens') {
      const go = () => window.LensInit(p[1], p[2]);
      if (window.LensInit) go(); else { const sc = document.createElement('script'); sc.src = 'lens.js'; sc.onload = go; document.head.appendChild(sc); }
    }
    if (v === 'today') window.TodayInit && window.TodayInit(p[1]);
    if (v === 'topics') window.TopicsInit && window.TopicsInit();
    if(v==='lesson'){const go=()=>window.LessonInit();if(window.LessonInit)go();else{const s=document.createElement('script');s.src='lesson.js';s.onload=go;document.head.appendChild(s);}}
    if (v === 'story' || v === 'explore') window.StoryInit && window.StoryInit();
    if (v === 'explore') { const hg = () => window.HistInit(); if (window.HistInit) hg(); else { const sc = document.createElement('script'); sc.src = 'history.js'; sc.onload = hg; document.head.appendChild(sc); } window.ExploreInit && window.ExploreInit().then(() => window.ExploreLink && window.ExploreLink()); window.ExploreVendor && window.ExploreVendor(); }
    if (v === 'week') loadWeek(p[1], p[2]);
    if (v === 'aud') single(p[1], p[2]);
    if (cur !== v || v === 'aud') scrollTo({ top: 0, behavior: 'instant' });
    cur = v;
    document.body.dataset.view = v;
    setTimeout(() => { dispatchEvent(new Event('resize')); dispatchEvent(new Event('scroll')); }, 60);
  }
  addEventListener('hashchange', route); route();
})();
