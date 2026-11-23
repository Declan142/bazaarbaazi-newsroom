"""Tests for results.py. Run: python3 -m unittest -v test_results"""

import copy
import datetime
import unittest

import results

TEAMS = [f"Club {c}" for c in "ABCDEFGHIJKLMNOPQRST"]
AS_OF = datetime.date(2026, 11, 24)


def rec(home, away, hg, ag, rnd, date="2026-09-01", source="base"):
    return {"home": f"Club {home}", "away": f"Club {away}", "home_goals": hg,
            "away_goals": ag, "date": date, "round": rnd, "source": source}


def A(home, away, hg, ag, rnd, **kw):
    kw.setdefault("source", "open-a")
    return rec(home, away, hg, ag, rnd, **kw)


def B(home, away, hg, ag, rnd, **kw):
    kw.setdefault("source", "open-b")
    return rec(home, away, hg, ag, rnd, **kw)


BASE = [rec("A", "B", 2, 1, 1, source="base-1"),
        rec("C", "D", 0, 0, 1, source="base-1")]


def combine(baseline, a, b, **kw):
    kw.setdefault("as_of", AS_OF)
    return results.combine_results(TEAMS, baseline, a, b, **kw)


def held_reasons(result):
    return {(h["home"], h["away"]): h["reason"] for h in result.held}


def kinds(result):
    return sorted(c["kind"] for c in result.conflicts)


class Base(unittest.TestCase):
    def assert_preserved(self, result, baseline=BASE):
        """The current summary (baseline) must always survive unchanged."""
        for r in baseline:
            self.assertIn(r, result.accepted)
        self.assertEqual(
            [r for r in result.accepted if r not in result.added],
            sorted(baseline, key=lambda r: (r["round"], r["date"], r["home"], r["away"])),
        )


class AdditionTests(Base):
    def test_both_sources_confirm_adds_with_audit_ids(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2)], [B("E", "F", 1, 0, 2)])
        self.assertEqual(r.added, ({
            "home": "Club E", "away": "Club F", "home_goals": 1, "away_goals": 0,
            "date": "2026-09-01", "round": 2, "source": "open-a+open-b",
            "confirmed_by": ("open-a", "open-b")},))
        self.assertEqual(len(r.accepted), 3)
        self.assertIn(r.added[0], r.accepted)
        self.assertEqual((r.held, r.conflicts, r.rejected), ((), (), ()))
        self.assert_preserved(r)

    def test_later_gap_is_caught_up(self):
        # rounds 2-4 are missing everywhere; round 5 is still confirmed
        r = combine(BASE, [A("E", "F", 3, 3, 5)], [B("E", "F", 3, 3, 5)])
        self.assertEqual([x["round"] for x in r.added], [5])

    def test_single_source_not_added(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2)], [])
        self.assertEqual(r.added, ())
        self.assertEqual(held_reasons(r), {("Club E", "Club F"): "single_source"})
        self.assertEqual(r.conflicts, ())
        self.assert_preserved(r)

    def test_future_fixture_not_promoted_but_today_is(self):
        fut = "2026-11-25"
        r = combine(BASE, [A("E", "F", 1, 0, 2, date=fut)], [B("E", "F", 1, 0, 2, date=fut)])
        self.assertEqual(r.added, ())
        self.assertEqual(held_reasons(r), {("Club E", "Club F"): "future_fixture"})
        today = "2026-11-24"
        r = combine(BASE, [A("E", "F", 1, 0, 2, date=today)], [B("E", "F", 1, 0, 2, date=today)])
        self.assertEqual(len(r.added), 1)

    def test_sources_must_be_independent(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2, source="x")], [B("E", "F", 1, 0, 2, source="x")])
        self.assertEqual(r.added, ())
        self.assertEqual(held_reasons(r), {("Club E", "Club F"): "sources_not_independent"})

    def test_identical_duplicate_rows_collapse(self):
        a = [A("E", "F", 1, 0, 2, source="a1"), A("E", "F", 1, 0, 2, source="a2")]
        r = combine(BASE, a, [B("E", "F", 1, 0, 2)])
        self.assertEqual(len(r.added), 1)
        self.assertEqual(r.added[0]["confirmed_by"], ("a1", "a2", "open-b"))
        self.assertEqual(r.conflicts, ())

    def test_rows_equal_to_baseline_are_quiet(self):
        same = [rec("A", "B", 2, 1, 1, source="open-a")]
        r = combine(BASE, same, [dict(same[0], source="open-b")])
        self.assertEqual((r.added, r.held, r.conflicts, r.rejected), ((), (), (), ()))
        self.assert_preserved(r)


