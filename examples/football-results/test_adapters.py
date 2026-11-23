import copy
import unittest

from adapters import CANON, OPENFOOTBALL_NAMES, OPENLIGA_NAMES, openfootball, openliga


def of_match(**changes):
    match = {"round": "Matchday 1", "date": "2026-08-21", "time": "20:00",
             "team1": "Arsenal FC", "team2": "Coventry City FC",
             "score": {"ht": [2, 0], "ft": [3, 0]}}
    match.update(changes)
    return match


def of_doc(*matches):
    return {"name": "English Premier League 2026/27", "matches": list(matches) or [of_match()]}


def lg_row(**changes):
    row = {"leagueId": 5996, "leagueSeason": 2026, "matchDateTimeUTC": "2026-08-21T19:00:00Z",
           "group": {"groupOrderID": 1, "groupName": "1. Spieltag"}, "matchIsFinished": True,
           "team1": {"teamName": "FC Arsenal", "teamIconUrl": "https://example.invalid/a.png"},
           "team2": {"teamName": "Coventry City", "teamIconUrl": "https://example.invalid/c.png"},
           "matchResults": [
               {"resultTypeKind": "HalfTime", "resultTypeID": 1, "pointsTeam1": 0, "pointsTeam2": 0},
               {"resultTypeKind": "After90Minutes", "resultTypeID": 2,
                "pointsTeam1": 3, "pointsTeam2": 0}]}
    row.update(changes)
    return row


def final_of(row):
    return row["matchResults"][1]


class NameTables(unittest.TestCase):
    def test_tables_cover_exactly_the_twenty_canonical_clubs(self):
        self.assertEqual(len(CANON), 20)
        self.assertEqual(sorted(CANON), list(CANON))
        for table in (OPENFOOTBALL_NAMES, OPENLIGA_NAMES):
            self.assertEqual(len(table), 20)
            self.assertEqual(set(table.values()), set(CANON))

    def test_zip_alignment_of_spot_checked_aliases(self):
        for table, alias, canon in (
                (OPENFOOTBALL_NAMES, "Arsenal FC", "Arsenal"), (OPENFOOTBALL_NAMES, "Hull City AFC", "Hull City"),
                (OPENFOOTBALL_NAMES, "Brighton & Hove Albion FC", "Brighton & Hove Albion"),
                (OPENFOOTBALL_NAMES, "Tottenham Hotspur FC", "Tottenham Hotspur"),
                (OPENLIGA_NAMES, "FC Arsenal", "Arsenal"), (OPENLIGA_NAMES, "FC Liverpool", "Liverpool"),
                (OPENLIGA_NAMES, "Brentford F.C.", "Brentford"), (OPENLIGA_NAMES, "Nottingham Forest", "Nottingham Forest"),
                (OPENLIGA_NAMES, "Manchester United FC", "Manchester United"),
                (OPENLIGA_NAMES, "Sunderland", "Sunderland")):
            self.assertEqual(table[alias], canon)

    def test_every_alias_names_its_own_club(self):
        for table in (OPENFOOTBALL_NAMES, OPENLIGA_NAMES):
            for alias, canon in table.items():
                words = set(canon.replace("&", " ").split())
                self.assertTrue(words & set(alias.replace(".", "").split()), (alias, canon))


