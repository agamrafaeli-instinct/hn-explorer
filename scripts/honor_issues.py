#!/usr/bin/env python3
"""Open one "Upgrade card hNNN: <criteria>" issue per failing card (docs/HONOR_SPEC.md).
Reads data/honor.json. At most 5 new issues a day, the rest are listed. Never fails the run.
plan() is pure and tested; apply() calls the gh CLI."""
import json, os, subprocess, sys, datetime
from pathlib import Path
CAP = 5; LABEL = 'needs-upgrade'; PREFIX = 'Upgrade card '
RULE = {'sharp': 'two named groups, a source path that resolves, numeric supported and refuted rules',
        'interesting': 'an audience tag and a why-care line',
        'fresh': 'verdict or confidence changed within the last 14 logged days',
        'relevant': 'an audience tag and at least 30 matching items in group A',
        'insightful': 'a different comparison group, a numeric rule in the text, and a caveat',
        'novel': 'no older card with the same fields and verdict rules or a near-identical title'}

def title(c):
    return PREFIX + c['id'] + ': ' + ', '.join(c['failing'])

def body(c):
    lines = ['**Why.** The scorecard found failing criteria for ' + c['id'] + ' (' + c['title'] + ').', '',
             '**What.** Write a new card with a new ID that passes these criteria. The old card, its thresholds and its verdict stay unchanged.', '',
             '**Failing criteria.**']
    for k in c['failing']:
        extra = ' (group A count: %s)' % c['group_a_count'] if k == 'relevant' else ''
        lines.append('- ' + k + ': needs ' + RULE[k] + extra)
    lines += ['', '**Estimate.** M', '**Depends on.** None', '', '**Acceptance criteria.**',
              '- [ ] A new card replaces or extends ' + c['id'] + ' and passes all scored criteria in data/honor.json',
              '- [ ] ' + c['id'] + ' is left as it is', '',
              '**Sources.** docs/HONOR_SPEC.md, data/honor.json', '', 'Part of #133.']
    return '\n'.join(lines)

def plan(honor, open_issues, created_today, cap=CAP):
    """open_issues: list of {number, title}. Returns dict with create, update, close, deferred."""
    failing = {c['id']: c for c in honor['cards'] if c['failing']}
    by_card = {}
    for i in open_issues:
        if i['title'].startswith(PREFIX):
            by_card.setdefault(i['title'][len(PREFIX):].split(':')[0], i)
    close = [i for cid, i in by_card.items() if cid not in failing]
    update = [(by_card[cid]['number'], c) for cid, c in failing.items() if cid in by_card and by_card[cid]['title'] != title(c)]
    todo = sorted((c for cid, c in failing.items() if cid not in by_card), key=lambda c: (-len(c['failing']), c['id']))
    room = max(0, cap - created_today)
    return {'create': todo[:room], 'deferred': todo[room:], 'update': update, 'close': close}

def gh(*a, inp=None):
    r = subprocess.run(['gh'] + list(a), input=inp, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(' '.join(a[:3]) + ': ' + r.stderr.strip()[:200])
    return r.stdout.strip()

def apply(root='.', repo=None):
    honor = json.loads((Path(root) / 'data/honor.json').read_text())
    rep = ['-R', repo] if repo else []
    try:
        gh('label', 'create', LABEL, '--color', 'FBCA04', '--description', 'Card needs a better version', *rep)
    except RuntimeError:
        pass
    issues = json.loads(gh('issue', 'list', '--label', LABEL, '--state', 'all', '--limit', '300', '--json', 'number,title,state,createdAt', *rep))
    today = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d')
    made = sum(1 for i in issues if i['createdAt'].startswith(today))
    p = plan(honor, [i for i in issues if i['state'] == 'OPEN'], made)
    for c in p['create']:
        print('opened', gh('issue', 'create', '--title', title(c), '--label', LABEL, '--body-file', '-', *rep, inp=body(c)))
    for n, c in p['update']:
        gh('issue', 'edit', str(n), '--title', title(c), '--body-file', '-', *rep, inp=body(c)); print('updated #%s' % n)
    for i in p['close']:
        gh('issue', 'comment', str(i['number']), '--body', 'The card now passes every scored criterion. Closing.', *rep)
        gh('issue', 'close', str(i['number']), '--reason', 'completed', *rep); print('closed #%s' % i['number'])
    if p['deferred']:
        print('deferred (daily cap %d): %s' % (CAP, ', '.join(c['id'] for c in p['deferred'])))
    return p

if __name__ == '__main__':
    try:
        apply(repo=os.environ.get('GITHUB_REPOSITORY'))
    except Exception as e:
        print('::warning::honor issues skipped: %s' % e)
