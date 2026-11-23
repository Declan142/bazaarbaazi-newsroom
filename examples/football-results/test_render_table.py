import json
import unittest

from refresh import ROOT
from render_table import render


class PublicTableTests(unittest.TestCase):
    def test_readable_table_contains_every_accepted_stat_and_latest_source(self):
        data = json.loads((ROOT / 'snapshot.json').read_text())
        content = render(data)
        rows = [line for line in content.splitlines() if line.startswith('| ')][2:]
        self.assertEqual(len(rows), 20)
        for line, club in zip(rows, data['table'], strict=True):
            values = [x.strip() for x in line.strip('|').split('|')]
            self.assertEqual(values[1], club['team'])
            self.assertEqual([int(values[i]) for i in (0, 2, 3, 4, 5, 6, 7, 8, 9)],
                             [club[field] for field in ('rank', 'P', 'W', 'D', 'L', 'GF', 'GA', 'GD', 'Pts')])
        for match in data['results']:
            if match['date'] == data['through']:
                self.assertIn(f"{match['home']} {match['home_goals']}-{match['away_goals']} {match['away']}", content)
                self.assertTrue(all(url in content for url in match['references']))
        self.assertIn('ODbL 1.0', content)
        self.assertIn('snapshot.json', content)
        self.assertIn('## Source notes', content)
        self.assertIn('2-2 draw', content)
        self.assertEqual(render(data), content)
