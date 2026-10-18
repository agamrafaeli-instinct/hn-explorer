import sys, json, tempfile, unittest, pathlib, copy
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / 'scripts'))
import honor_scorecard as h

CARD = {'schema': 1, 'id': 'h900', 'title': 'Alpha beta gamma', 'audience': 'engineers', 'hypothesis': 'x', 'expect': 'ratio of 2x or more',
        'check': {'source': 'data/s.json', 'path': 'rows', 'field': 'n', 'stat': 'mean_ratio_a_over_b',
                  'group_a': {'label': 'A', 'indices': [0, 1], 'field': 'n'}, 'group_b': {'label': 'B', 'indices': [2], 'field': 'n'}},
        'verdicts': [{'when': {'op': '>=', 'value': 2}, 'verdict': 'supported', 'confidence': 'strong'},
                     {'when': {'op': '<=', 'value': 1}, 'verdict': 'refuted', 'confidence': 'strong'},
                     {'else': True, 'verdict': 'inconclusive', 'confidence': 'inconclusive'}],
        'caveats': ['limit']}

def make(card=None, rows=None, extra=None, log=None, stories=None):
    d = pathlib.Path(tempfile.mkdtemp()); (d / 'hypotheses').mkdir(); (d / 'data').mkdir()
    cards = [card or CARD] + (extra or [])
    for c in cards:
        (d / 'hypotheses' / (c['id'] + '-x.json')).write_text(json.dumps(c))
    (d / 'data/s.json').write_text(json.dumps({'rows': rows if rows is not None else [{'n': 100}, {'n': 100}, {'n': 50}]}))
    if log:
        (d / 'data/verdicts').mkdir(); (d / 'data/verdicts/log.csv').write_text('date,card_id,verdict,confidence\n' + ''.join(f'{a},{b},{c},{e}\n' for a, b, c, e in log))
    if stories is not None:
        (d / 'stories').mkdir(); (d / 'stories/index.json').write_text(json.dumps({'ids': list(stories)}))
        for i, w in stories.items() if isinstance(stories, dict) else []:
            (d / 'stories' / (i + '.json')).write_text(json.dumps({'why': w}))
    return d

def crit(d, cid='h900'):
    return next(c for c in h.run(d)['cards'] if c['id'] == cid)['criteria']

class Replaces(unittest.TestCase):
    def test_new_card_is_not_a_duplicate_of_the_card_it_replaces(self):
        new = copy.deepcopy(CARD); new['id'] = 'h901'; new['replaces'] = 'h900'
        self.assertFalse(crit(make(extra=[new]), 'h901')['novel'] is False)
    def test_still_a_duplicate_of_other_cards(self):
        new = copy.deepcopy(CARD); new['id'] = 'h901'; new['replaces'] = 'h899'
        self.assertFalse(crit(make(extra=[new]), 'h901')['novel'])

class T(unittest.TestCase):
    def test_all_pass(self):
        c = crit(make()); self.assertEqual({k: v for k, v in c.items() if k != 'fresh'}, {k: True for k in h.CRITERIA if k != 'fresh'}); self.assertIsNone(c['fresh'])
    def test_sharp_fails_without_refute_rule(self):
        c = copy.deepcopy(CARD); c['verdicts'] = [c['verdicts'][0], c['verdicts'][2]]; self.assertFalse(crit(make(c))['sharp'])
    def test_sharp_fails_when_path_missing(self):
        c = copy.deepcopy(CARD); c['check']['path'] = 'nope'; self.assertFalse(crit(make(c))['sharp'])
    def test_interesting_needs_audience(self):
        c = copy.deepcopy(CARD); del c['audience']; self.assertFalse(crit(make(c))['interesting'])
    def test_interesting_needs_why_when_stories_complete(self):
        self.assertFalse(crit(make(stories={'h900': ''}))['interesting']); self.assertTrue(crit(make(stories={'h900': 'because'}))['interesting'])
    def test_fresh_stale_and_moving(self):
        days = [f'2026-10-{d:02d}' for d in range(1, 15)]
        self.assertFalse(crit(make(log=[(d, 'h900', 'supported', 'strong') for d in days]))['fresh'])
        mixed = [(d, 'h900', 'supported' if i % 2 else 'refuted', 'strong') for i, d in enumerate(days)]
        self.assertTrue(crit(make(log=mixed))['fresh'])
        self.assertIsNone(crit(make(log=[(d, 'h900', 'supported', 'strong') for d in days[:5]]))['fresh'])
    def test_fresh_na_for_fixed_card(self):
        c = copy.deepcopy(CARD); c['check']['source'] = 'data/curious_round2.json'
        d = make(c); (d / 'data/curious_round2.json').write_text(json.dumps({'rows': [{'n': 100}] * 3}))
        self.assertIsNone(crit(d)['fresh'])
    def test_relevant_needs_count(self):
        self.assertFalse(crit(make(rows=[{'n': 5}, {'n': 5}, {'n': 5}]))['relevant'])
    def test_insightful_needs_number_and_caveat(self):
        c = copy.deepcopy(CARD); c['expect'] = 'goes up'; self.assertFalse(crit(make(c))['insightful'])
        c = copy.deepcopy(CARD); c['caveats'] = []; self.assertFalse(crit(make(c))['insightful'])
    def test_novel_fails_for_newer_duplicate_only(self):
        e = copy.deepcopy(CARD); e['id'] = 'h901'; d = make(extra=[e])
        self.assertTrue(crit(d, 'h900')['novel']); self.assertFalse(crit(d, 'h901')['novel'])
    def test_novel_same_check_different_verdicts_passes(self):
        e = copy.deepcopy(CARD); e['id'] = 'h901'; e['title'] = 'Gamma delta epsilon'
        e['verdicts'] = [{'when': {'op': '>=', 'value': 5}, 'verdict': 'supported', 'confidence': 'strong'},
                         {'when': {'op': '<=', 'value': 0.5}, 'verdict': 'refuted', 'confidence': 'strong'},
                         {'else': True, 'verdict': 'inconclusive', 'confidence': 'inconclusive'}]
        self.assertTrue(crit(make(extra=[e]), 'h901')['novel'])
    def test_novel_fails_for_near_identical_title(self):
        e = copy.deepcopy(CARD); e['id'] = 'h901'; e['check'] = dict(CARD['check'], path='other')
        self.assertFalse(crit(make(extra=[e]), 'h901')['novel'])
    def test_same_input_same_output(self):
        d = make(); self.assertEqual(h.run(d), h.run(d))
    def test_does_not_touch_card_files(self):
        d = make(); before = (d / 'hypotheses/h900-x.json').read_bytes(); h.run(d); self.assertEqual(before, (d / 'hypotheses/h900-x.json').read_bytes())

if __name__ == '__main__':
    unittest.main()
