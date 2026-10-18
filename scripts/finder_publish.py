#!/usr/bin/env python3
"""Story finder, step 4 (#181): publish the day's pick. The top story goes live by itself each day (Decision 2026-10-11).
  python3 scripts/finder_publish.py [--date YYYY-MM-DD]
Run after finder_select.py (it wrote data/finder/<date>.json) and, for the pick, finder_dictionary.py term <id>.
Adds the story block (headline, rows, takeaway, limit) built from the evidence numbers only, writes data/finder/latest.json (one line for the
home page) and appends the pick to data/finder/shown.json. A rerun on the same date changes nothing. With no pick, latest.json is removed so the home entry hides.
"""
import glob, json, os, re, sys, tempfile, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

def pct(v): return ('%.3f' if v < 0.001 else '%.2f' if v < 0.01 else '%.1f') % (v * 100) + '%'
def x(v): return ('%.0f' if v >= 10 else '%.1f' if v >= 1 else '%.2f') % v + 'x'
def mo(s): return s
def row(label, w): return {'label': label, 'from': w['from'], 'to': w['to'], 'n': w['n'], 'total': w['total'], 'share': w['share']}

def story(e):
    L, g, W, R = e['label'], e['generator'], e['windows'], e['ratios']
    if g == 'reversal':
        head = '%s: up against all earlier years, down against its peak year' % L
        rows = [row('Latest 12 months', W['latest']), row('Peak year %s' % W['peak']['year'], W['peak']), row('All earlier months', W['prior'])]
        take = 'The answer depends on the base window. Against all earlier months the share is %s. Against the peak year it is %s.' % (x(R['latest_vs_prior']), x(R['latest_vs_peak']))
    elif g == 'cross_window':
        head = '%s: the answer depends on which earlier window you pick' % L
        rows = [row('Latest 12 months', W['latest']), row('All earlier months', W['prior']), row('The 12 months before', W['before'])]
        take = 'Against all earlier months the share is %s. Against the 12 months just before it is %s.' % (x(R['latest_vs_prior']), x(R['latest_vs_before']))
    else:
        head = '%s: the latest month is above every month of the year before' % L
        m, rg = W['month'], W['range_prev_12']
        rows = [row('Latest month', m), {'label': 'Highest month of the year before', 'from': rg['from'], 'to': rg['to'], 'share': rg['max']}]
        take = 'The latest month is %s the highest month of the 12 before it.' % x(R['month_vs_prev_max'])
    opening = '%s matched %s of story titles in the latest window (%s of %s stories).' % (L, pct(rows[0]['share']), format(rows[0].get('n', 0), ','), format(rows[0].get('total', 0), ','))
    limit = 'Title matching only: the word list will miss and mis-match some stories. Archive scores for 2025-26 are low for all stories, so only shares of titles are used.'
    return {'headline': head, 'opening': opening, 'rows': rows, 'takeaway': take, 'limit': limit}

STRONG, WEAK, REFUTE = 1.5, 1.25, 0.8

def next_card_id(root):
    ids = [int(re.match(r'h(\d+)-', os.path.basename(f)).group(1)) for f in glob.glob(os.path.join(root, 'hypotheses', 'h*-*.json'))]
    return 'h%d' % (max(ids + [368]) + 1)

