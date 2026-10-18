#!/usr/bin/env python3
"""Honor scorecard (docs/HONOR_SPEC.md). Reads hypotheses/*.json, the data files they name,
stories/index.json and data/verdicts/log.csv. Writes data/honor.json. Never edits a card.
Criteria: sharp, interesting, fresh, relevant, insightful, novel. Each is True, False or None (n/a)."""
import argparse, csv, json, os, re
from pathlib import Path
CRITERIA = ['sharp', 'interesting', 'fresh', 'relevant', 'insightful', 'novel']
AUDIENCES = {'engineers', 'deep-tech investors', 'curious readers'}
FIXED_SOURCES = {'data/engineers_history.json', 'data/vcs_history.json', 'data/curious_round2.json'}
STOP = {'the', 'a', 'of', 'is', 'in', 'to', 'and', 'on', 'more', 'than', 'are', 'for'}
FRESH_DAYS = 14; MIN_COUNT = 30; DUP_JACCARD = 0.7

def dig(o, path):
    for k in path.split('.'):
        o = o.get(k) if isinstance(o, dict) else None
        if o is None:
            return None
    return o

def pick(ix, n):
    if ix == 'all':
        return list(range(n))
    if isinstance(ix, dict):  # film cards: {"last": N} or {"before_last": N}
        if ix.get('last'): return list(range(max(0, n - ix['last']), n))
        if ix.get('before_last'): return list(range(max(0, n - ix['before_last'])))
        return []
    return [i + n if i < 0 else i for i in ix if 0 <= (i + n if i < 0 else i) < n]

def words(t):
    return set(re.findall(r'[a-z0-9]+', t.lower())) - STOP

def load_cards(root):
    out = {}
    for f in sorted((Path(root) / 'hypotheses').glob('h[0-9][0-9][0-9]-*.json')):
        c = json.loads(f.read_text()); out[c['id']] = c
    return out

def data_rows(root, card, cache):
    src = Path(root) / card['check']['source']
    if not src.is_file():
        return None
    if src not in cache:
        cache[src] = json.loads(src.read_text())
    rows = dig(cache[src], card['check']['path'])
    return rows if isinstance(rows, list) else None

def is_fixed(card):
    n = int(card['id'][1:])
    return card['check']['source'] in FIXED_SOURCES or 135 <= n <= 149

def read_log(root):
    p = Path(root) / 'data/verdicts/log.csv'; by = {}
    if p.is_file():
        with p.open(newline='') as f:
            for r in csv.DictReader(f):
                by.setdefault(r['card_id'], []).append((r['date'], r['verdict'], r['confidence']))
    return {k: sorted(v) for k, v in by.items()}

def score_card(card, cards, rows, story_ids, stories_complete, log, root):
    k = card['check']; ga, gb = k['group_a'], k['group_b']; vs = card['verdicts']; r = {}
    r['sharp'] = bool(ga.get('label') and gb.get('label') and ga.get('indices') and gb.get('indices')
        and rows is not None
        and any(v.get('verdict') == 'supported' and isinstance(v.get('when', {}).get('value'), (int, float)) for v in vs)
        and any(v.get('verdict') == 'refuted' and isinstance(v.get('when', {}).get('value'), (int, float)) for v in vs)
        and vs and vs[-1].get('else'))
    aud = card.get('audience') in AUDIENCES
    if not aud:
        r['interesting'] = False
    elif not stories_complete:
        r['interesting'] = True
    else:
        why = None
        sp = Path(root) / 'stories' / (card['id'] + '.json')
        if card['id'] in story_ids and sp.is_file():
            why = json.loads(sp.read_text()).get('why')
        r['interesting'] = bool(why)
    hist = log.get(card['id'], [])
    days = sorted({d for d, _, _ in hist})
    if is_fixed(card) or len(days) < FRESH_DAYS:
        r['fresh'] = None
    else:
        last = [(v, c) for d, v, c in hist if d in days[-FRESH_DAYS:]]
        stale = len(set(last)) == 1 and last[0][1] == 'strong'
        r['fresh'] = not stale
    n = 0.0
    if rows is not None:
        f = ga.get('field') or k['field']
        if 'points' in f and ga.get('per'):
            f = ga['per']
        for i in pick(ga['indices'], len(rows)):
            n += float(rows[i].get(f, 0) or 0)
    r['relevant'] = aud and n >= MIN_COUNT
    r['insightful'] = (json.dumps(ga, sort_keys=True) != json.dumps(gb, sort_keys=True)
        and bool(re.search(r'\d', card.get('expect', ''))) and len(card.get('caveats', [])) >= 1)
    key = lambda x: json.dumps([x['check']['source'], x['check']['path'], x['check'].get('labels'), x['check']['group_a'].get('field'),
        x['check']['group_a'].get('per'), x['check']['group_a'].get('indices'), x['check']['group_b'].get('field'),
        x['check']['group_b'].get('indices'), x.get('verdicts')], sort_keys=True)
    me = words(card['title']); dup = False
    for oid, o in cards.items():
        if oid >= card['id'] or oid in ([card['replaces']] if isinstance(card.get('replaces'), str) else card.get('replaces', [])):
            continue  # a card is not a duplicate of the card it replaces
        ow = words(o['title'])
        if len(me & ow) / max(1, len(me | ow)) >= DUP_JACCARD or key(o) == key(card):  # same comparison with the same verdict rules
            dup = True; break
    r['novel'] = not dup
    return r, n

def run(root):
    cards = load_cards(root); cache = {}; log = read_log(root)
    sp = Path(root) / 'stories/index.json'
    story_ids = set(json.loads(sp.read_text()).get('ids', [])) if sp.is_file() else set()
    complete = bool(cards) and set(cards) <= story_ids
    out = []
    replaced = {x: cid for cid, c in cards.items() for x in ([c['replaces']] if isinstance(c.get('replaces'), str) else c.get('replaces', []))}
    for cid, c in cards.items():
        r, n = score_card(c, cards, data_rows(root, c, cache), story_ids, complete, log, root)
        scored = [v for v in r.values() if v is not None]
        out.append({'id': cid, 'title': c['title'], 'audience': c.get('audience'),
            'criteria': {k: r[k] for k in CRITERIA}, 'score': round(sum(scored) / len(scored), 3) if scored else None,
            'failing': [] if cid in replaced else [k for k in CRITERIA if r[k] is False], 'group_a_count': round(n, 1), **({'replaced_by': replaced[cid]} if cid in replaced else {})})
    return {'schema': 1, 'spec': 'docs/HONOR_SPEC.md', 'cards': out}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--out', default=None)
    a = ap.parse_args(); res = run(a.root)
    out = Path(a.out or Path(a.root) / 'data/honor.json'); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1, sort_keys=True) + '\n')
    bad = sum(1 for c in res['cards'] if c['failing'])
    print('scored', len(res['cards']), 'cards;', bad, 'need an upgrade')

if __name__ == '__main__':
    main()
