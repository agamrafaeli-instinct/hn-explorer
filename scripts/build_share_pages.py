#!/usr/bin/env python3
"""Build static share pages so a pasted link previews with the right title (docs/SHARING.md)."""
import html, json, pathlib
from html.parser import HTMLParser

SITE = 'Hacker News posts, explored'
SKIP = {'index.json', 'bundle.json', 'tally.json'}

def page(title, desc, target):
    t, d = html.escape(title, quote=True), html.escape(desc, quote=True)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{t}</title><meta name="description" content="{d}">'
            f'<meta property="og:type" content="website"><meta property="og:site_name" content="{SITE}">'
            f'<meta property="og:title" content="{t}"><meta property="og:description" content="{d}">'
            f'<meta name="twitter:card" content="summary"><meta name="twitter:title" content="{t}">'
            f'<meta name="twitter:description" content="{d}">'
            f'<meta http-equiv="refresh" content="0;url={target}"></head>'
            f'<body><p><a href="{target}">{t}</a></p><p>{d}</p>'
            f'<script>location.replace({json.dumps(target)})</script></body></html>\n')

def card_pages(site):
    site = pathlib.Path(site); hd = site / 'hypotheses'; out = site / 'share' / 'c'
    out.mkdir(parents=True, exist_ok=True); n = 0
    for f in sorted(hd.glob('*.json')):
        if f.name in SKIP: continue
        c = json.loads(f.read_text())
        if not (isinstance(c, dict) and c.get('id') and c.get('title')): continue
        desc = c.get('hypothesis') or c['title']
        story_file = site / 'stories' / (c['id'] + '.json')
        title = json.loads(story_file.read_text()).get('question') if story_file.is_file() else None
        title = title or c['title']
        (out / (c['id'] + '.html')).write_text(page(title + ' (Hacker News, tested)', desc, '../../#/c/' + c['id']))
        n += 1
    return n

AUD = {
    'engineers': ('Engineers', 'engineers', "Builder's radar", 'What moved this week among the things people build with.'),
    'vcs': ('Deep-tech VCs', 'deep-tech investors', 'Money and names', 'Which deep tech themes, names and deal words moved this week.'),
    'geeks': ('Curious geeks', 'curious readers', 'Beyond AI', 'What people talked about this week that is not AI.'),
}
MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

def week_range(start, end_ex):
    import datetime as dt
    s = dt.date.fromisoformat(start); e = dt.date.fromisoformat(end_ex) - dt.timedelta(days=1)
    f = lambda d: MON[d.month - 1] + ' ' + str(d.day)
    return f(s) + ' to ' + f(e)

def week_title(a, week, start, end_ex):
    # Same title and description the week screen sets in the browser (weekly.js).
    rg = week_range(start, end_ex); name, _, _, intro = AUD[a]
    return name + ': week ' + week + ' (' + rg + ') | ' + SITE, name + ' view of Hacker News for ' + rg + '. ' + intro

def week_audience_pages(site):
    site = pathlib.Path(site); idx = json.loads((site / 'data/weekly/index.json').read_text())['weeks']; n = 0
    for a in AUD:
        d = site / 'share' / 'w' / a; d.mkdir(parents=True, exist_ok=True)
        for w in idx:
            wk = json.loads((site / 'data/weekly' / w['path']).read_text())
            t, desc = week_title(a, w['week'], w['start_utc'], wk['end_exclusive_utc'])
            (d / (w['week'] + '.html')).write_text(page(t, desc, '../../../#/w/' + a + '/' + w['week'])); n += 1
        last = idx[-1]; wk = json.loads((site / 'data/weekly' / last['path']).read_text())
        t, desc = week_title(a, last['week'], last['start_utc'], wk['end_exclusive_utc'])
        (d / 'current.html').write_text(page(t, desc, '../../../#/w/' + a + '/' + last['week'])); n += 1
    return n

# Story pages that have a route of their own. Titles and descriptions match TITLES in router.js (a test checks it).
ROUTES = {
    'home': ('Hacker News, counted', 'Every Hacker News story since 2006, asked one question at a time. 543,588 sites, and the top 1% hold about two thirds of the points.'),
    'phoenix': ('Quiet, then back', '285 times a word or site on Hacker News went quiet for a year or more and came back. Only 13 held.'),
    'hypotheses': ('Hypotheses, tested', 'Every card on this site, each checked against the full Hacker News archive. Wrong guesses stay on the page.'),
    'compare': ('Compare topics', 'Pick from 52 topics and compare their share of Hacker News story titles over time.'),
    'topics': ('Topics', '52 topics, one chart each, across every Hacker News story since 2006.'),
    'rings': ('What HN rewarded, year by year', '12 themes, top sites and story types for each of 21 years of Hacker News.'),
}

def route_pages(site):
    out = pathlib.Path(site) / 'share' / 'p'; out.mkdir(parents=True, exist_ok=True)
    for r, (t, d) in ROUTES.items():
        (out / (r + '.html')).write_text(page(t + ' (Hacker News)', d, '../../#/' + ('' if r == 'home' else r)))
    return len(ROUTES)

class BeatCopy(HTMLParser):
    def __init__(self):
        super().__init__(); self.beat = None; self.field = None; self.copy = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'section': self.beat = a.get('id') if a.get('id') in ('sg2','sg3','sg4','sg5') else None
        if self.beat and (tag == 'h2' or (tag == 'p' and 'sg_cav' in a.get('class',''))):
            self.field = 'title' if tag == 'h2' else 'desc'; self.copy.setdefault(self.beat, {}).setdefault(self.field, '')
    def handle_data(self, data):
        if self.beat and self.field: self.copy[self.beat][self.field] += data
    def handle_endtag(self, tag):
        if tag in ('h2','p'): self.field = None
        if tag == 'section': self.beat = None

def beat_pages(site):
    site = pathlib.Path(site); parser = BeatCopy(); parser.feed((site / 'index.html').read_text())
    out = site / 'share' / 'p'; out.mkdir(parents=True, exist_ok=True)
    for beat, c in parser.copy.items():
        title = c['title'].strip(); desc = c.get('desc', title).strip()
        (out / ('home-' + beat + '.html')).write_text(page(title + ' (Hacker News)', desc, '../../#/saga?beat=' + beat))
    return len(parser.copy)

if __name__ == '__main__':
    import sys
    site = sys.argv[1] if len(sys.argv) > 1 else '_site'
    print('share pages:', card_pages(site) + week_audience_pages(site) + route_pages(site) + beat_pages(site))