class OpenFootballTests(unittest.TestCase):
    def test_completed_match_is_reduced_to_the_agreed_fields(self):
        extra = of_match(logo="https://example.invalid/logo.png")
        self.assertEqual(openfootball(of_doc(extra)), [{
            "home": "Arsenal", "away": "Coventry City", "home_goals": 3, "away_goals": 0,
            "date": "2026-08-21", "round": 1, "source": "openfootball"}])

    def test_unfinished_records_are_skipped_not_asserted(self):
        doc = of_doc(
            of_match(),
            of_match(team1="Chelsea FC", team2="Everton FC", score=None),
            of_match(team1="Fulham FC", team2="Hull City AFC", score=[0, 0]),
            of_match(team1="Leeds United FC", team2="Liverpool FC", score={"ht": [1, 0]}),
            of_match(team1="Brentford FC", team2="Aston Villa FC"))
        del doc["matches"][-1]["score"]
        self.assertEqual([r["home"] for r in openfootball(doc)], ["Arsenal"])

    def test_explicit_full_time_nil_nil_is_a_real_result(self):
        result = openfootball(of_doc(of_match(score={"ft": [0, 0]})))
        self.assertEqual((result[0]["home_goals"], result[0]["away_goals"]), (0, 0))

    def test_output_keeps_feed_order(self):
        doc = of_doc(of_match(team1="Everton FC", team2="Fulham FC"), of_match())
        self.assertEqual([r["home"] for r in openfootball(doc)], ["Everton", "Arsenal"])

    def test_wrong_identity_or_shape_is_rejected(self):
        bad = [[], None, {}, {"matches": [of_match()]}, of_doc(of_match()) | {"name": "Premier League"},
               of_doc(of_match()) | {"name": "English Premier League 2025/26"},
               {"name": "English Premier League 2026/27", "matches": []},
               {"name": "English Premier League 2026/27", "matches": {}},
               of_doc("not a match")]
        for payload in bad:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                openfootball(payload)

    def test_bare_non_zero_list_score_is_rejected(self):
        for score in ([1, 0], [0], [True, False], "3-0", 3, {"ft": [1]}, {"et": [1, 1]}):
            with self.subTest(score=score), self.assertRaises(ValueError):
                openfootball(of_doc(of_match(score=score)))

    def test_invalid_goal_values_are_rejected(self):
        for ft in ([True, False], [-1, 0], [1.0, 0], ["1", "0"], [None, 0], [1, 0, 0]):
            with self.subTest(ft=ft), self.assertRaises(ValueError):
                openfootball(of_doc(of_match(score={"ft": ft})))

    def test_invalid_dates_are_rejected(self):
        for date in ("2026-8-21", "2026-02-30", "21/08/2026", "20260821", "2026-08-21T20:00",
                     " 2026-08-21", "2026-06-30", "2027-08-01", None, 20260821):
            with self.subTest(date=date), self.assertRaises(ValueError):
                openfootball(of_doc(of_match(date=date)))

    def test_invalid_time_is_rejected(self):
        for clock in ("25:00", "8:00", 2000, None):
            with self.subTest(clock=clock), self.assertRaises(ValueError):
                openfootball(of_doc(of_match(time=clock)))

    def test_invalid_rounds_are_rejected(self):
        for label in ("Matchday 0", "Matchday 39", "Matchday 01", "Matchday", "matchday 1", 1, None):
            with self.subTest(label=label), self.assertRaises(ValueError):
                openfootball(of_doc(of_match(round=label)))
        self.assertEqual(openfootball(of_doc(of_match(round="Matchday 38")))[0]["round"], 38)

    def test_only_exact_allowlisted_names_are_accepted(self):
        for name in ("Arsenal", "arsenal fc", "Arsenal FC ", "FC Arsenal", "Coventry", "", None, ["Arsenal FC"]):
            for key in ("team1", "team2"):
                with self.subTest(name=name, key=key), self.assertRaises(ValueError):
                    openfootball(of_doc(of_match(**{key: name})))

    def test_home_must_differ_from_away(self):
        with self.assertRaises(ValueError):
            openfootball(of_doc(of_match(team2="Arsenal FC")))

    def test_conflicting_duplicates_raise_and_identical_ones_collapse(self):
        with self.assertRaises(ValueError):
            openfootball(of_doc(of_match(), of_match(score={"ft": [0, 3]})))
        with self.assertRaises(ValueError):
            openfootball(of_doc(of_match(), of_match(date="2026-08-22")))
        with self.assertRaises(ValueError):
            openfootball(of_doc(of_match(), of_match(score=None)))
        self.assertEqual(len(openfootball(of_doc(of_match(), of_match()))), 1)
        reverse = of_match(team1="Coventry City FC", team2="Arsenal FC", round="Matchday 20")
        self.assertEqual(len(openfootball(of_doc(of_match(), reverse))), 2)

    def test_input_is_not_mutated(self):
        doc = of_doc(of_match())
        before = copy.deepcopy(doc)
        openfootball(doc)
        self.assertEqual(doc, before)