class ConflictTests(Base):
    def test_conflicting_scores_not_added_and_logged(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2)], [B("E", "F", 2, 0, 2)])
        self.assertEqual(r.added, ())
        self.assertEqual(kinds(r), ["score_conflict"])
        reports = r.conflicts[0]["reports"]
        self.assertEqual([(x["source"], x["home_goals"]) for x in reports],
                         [("open-a", 1), ("open-b", 2)])
        self.assertEqual(held_reasons(r), {("Club E", "Club F"): "score_conflict"})
        self.assert_preserved(r)

    def test_rearranged_date_between_feeds_is_held(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2, date="2026-09-01")],
                    [B("E", "F", 1, 0, 2, date="2026-09-02")])
        self.assertEqual(r.added, ())
        self.assertEqual(kinds(r), ["date_or_round_mismatch"])

    def test_rearranged_date_never_changes_baseline(self):
        moved = [rec("A", "B", 2, 1, 1, date="2026-10-10", source="open-a")]
        r = combine(BASE, moved, [dict(moved[0], source="open-b")])
        self.assertEqual(kinds(r), ["date_or_round_mismatch"])
        self.assert_preserved(r)

    def test_correction_of_accepted_score_needs_manual_confirmation(self):
        fix = [A("A", "B", 3, 1, 1)]
        r = combine(BASE, fix, [B("A", "B", 3, 1, 1)])
        self.assertEqual(kinds(r), ["correction_pending"])
        self.assertEqual(r.conflicts[0]["baseline"], BASE[0])
        self.assert_preserved(r)
        self.assertEqual(results.build_table(TEAMS, r.accepted),
                         results.build_table(TEAMS, BASE))

    def test_one_provider_regression_does_not_overwrite(self):
        r = combine(BASE, [A("A", "B", 0, 0, 1)], [])
        self.assertEqual(kinds(r), ["baseline_score_conflict"])
        self.assert_preserved(r)

    def test_feeds_disagreeing_with_each_other_and_baseline(self):
        r = combine(BASE, [A("A", "B", 3, 1, 1)], [B("A", "B", 4, 1, 1)])
        self.assertEqual(kinds(r), ["baseline_score_conflict"])
        self.assert_preserved(r)

    def test_conflicting_duplicates_are_not_last_wins(self):
        a = [A("E", "F", 1, 0, 2), A("E", "F", 2, 0, 2, source="open-a-late")]
        b = [B("E", "F", 2, 0, 2)]
        for rows in (a, list(reversed(a))):
            r = combine(BASE, rows, b)
            self.assertEqual(r.added, ())
            self.assertEqual(kinds(r), ["duplicate_conflict"])
            self.assertEqual(held_reasons(r), {("Club E", "Club F"): "unreliable_source_data"})

    def test_match_played_twice_is_not_accepted(self):
        a = [A("E", "F", 1, 0, 2), A("E", "F", 1, 0, 7)]
        r = combine(BASE, a, [B("E", "F", 1, 0, 2)])
        self.assertEqual(r.added, ())
        self.assertEqual(kinds(r), ["duplicate_conflict"])

    def test_team_twice_in_a_round_is_held_not_picked(self):
        a = [A("E", "F", 1, 0, 2), A("E", "G", 1, 0, 2)]
        b = [B("E", "F", 1, 0, 2), B("E", "G", 1, 0, 2)]
        r = combine(BASE, a, b)
        self.assertEqual(r.added, ())
        self.assertEqual(kinds(r), ["round_clash", "round_clash"])
        self.assertEqual(set(held_reasons(r).values()), {"round_clash"})

    def test_round_clash_with_baseline(self):
        r = combine(BASE, [A("A", "E", 1, 0, 1)], [B("A", "E", 1, 0, 1)])
        self.assertEqual(r.added, ())
        self.assertEqual(kinds(r), ["round_clash"])
        self.assert_preserved(r)

    def test_aliases_are_not_different_teams(self):
        aliases = {"Club A FC": "Club A"}
        a = [dict(A("A", "E", 1, 0, 2), home="Club A FC")]
        b = [B("A", "E", 1, 0, 2)]
        r = combine(BASE, a, b, aliases=aliases)
        self.assertEqual(len(r.added), 1)
        self.assertEqual(r.added[0]["home"], "Club A")
        self.assertEqual(r.conflicts, ())
        # a genuine score disagreement is reported under the canonical name
        r = combine(BASE, a, [B("A", "E", 2, 0, 2)], aliases=aliases)
        self.assertEqual([(c["home"], c["away"]) for c in r.conflicts],
                         [("Club A", "Club E")])

    def test_unknown_alias_is_rejected_not_a_disagreement(self):
        a = [dict(A("A", "E", 1, 0, 2), home="Club A FC")]
        r = combine(BASE, a, [B("A", "E", 1, 0, 2)])
        self.assertEqual(len(r.rejected), 1)
        self.assertEqual(r.conflicts, ())
        self.assertEqual(r.added, ())


