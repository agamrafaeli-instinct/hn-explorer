#!/usr/bin/env python3
"""Refresh the copy that embeds numbers from data/atlas (#510). The weekly snapshot rebuilds the atlas,
and the top-sites table, the home site count and the share descriptions go stale, which fails the
data-consistency tests and skips the deploy. Run after scripts/atlas_aggregates.py. Idempotent.
HN_ROOT: test fixture root (same pattern as scripts/saga_data.py)."""
import json, os, pathlib, re
ROOT = pathlib.Path(os.environ.get('HN_ROOT') or pathlib.Path(__file__).resolve().parent.parent)

def top_rows(c):
    rows = []
    for x in c['entities']['domain']['top'][:10]:
        rows.append('<tr><td><a href="#/explore?domain=%s">%s</a></td><td>%s</td><td>%s</td></tr>'
                    % (x['name'], x['name'], format(x['posts'], ','), format(round(x['points'] / 1000), ',')))
    return ''.join(rows)

def refresh(root=ROOT):
    root = pathlib.Path(root)
    n = format(json.loads((root / 'data/atlas/concentration.json').read_text())['entities']['domain']['count'], ',')
    changed = []
    p = root / 'index.html'; h = p.read_text()
    out, k = re.subn(r'(<caption>Ten sites with the most points</caption><thead>.*?</thead><tbody>).*?(</tbody>)',
                     lambda m: m.group(1) + top_rows(json.loads((root / 'data/atlas/concentration.json').read_text())) + m.group(2), h, count=1, flags=re.S)
    assert k == 1, 'top-sites table not found in index.html'
    out, k = re.subn(r'There are [\d,]+ sites behind the stories', 'There are %s sites behind the stories' % n, out, count=1)
    assert k == 1, 'site count prose not found in index.html'
    if out != h: p.write_text(out); changed.append('index.html')
    pat = re.compile(r'(Every Hacker News story since 2006, asked one question at a time\. )[\d,]+( sites, and the top 1% hold about two thirds of the points\.)')
    for rel in ('router.js', 'scripts/build_share_pages.py'):
        p = root / rel; h = p.read_text()
        out, k = pat.subn(r'\g<1>%s\g<2>' % n, h, count=1)
        assert k == 1, 'home description not found in ' + rel
        if out != h: p.write_text(out); changed.append(rel)
    print('refreshed: ' + (', '.join(changed) if changed else 'already current'))
    return changed

if __name__ == '__main__':
    refresh()
