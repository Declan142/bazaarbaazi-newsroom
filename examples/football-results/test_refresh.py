import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import refresh


class PublishedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((refresh.ROOT / 'snapshot.json').read_text())
        self.now = datetime(2027, 6, 15, tzinfo=timezone.utc)

    def observations(self, source):
        # Hypothetical synthetic result. Pick the next unused pairing and matchweek.
        existing = {refresh.key(r) for r in self.base['results']}
        rnd = max(r['round'] for r in self.base['results']) + 1
        if rnd > 38:
            self.skipTest('The published season is complete')
        home, away = next((h, a) for h in self.base['clubs'] for a in self.base['clubs'] if h != a and (h, a) not in existing)
        return {'home': home, 'away': away, 'home_goals': 1, 'away_goals': 0,
                'date': '2027-06-01', 'round': rnd, 'source': source}

    def run_feeds(self, football, liga):
        with patch.object(refresh, 'openfootball_feed', return_value={'revision': 'a'*40, 'finals': football}), \
             patch.object(refresh, 'openliga_feed', return_value={'12': {'changed': '2027-06-01T20:00:00', 'finals': liga}}):
            return refresh.refreshed(self.base, {}, self.now)[0]

    def test_published_data_contains_the_protected_club_verified_score(self):
        refresh.checked_document(self.base)
        row = next(r for r in self.base['results'] if refresh.key(r) == ('AFC Bournemouth', 'Brentford'))
        self.assertEqual((row['home_goals'], row['away_goals']), (2, 2))
        self.assertTrue(any('brentfordfc.com' in url for url in row['references']))

    def test_promotion_adds_only_new_fixture_and_keeps_evidence(self):
        if self.base['through'] > '2027-06-01':
            self.skipTest('Synthetic demonstration date has elapsed')
        new = self.run_feeds([self.observations('openfootball')], [self.observations('openligadb')])
        rows = {refresh.key(row): row for row in new['results']}
        for prior in self.base['results']:
            self.assertEqual(rows[refresh.key(prior)], prior)
        self.assertEqual(len(rows), len(self.base['results']) + 1)
        addition = rows[refresh.key(self.observations('openfootball'))]
        self.assertEqual(len(addition['references']), 2)
        self.assertEqual(new['through'], '2027-06-01')
        self.assertEqual(sum(row['P'] for row in new['table']), len(rows) * 2)

    def test_omission_or_regression_leaves_the_actual_file_byte_for_byte_intact(self):
        old = self.base['results'][0]
        changed = {**old, 'home_goals': old['home_goals'] + 1, 'source': 'openligadb'}
        for a, b in (([], []), ([self.observations('openfootball')], []), ([], [changed]),
                     ([{**changed, 'source': 'openfootball'}], [changed])):
            self.assertIs(self.run_feeds(a, b), self.base)
        before = (refresh.ROOT/'snapshot.json').read_bytes()
        with patch.object(refresh, 'openfootball_feed', side_effect=TimeoutError('test outage')):
            with self.assertRaises(TimeoutError):
                refresh.refreshed(self.base, {}, self.now)
        self.assertEqual((refresh.ROOT/'snapshot.json').read_bytes(), before)

    def test_marks_round_changed_only_after_a_complete_response(self):
        old = {'10': {'changed': '2026-11-01T03:00:00', 'finals': []}}
        calls = []
        def simulated(url):
            calls.append(url)
            if 'getcurrentgroup' in url:
                return {'groupOrderID': 11}
            if 'getlastchangedate' in url:
                return '2026-11-01T03:00:00'
            return []
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            refresh.openliga_feed(copy.deepcopy(old), [], self.now.date(), simulated)
        self.assertNotIn('/getmatchdata/pl/2026/10', ' '.join(calls))
        self.assertEqual(set(old), {'10'})

    def test_malformed_and_unattributed_snapshots_fail_closed(self):
        changed = copy.deepcopy(self.base)
        changed['table'][0]['Pts'] += 1
        with self.assertRaises(ValueError):
            refresh.checked_document(changed)
        changed = copy.deepcopy(self.base)
        changed['results'][0]['references'] = ['https://example.org/a', 'https://example.org/b']
        with self.assertRaises(ValueError):
            refresh.checked_document(changed)

    def test_identical_data_never_rewrites_an_existing_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'snapshot.json'
            self.assertTrue(refresh.write_json(path, self.base))
            self.assertFalse(refresh.write_json(path, self.base))
