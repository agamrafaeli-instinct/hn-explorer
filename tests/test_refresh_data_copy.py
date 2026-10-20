import json, pathlib, sys, tempfile, unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import refresh_data_copy as r

TOP = [{'name': 's%d.com' % i, 'posts': 1000 + i, 'points': 50000 - i * 1000} for i in range(10)]
DESC = 'Every Hacker News story since 2006, asked one question at a time. 9,999 sites, and the top 1% hold about two thirds of the points.'

def make_root(d):
    d = pathlib.Path(d)
    (d / 'data/atlas').mkdir(parents=True); (d / 'scripts').mkdir()
    json.dump({'entities': {'domain': {'count': 123456, 'top': TOP}}}, open(d / 'data/atlas/concentration.json', 'w'))
    (d / 'index.html').write_text('<caption>Ten sites with the most points</caption><thead><tr><th>Site</th></tr></thead><tbody>STALE</tbody>'
                                  '<p>There are 9,999 sites behind the stories. The top 1% of them hold about two thirds of all points.</p>')
    (d / 'router.js').write_text("home: ['Hacker News, counted', '%s']" % DESC)
    (d / 'scripts/build_share_pages.py').write_text("'home': ('Hacker News, counted', '%s')," % DESC)
    return d

class RefreshDataCopy(unittest.TestCase):
    def test_rewrites_stale_numbers_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as t:
            d = make_root(t)
            changed = r.refresh(d)
            self.assertEqual(set(changed), {'index.html', 'router.js', 'scripts/build_share_pages.py'})
            h = (d / 'index.html').read_text()
            self.assertIn('There are 123,456 sites behind the stories', h)
            self.assertNotIn('STALE', h)
            self.assertIn('<tr><td><a href="#/explore?domain=s0.com">s0.com</a></td><td>1,000</td><td>50</td></tr>', h)
            self.assertEqual(h.count('<tr><td><a href="#/explore?domain='), 10)
            self.assertIn('123,456 sites', (d / 'router.js').read_text())
            self.assertIn('123,456 sites', (d / 'scripts/build_share_pages.py').read_text())
            self.assertEqual(r.refresh(d), [])

if __name__ == '__main__':
    unittest.main()