class OpenLigaTests(unittest.TestCase):
    def test_finished_row_is_reduced_to_the_agreed_fields(self):
        self.assertEqual(openliga([lg_row()]), [{
            "home": "Arsenal", "away": "Coventry City", "home_goals": 3, "away_goals": 0,
            "date": "2026-08-21", "round": 1, "source": "openligadb"}])

    def test_unfinished_rows_are_skipped_even_with_partial_results(self):
        live = lg_row(matchIsFinished=False, team1={"teamName": "Everton FC"},
                      team2={"teamName": "Fulham FC"})
        scheduled = lg_row(matchIsFinished=False, matchResults=[],
                           team1={"teamName": "Hull City"}, team2={"teamName": "Sunderland"})
        self.assertEqual([r["home"] for r in openliga([lg_row(), live, scheduled])], ["Arsenal"])

    def test_explicit_nil_nil_after_90_is_a_real_result(self):
        row = lg_row()
        final_of(row).update(pointsTeam1=0, pointsTeam2=0)
        self.assertEqual(openliga([row])[0]["home_goals"], 0)

    def test_date_is_the_london_match_date(self):
        cases = {"2026-08-21T22:59:59Z": "2026-08-21", "2026-08-21T23:00:00Z": "2026-08-22",
                 "2026-12-05T23:30:00Z": "2026-12-05", "2027-03-27T23:30:00Z": "2027-03-27",
                 "2027-03-28T00:59:59Z": "2027-03-28", "2027-03-28T23:00:00Z": "2027-03-29",
                 "2026-10-24T23:30:00Z": "2026-10-25", "2026-10-25T00:30:00Z": "2026-10-25",
                 "2026-10-25T23:30:00Z": "2026-10-25"}
        for stamp, expected in cases.items():
            with self.subTest(stamp=stamp):
                self.assertEqual(openliga([lg_row(matchDateTimeUTC=stamp)])[0]["date"], expected)

    def test_invalid_timestamps_are_rejected(self):
        for stamp in ("2026-08-21T19:00:00", "2026-08-21T19:00:00+00:00", "2026-08-21 19:00:00Z",
                      "2026-02-30T19:00:00Z", "2026-08-21T25:00:00Z", "2026-06-30T12:00:00Z",
                      "2027-08-01T12:00:00Z", "", None):
            with self.subTest(stamp=stamp), self.assertRaises(ValueError):
                openliga([lg_row(matchDateTimeUTC=stamp)])

    def test_finished_without_exactly_one_explicit_final_raises(self):
        no_final = lg_row(matchResults=[lg_row()["matchResults"][0]])
        twice = lg_row()
        twice["matchResults"].append(dict(final_of(twice)))
        wrong_id = lg_row()
        final_of(wrong_id)["resultTypeID"] = 3
        wrong_kind = lg_row()
        final_of(wrong_kind)["resultTypeKind"] = "EndResult"
        missing_points = lg_row()
        del final_of(missing_points)["pointsTeam2"]
        no_key = lg_row()
        del no_key["matchResults"]
        for row in (no_final, twice, wrong_id, wrong_kind, missing_points, no_key,
                    lg_row(matchResults=[]), lg_row(matchResults=None), lg_row(matchResults=["x"])):
            with self.subTest(row=row), self.assertRaises(ValueError):
                openliga([row])

    def test_invalid_points_are_rejected(self):
        for points in (True, False, -1, 1.0, "1", None):
            row = lg_row()
            final_of(row)["pointsTeam1"] = points
            with self.subTest(points=points), self.assertRaises(ValueError):
                openliga([row])

    def test_finished_flag_must_be_a_real_boolean(self):
        for flag in (1, 0, "true", "false", None):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                openliga([lg_row(matchIsFinished=flag)])
        row = lg_row()
        del row["matchIsFinished"]
        with self.assertRaises(ValueError):
            openliga([row])

    def test_league_and_season_identity(self):
        for changes in ({"leagueId": 5995}, {"leagueId": "5996"}, {"leagueId": True},
                        {"leagueSeason": 2025}, {"leagueSeason": "2026"}, {"leagueSeason": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                openliga([lg_row(**changes)])

    def test_group_must_be_consistent_and_match_expected_group(self):
        self.assertEqual(openliga([lg_row()], expected_group=1)[0]["round"], 1)
        row2 = lg_row(group={"groupOrderID": 2}, team1={"teamName": "Everton FC"},
                      team2={"teamName": "Fulham FC"})
        self.assertEqual(openliga([row2])[0]["round"], 2)
        for payload, expected in (([lg_row()], 2), ([lg_row(), row2], None), ([lg_row(), row2], 1),
                                  ([lg_row()], True), ([lg_row()], 0), ([lg_row()], 39), ([lg_row()], "1")):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                openliga(payload, expected_group=expected)
        for group in ({"groupOrderID": 0}, {"groupOrderID": 39}, {"groupOrderID": True},
                      {"groupOrderID": "1"}, {}, None):
            with self.subTest(group=group), self.assertRaises(ValueError):
                openliga([lg_row(group=group)])

    def test_wrong_response_shape_is_rejected(self):
        for payload in ({}, None, [], "[]", {"matches": [lg_row()]}, [None], ["row"], (lg_row(),)):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                openliga(payload)

    def test_only_exact_allowlisted_names_are_accepted(self):
        for name in ("Arsenal", "Arsenal FC", "fc arsenal", "FC Arsenal ", "Coventry", None, 5):
            for key in ("team1", "team2"):
                with self.subTest(name=name, key=key), self.assertRaises(ValueError):
                    openliga([lg_row(**{key: {"teamName": name}})])
        with self.assertRaises(ValueError):
            openliga([lg_row(team1={})])

    def test_home_must_differ_from_away(self):
        with self.assertRaises(ValueError):
            openliga([lg_row(team2={"teamName": "FC Arsenal"})])

    def test_conflicting_duplicates_raise_and_identical_ones_collapse(self):
        other = lg_row()
        final_of(other)["pointsTeam1"] = 2
        with self.assertRaises(ValueError):
            openliga([lg_row(), other])
        with self.assertRaises(ValueError):
            openliga([lg_row(), lg_row(matchIsFinished=False)])
        self.assertEqual(len(openliga([lg_row(), lg_row()])), 1)

    def test_full_group_of_ten_with_mixed_status(self):
        names = sorted(OPENLIGA_NAMES)
        rows = [lg_row(team1={"teamName": names[i]}, team2={"teamName": names[i + 10]},
                       matchIsFinished=i < 7, matchResults=lg_row()["matchResults"] if i < 7 else [])
                for i in range(10)]
        results = openliga(rows, expected_group=1)
        self.assertEqual(len(results), 7)
        self.assertEqual({r["source"] for r in results}, {"openligadb"})
        self.assertEqual(len({(r["home"], r["away"]) for r in results}), 7)


if __name__ == "__main__":
    unittest.main()