class InvalidInputTests(Base):
    def test_malformed_records_are_rejected(self):
        good = A("E", "F", 1, 0, 2)
        cases = {
            "bool goals": {"home_goals": True},
            "bool away goals": {"away_goals": False},
            "float goals": {"home_goals": 1.0},
            "string goals": {"home_goals": "1"},
            "negative goals": {"away_goals": -1},
            "self fixture": {"away": "Club E"},
            "unknown team": {"home": "Club Z"},
            "non-string team": {"home": ["Club E"]},
            "bad date": {"date": "2026-13-01"},
            "compact date": {"date": "20260901"},
            "datetime string": {"date": "2026-09-01T12:00:00"},
            "date object": {"date": datetime.date(2026, 9, 1)},
            "bool round": {"round": True},
            "round zero": {"round": 0},
            "round 39": {"round": 39},
            "float round": {"round": 2.0},
            "empty source": {"source": ""},
            "non-string source": {"source": 7},
        }
        for name, change in cases.items():
            with self.subTest(name):
                r = combine(BASE, [dict(good, **change)], [])
                self.assertEqual(len(r.rejected), 1)
                self.assertEqual((r.added, r.conflicts), ((), ()))
                self.assert_preserved(r)

    def test_missing_fields_and_non_mappings_are_rejected(self):
        good = A("E", "F", 1, 0, 2)
        bad = [{k: v for k, v in good.items() if k != f} for f in good]
        bad += ["garbage", 5, None, ["Club E", "Club F"]]
        for item in bad:
            with self.subTest(repr(item)):
                r = combine(BASE, [item], [])
                self.assertEqual(len(r.rejected), 1)
                self.assert_preserved(r)

    def test_bad_row_cannot_be_papered_over_by_other_feed(self):
        bad = dict(A("E", "F", 1, 0, 2), home_goals=True)
        r = combine(BASE, [bad], [B("E", "F", 1, 0, 2)])
        self.assertEqual(len(r.rejected), 1)
        self.assertEqual(r.added, ())
        self.assertEqual(held_reasons(r), {("Club E", "Club F"): "unreliable_source_data"})

    def test_valid_rows_survive_beside_rejected_ones(self):
        a = ["junk", A("E", "F", 1, 0, 2)]
        r = combine(BASE, a, [B("E", "F", 1, 0, 2)])
        self.assertEqual(len(r.added), 1)
        self.assertEqual(len(r.rejected), 1)

    def test_corrupt_or_missing_source_preserves_baseline(self):
        good = [A("E", "F", 1, 0, 2)]
        for broken in (None, "garbage", 42, {"a": 1}):
            with self.subTest(repr(broken)):
                r = combine(BASE, good, broken)
                self.assertEqual(r.added, ())
                self.assertEqual(len(r.accepted), len(BASE))
                self.assertTrue(r.source_status["feed_b"].startswith("unusable"))
                self.assertEqual(r.source_status["feed_a"], "ok")
                self.assertEqual(held_reasons(r), {("Club E", "Club F"): "source_failure"})
                self.assert_preserved(r)
        r = combine(BASE, None, None)
        self.assertEqual(r.added, ())
        self.assert_preserved(r)

    def test_empty_feeds_are_omission_not_failure(self):
        r = combine(BASE, [], [])
        self.assertEqual(r.source_status, {"feed_a": "ok", "feed_b": "ok"})
        self.assert_preserved(r)

    def test_invalid_baseline_raises(self):
        bad_baselines = [
            None,
            [dict(BASE[0], home_goals=True)],
            [BASE[0], dict(BASE[0], home_goals=9)],           # duplicate fixture
            [rec("A", "B", 1, 0, 1), rec("A", "C", 1, 0, 1)],  # A twice in round 1
        ]
        for baseline in bad_baselines:
            with self.subTest(repr(baseline)):
                with self.assertRaises(ValueError):
                    combine(baseline, [], [])

    def test_bad_arguments_raise(self):
        with self.assertRaises(ValueError):
            results.combine_results(TEAMS[:19], BASE, [], [], as_of=AS_OF)
        with self.assertRaises(ValueError):
            results.combine_results(TEAMS, BASE, [], [], as_of=datetime.datetime(2026, 11, 24))
        with self.assertRaises(ValueError):
            combine(BASE, [], [], aliases={"Club A": "Club B"})
        with self.assertRaises(ValueError):
            combine(BASE, [], [], aliases={"Nope": "Club Z"})