def make_card(e, today, root=None):
    """Reuse an unchanged test or create a card (#505). The rule uses the latest 12 months against all earlier months,
    with fixed thresholds written here, not tuned to the result. The term was picked because of its numbers, so the card tests the term on the
    current data. It is not a prediction."""
    import film
    root = root or ROOT; cid = next_card_id(root); L = e['label']
    slug = re.sub(r'[^a-z0-9]+', '-', e['term'].lower()).strip('-') + '-story'
    expect = ('Share of stories in the latest 12 months divided by the pooled share of all earlier stories since 2006: %gx or more supports (%gx or more is strong); %gx or less refutes. Between is inconclusive. Title matching only.' % (WEAK, STRONG, REFUTE))
    previous_root = film.ROOT
    # Build a candidate outside the published archive; reuse must not write a card.
    with tempfile.TemporaryDirectory() as staging:
        os.makedirs(os.path.join(staging, 'hypotheses'))
        film.ROOT = staging
        try:
            p = film.make_card(cid, slug, e['term'], '%s: a bigger share than before' % L, '%s titles are a bigger share of stories in the latest 12 months than before.' % L, expect, STRONG, WEAK, REFUTE, 'curious readers', author='story-finder')
            with open(p) as src:
                c = json.load(src)
        finally:
            film.ROOT = previous_root
    existing_cards = []
    replaced_ids = set()
    for existing_path in sorted(glob.glob(os.path.join(root, 'hypotheses', 'h*-*.json'))):
        with open(existing_path) as src:
            existing = json.load(src)
        existing_cards.append(existing)
        r = existing.get('replaces')
        replaced_ids.update([r] if isinstance(r, str) else (r or []))
    for existing in existing_cards:
        if existing.get('id') in replaced_ids:
            continue  # A replaced card is frozen history; reuse its successor's rule.
        if (existing.get('author') != 'story-finder' or existing.get('check') != c['check']
                or existing.get('verdicts') != c['verdicts']):
            continue
        date = re.match(r'^Set on (\d{4}-\d{2}-\d{2}) by the story finder,', existing.get('thresholds_note', ''))
        if not date:
            continue  # Do not invent a rule date for an older experiment.
        return existing['id'], {'strong': STRONG, 'weak': WEAK, 'refute': REFUTE, 'set_on': date[1], 'reused': True}
    c['thresholds_note'] = 'Set on %s by the story finder, before the story text was written. These are the standard film-card thresholds, not tuned to this result. The term was picked because its numbers stood out, so this card tests it on the current data and is not a prediction.' % today
    c['caveats'] = [
        'Title matching only: the word list will miss and mis-match some stories.',
        'The term was picked because its numbers stood out. This is an exploratory check on the current data, not a prediction.',
        'HN attention does not measure adoption, technical validation or investment return.'
    ]
    p = os.path.join(root, 'hypotheses', '%s-%s.json' % (cid, slug))
    with open(p, 'w') as dst:
        json.dump(c, dst, indent=2); dst.write('\n')
    return cid, {'strong': STRONG, 'weak': WEAK, 'refute': REFUTE, 'set_on': today}

def main(today):
    d = os.path.join(ROOT, 'data/finder'); p = os.path.join(d, today + '.json'); lp = os.path.join(d, 'latest.json'); sp = os.path.join(d, 'shown.json')
    if not os.path.exists(p):
        if os.path.exists(lp): os.remove(lp)
        print('no pick for', today); return
    e = json.load(open(p))
    if 'story' not in e:
        e['card_id'], e['rule'] = make_card(e, today); e['story'] = story(e); e['date'] = today
        timing = ('Reuses the existing rule set on %s.' % e['rule']['set_on'] if e['rule'].get('reused') else 'Rule set on %s before this text was written.' % e['rule']['set_on'])
        e['story']['tracked'] = 'Tracked as %s. Supported at %gx or more against all earlier months, refuted at %gx or less. %s The term was picked because of its numbers, so this tests it on the current data and is not a prediction.' % (e['card_id'], e['rule']['weak'], e['rule']['refute'], timing)
        dp = 'data/finder/dictionaries/%s.json' % e['term']; e['dictionary'] = dp if os.path.exists(os.path.join(ROOT, dp)) else None
        json.dump(e, open(p, 'w'), indent=1, sort_keys=True)
    json.dump({'date': today, 'term': e['term'], 'headline': e['story']['headline']}, open(lp, 'w'), indent=1, sort_keys=True)
    shown = json.load(open(sp)) if os.path.exists(sp) else []
    if not any(s['term'] == e['term'] and s['date'] == today for s in shown):
        shown.append({'term': e['term'], 'date': today}); json.dump(shown, open(sp, 'w'), indent=1, sort_keys=True)
    print('published', e['term'], today)

if __name__ == '__main__':
    a = sys.argv[1:]; main(a[a.index('--date') + 1] if '--date' in a else dt.date.today().isoformat())
