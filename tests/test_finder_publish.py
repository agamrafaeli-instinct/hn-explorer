import json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import finder_publish as f

E = {'term': 'llm', 'label': 'LLM, RAG and fine-tuning', 'generator': 'cross_window', 'note': '',
     'windows': {w: {'from': '2025-08', 'to': '2026-07', 'n': 100, 'total': 5000, 'share': 0.02} for w in ('latest', 'prior', 'before')},
     'ratios': {'latest_vs_prior': 8.3, 'latest_vs_before': 1.2}}

def setup(d, existing=()):
    os.makedirs(os.path.join(d, 'hypotheses')); os.makedirs(os.path.join(d, 'data/finder'))
    for i in existing: open(os.path.join(d, 'hypotheses', i + '-x.json'), 'w').write('{}')
    json.dump(E, open(os.path.join(d, 'data/finder/2026-10-11.json'), 'w'))

class Publish(unittest.TestCase):
    def run_main(self, d, date='2026-10-11'):
        f.ROOT = d; f.main(date)
        return json.load(open(os.path.join(d, 'data/finder/%s.json' % date)))
    def test_card_id_follows_the_last_card(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d, ['h367', 'h412']); e = self.run_main(d)
            self.assertEqual(e['card_id'], 'h413')
            c = json.load(open(os.path.join(d, 'hypotheses/h413-llm-story.json')))
            self.assertEqual(c['check']['source'], 'data/film_shares.json')
            ops = [(v['when']['op'], v['when']['value'], v['verdict']) for v in c['verdicts'] if v.get('when')]
            self.assertEqual(ops, [('>=', 1.5, 'supported'), ('>=', 1.25, 'supported'), ('<=', 0.8, 'refuted')])
            self.assertIn('not tuned', c['thresholds_note']); self.assertEqual(e['rule']['set_on'], '2026-10-11')
    def test_rerun_keeps_card_and_rule(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); a = self.run_main(d); b = self.run_main(d)
            self.assertEqual(a, b); self.assertEqual(len([x for x in os.listdir(os.path.join(d, 'hypotheses')) if x.startswith('h')]), 1)
            self.assertEqual(len(json.load(open(os.path.join(d, 'data/finder/shown.json')))), 1)
    def test_story_text_names_the_card_and_window(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); e = self.run_main(d); self.assertIn(e['card_id'], e['story']['tracked']); self.assertIn('not a prediction', e['story']['tracked'])
            self.assertEqual(e['story']['rows'][0]['from'], '2025-08')
    def test_new_card_has_explicit_limits(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); e = self.run_main(d)
            with open(os.path.join(d, 'hypotheses', e['card_id'] + '-llm-story.json')) as src:
                c = json.load(src)
            self.assertTrue(any('Title matching' in x for x in c['caveats']))
            self.assertTrue(any('not a prediction' in x for x in c['caveats']))
            import honor_scorecard
            cards = {c['id']: c}
            criteria, _ = honor_scorecard.score_card(c, cards, [], set(), False, {}, d)
            self.assertTrue(criteria['insightful'])
    def test_reuse_preserves_published_bytes_and_original_date(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); original = self.run_main(d)
            card_path = os.path.join(d, 'hypotheses', original['card_id'] + '-llm-story.json')
            dated_path = os.path.join(d, 'data/finder/2026-10-11.json')
            before = {p: open(p, 'rb').read() for p in (card_path, dated_path)}
            json.dump(E, open(os.path.join(d, 'data/finder/2027-02-11.json'), 'w'))
            reused = self.run_main(d, '2027-02-11')
            self.assertEqual(reused['card_id'], original['card_id'])
            self.assertEqual(reused['rule']['set_on'], '2026-10-11')
            self.assertTrue(reused['rule']['reused'])
            self.assertIn('Reuses the existing rule set on 2026-10-11.', reused['story']['tracked'])
            self.assertNotIn('before this text', reused['story']['tracked'])
            self.assertEqual(len(os.listdir(os.path.join(d, 'hypotheses'))), 1)
            for p, data in before.items(): self.assertEqual(open(p, 'rb').read(), data)
            self.assertEqual(reused, self.run_main(d, '2027-02-11'))
    def test_different_rules_do_not_reuse_the_same_comparison(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); original = self.run_main(d)
            card_path = os.path.join(d, 'hypotheses', original['card_id'] + '-llm-story.json')
            c = json.load(open(card_path)); c['verdicts'][1]['when']['value'] = 0.8
            json.dump(c, open(card_path, 'w'))
            before = open(card_path, 'rb').read()
            json.dump(E, open(os.path.join(d, 'data/finder/2027-02-11.json'), 'w'))
            different = self.run_main(d, '2027-02-11')
            self.assertNotEqual(different['card_id'], original['card_id'])
            self.assertNotIn('reused', different['rule'])
            self.assertEqual(open(card_path, 'rb').read(), before)
    def test_missing_rule_date_is_not_invented(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); original = self.run_main(d)
            card_path = os.path.join(d, 'hypotheses', original['card_id'] + '-llm-story.json')
            c = json.load(open(card_path)); c['thresholds_note'] = 'Exploratory.'
            json.dump(c, open(card_path, 'w'))
            json.dump(E, open(os.path.join(d, 'data/finder/2027-02-11.json'), 'w'))
            self.assertNotEqual(self.run_main(d, '2027-02-11')['card_id'], original['card_id'])
    def test_reuse_skips_a_replaced_card(self):
        with tempfile.TemporaryDirectory() as d:
            setup(d); original = self.run_main(d)
            succ = {'schema': 1, 'id': 'h999', 'title': 'Successor', 'replaces': original['card_id']}
            json.dump(succ, open(os.path.join(d, 'hypotheses/h999-successor.json'), 'w'))
            json.dump(E, open(os.path.join(d, 'data/finder/2027-02-11.json'), 'w'))
            again = self.run_main(d, '2027-02-11')
            self.assertNotEqual(again['card_id'], original['card_id'])
            self.assertNotIn('reused', again['rule'])
    def test_no_pick_hides_home_line(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, 'data/finder')); lp = os.path.join(d, 'data/finder/latest.json'); open(lp, 'w').write('{}')
            f.ROOT = d; f.main('2026-10-12'); self.assertFalse(os.path.exists(lp))
if __name__ == '__main__': unittest.main()