class ReproducibilityTests(Base):
    def scenario(self):
        a = [A("E", "F", 1, 0, 2), A("G", "H", 2, 2, 2), A("I", "J", 0, 1, 3),
             A("K", "L", 1, 1, 3), A("A", "B", 5, 5, 1), "junk"]
        b = [B("E", "F", 1, 0, 2), B("G", "H", 2, 3, 2), B("K", "L", 1, 1, 3),
             B("M", "N", 4, 0, 4)]
        return a, b

    def test_feed_and_row_order_do_not_matter(self):
        a, b = self.scenario()
        first = combine(BASE, a, b)
        second = combine(list(reversed(BASE)), list(reversed(b)), list(reversed(a)))
        for name in ("accepted", "added", "held", "conflicts"):
            self.assertEqual(getattr(first, name), getattr(second, name), name)
        third = combine(BASE, list(reversed(a)), list(reversed(b)))
        self.assertEqual(first, third)

    def test_inputs_are_not_mutated(self):
        a, b = self.scenario()
        snapshot = copy.deepcopy((BASE, a, b))
        combine(BASE, a, b)
        self.assertEqual((BASE, a, b), snapshot)

    def test_scenario_outcomes(self):
        a, b = self.scenario()
        r = combine(BASE, a, b)
        self.assertEqual([(x["home"], x["round"]) for x in r.added],
                         [("Club E", 2), ("Club K", 3)])
        self.assertEqual(held_reasons(r), {
            ("Club G", "Club H"): "score_conflict",
            ("Club I", "Club J"): "single_source",
            ("Club M", "Club N"): "single_source",
        })
        self.assertEqual(kinds(r), ["baseline_score_conflict", "score_conflict"])
        self.assertEqual(len(r.rejected), 1)
        self.assert_preserved_with_added(r)

    def assert_preserved_with_added(self, r):
        for x in BASE:
            self.assertIn(x, r.accepted)


class CurrentSummaryTests(Base):
    def test_summary_preserved_in_every_failure_scenario(self):
        before = results.build_table(TEAMS, BASE)
        good = [A("A", "B", 3, 1, 1)]
        scenarios = [
            ([], []),
            (None, None),
            (good, None),
            (good, "garbage"),
            (good, [B("A", "B", 3, 1, 1)]),          # correction needs a human
            (good, [B("A", "B", 4, 1, 1)]),
            ([A("A", "B", 0, 0, 1)], []),            # regression
            ([A("E", "F", 1, 0, 2)], [B("E", "F", 2, 0, 2)]),
            ([A("E", "F", 1, 0, 2)], []),
            (["junk"], [dict(B("E", "F", 1, 0, 2), away="Club E")]),
            ([A("E", "F", 1, 0, 9, date="2027-01-01")], [B("E", "F", 1, 0, 9, date="2027-01-01")]),
        ]
        for i, (a, b) in enumerate(scenarios):
            with self.subTest(i):
                r = combine(BASE, a, b)
                self.assert_preserved(r)
                self.assertEqual(r.added, ())
                self.assertEqual(results.build_table(TEAMS, r.accepted), before)

    def test_confirmed_addition_only_adds_to_baseline_summary(self):
        r = combine(BASE, [A("E", "F", 1, 0, 2)], [B("E", "F", 1, 0, 2)])
        before = {row["team"]: row for row in results.build_table(TEAMS, BASE)}
        after = {row["team"]: row for row in results.build_table(TEAMS, r.accepted)}
        for team in TEAMS:
            if team not in ("Club E", "Club F"):
                self.assertEqual(before[team], dict(after[team], rank=before[team]["rank"]))
        self.assertEqual(after["Club E"]["Pts"], 3)


class TableTests(unittest.TestCase):
    def test_empty_table_has_all_teams_sharing_rank_one_in_alphabetical_order(self):
        t = results.build_table(TEAMS, [])
        self.assertEqual([r["team"] for r in t], sorted(TEAMS))
        self.assertEqual({r["rank"] for r in t}, {1})

    def test_columns_and_values(self):
        fixtures = [rec("A", "B", 2, 1, 1), rec("B", "C", 0, 0, 2)]
        t = {r["team"]: r for r in results.build_table(TEAMS, fixtures)}
        self.assertEqual(list(t["Club A"]), ["rank", "team", "P", "W", "D", "L",
                                             "GF", "GA", "GD", "Pts"])
        self.assertEqual(t["Club A"], {"rank": 1, "team": "Club A", "P": 1, "W": 1, "D": 0,
                                       "L": 0, "GF": 2, "GA": 1, "GD": 1, "Pts": 3})
        self.assertEqual(t["Club B"], {"rank": 3, "team": "Club B", "P": 2, "W": 0, "D": 1,
                                       "L": 1, "GF": 1, "GA": 2, "GD": -1, "Pts": 1})
        self.assertEqual(t["Club C"], {"rank": 2, "team": "Club C", "P": 1, "W": 0, "D": 1,
                                       "L": 0, "GF": 0, "GA": 0, "GD": 0, "Pts": 1})
        self.assertEqual(t["Club T"]["rank"], 4)

    def test_equal_pts_gd_gf_share_rank_and_display_alphabetically(self):
        fixtures = [rec("C", "D", 1, 0, 1), rec("A", "B", 1, 0, 1)]
        t = results.build_table(TEAMS, fixtures)
        self.assertEqual([r["team"][-1] for r in t[:2]], ["A", "C"])
        self.assertEqual([r["team"][-1] for r in t[-2:]], ["B", "D"])
        self.assertEqual([r["rank"] for r in t], [1, 1] + [3] * 16 + [19, 19])

    def test_goals_scored_breaks_level_pts_and_gd(self):
        fixtures = [rec("A", "B", 1, 1, 1), rec("C", "D", 2, 2, 1)]
        t = results.build_table(TEAMS, fixtures)
        self.assertEqual([r["team"][-1] for r in t][:4], ["C", "D", "A", "B"])
        self.assertEqual([r["rank"] for r in t][:5], [1, 1, 3, 3, 5])

    def test_table_independent_of_fixture_order(self):
        fixtures = [rec("A", "B", 2, 1, 1), rec("B", "C", 0, 0, 2), rec("C", "A", 1, 3, 3)]
        self.assertEqual(results.build_table(TEAMS, fixtures),
                         results.build_table(TEAMS, list(reversed(fixtures))))

    def test_table_rejects_bad_fixtures(self):
        for bad in (
            [rec("A", "B", 1, 0, 1), rec("A", "B", 2, 0, 2)],
            [rec("A", "B", 1, 0, 1), rec("A", "C", 1, 0, 1)],
            [dict(rec("A", "B", 1, 0, 1), home_goals=True)],
            [rec("A", "A", 1, 0, 1)],
            "not a list",
        ):
            with self.subTest(repr(bad)):
                with self.assertRaises(ValueError):
                    results.build_table(TEAMS, bad)


if __name__ == "__main__":
    unittest.main()
