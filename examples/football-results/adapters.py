"""Pure adapters for Premier League 2026-27 results from OpenFootball and OpenLigaDB.

No network or I/O. Each adapter returns only explicitly completed matches as plain
dicts {home, away, home_goals, away_goals, date, round, source}. Anything it does not
recognise raises ValueError so the caller can keep its existing data. Other fields
(logos, URLs, ids) are never copied to the output.
"""
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

CANON = (
    "AFC Bournemouth", "Arsenal", "Aston Villa", "Brentford", "Brighton & Hove Albion",
    "Chelsea", "Coventry City", "Crystal Palace", "Everton", "Fulham", "Hull City",
    "Ipswich Town", "Leeds United", "Liverpool", "Manchester City", "Manchester United",
    "Newcastle United", "Nottingham Forest", "Sunderland", "Tottenham Hotspur",
)
# Exact, case-sensitive provider spellings, listed in the same order as CANON.
OPENFOOTBALL_NAMES = dict(zip((
    "AFC Bournemouth", "Arsenal FC", "Aston Villa FC", "Brentford FC", "Brighton & Hove Albion FC",
    "Chelsea FC", "Coventry City FC", "Crystal Palace FC", "Everton FC", "Fulham FC",
    "Hull City AFC", "Ipswich Town FC", "Leeds United FC", "Liverpool FC", "Manchester City FC",
    "Manchester United FC", "Newcastle United FC", "Nottingham Forest FC", "Sunderland AFC",
    "Tottenham Hotspur FC",
), CANON))
OPENLIGA_NAMES = dict(zip((
    "AFC Bournemouth", "FC Arsenal", "Aston Villa", "Brentford F.C.", "Brighton & Hove Albion",
    "Chelsea FC", "Coventry City", "Crystal Palace FC", "Everton FC", "Fulham FC", "Hull City",
    "Ipswich Town", "Leeds United", "FC Liverpool", "Manchester City", "Manchester United FC",
    "Newcastle United FC", "Nottingham Forest", "Sunderland", "Tottenham Hotspur FC",
), CANON))

OPENFOOTBALL_LEAGUE = "English Premier League 2026/27"
OPENLIGA_LEAGUE_ID, OPENLIGA_SEASON = 5996, 2026
SEASON_START, SEASON_END = date(2026, 7, 1), date(2027, 7, 31)


def _int(value, low, high=None):
    """Real ints only (bool is rejected) within [low, high]."""
    if type(value) is not int or value < low or (high is not None and value > high):
        raise ValueError(f"invalid integer: {value!r}")
    return value


def _field(row, key):
    if not isinstance(row, dict) or key not in row:
        raise ValueError(f"missing {key!r}")
    return row[key]


def _club(table, name):
    if not isinstance(name, str) or name not in table:
        raise ValueError(f"unknown club name: {name!r}")
    return table[name]


def _parse(text, pattern, fmt):
    """Fixed-shape text parsed through datetime (rejects 2026-8-1 and 2026-02-30)."""
    if not isinstance(text, str) or not re.fullmatch(pattern, text):
        raise ValueError(f"invalid date or time: {text!r}")
    return datetime.strptime(text, fmt)


def _season_day(moment):
    if not SEASON_START <= moment.date() <= SEASON_END:
        raise ValueError(f"date outside the 2026-27 season: {moment.date()}")
    return moment.date()


def _london_day(text):
    moment = _parse(text, r"[0-9]{4}(-[0-9]{2}){2}T[0-9]{2}(:[0-9]{2}){2}Z", "%Y-%m-%dT%H:%M:%SZ")
    return _season_day(moment.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Europe/London")))


def _remember(seen, home, away, detail):
    """True for a new ordered pair, False for an identical repeat, ValueError on conflict."""
    if (home, away) in seen and seen[(home, away)] != detail:
        raise ValueError(f"conflicting duplicate fixture: {home} v {away}")
    new = (home, away) not in seen
    seen[(home, away)] = detail
    return new


def _result(home, away, goals, day, rnd, source):
    return {"home": home, "away": away, "home_goals": goals[0], "away_goals": goals[1],
            "date": day.isoformat(), "round": rnd, "source": source}


def _pair(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError(f"invalid score pair: {value!r}")
    return tuple(_int(goal, 0) for goal in value)


def _openfootball_goals(score):
    """Full-time goals, or None when the record asserts no completed result."""
    if score is None:
        return None
    if isinstance(score, list):  # bare list: only the [0, 0] placeholder is tolerated
        if _pair(score) == (0, 0):
            return None
        raise ValueError(f"bare score without status: {score!r}")
    if not isinstance(score, dict) or not set(score) <= {"ht", "ft"}:
        raise ValueError(f"unknown score schema: {score!r}")
    if "ht" in score:
        _pair(score["ht"])
    return _pair(score["ft"]) if "ft" in score else None


def openfootball(payload):
    if not isinstance(payload, dict) or payload.get("name") != OPENFOOTBALL_LEAGUE:
        raise ValueError("not the OpenFootball English Premier League 2026/27 document")
    matches = payload.get("matches")
    if not isinstance(matches, list) or not matches:
        raise ValueError("matches must be a non-empty list")
    seen, results = {}, []
    for match in matches:
        home = _club(OPENFOOTBALL_NAMES, _field(match, "team1"))
        away = _club(OPENFOOTBALL_NAMES, _field(match, "team2"))
        if home == away:
            raise ValueError(f"home equals away: {home}")
        label = _field(match, "round")
        found = re.fullmatch(r"Matchday ([1-9][0-9]?)", label) if isinstance(label, str) else None
        if not found:
            raise ValueError(f"invalid round: {label!r}")
        rnd = _int(int(found.group(1)), 1, 38)
        day = _season_day(_parse(_field(match, "date"), r"[0-9]{4}(-[0-9]{2}){2}", "%Y-%m-%d"))
        if "time" in match:  # kickoff is validated but not part of the output
            _parse(match["time"], r"[0-9]{2}:[0-9]{2}", "%H:%M")
        goals = _openfootball_goals(match.get("score"))
        if _remember(seen, home, away, (day, rnd, goals)) and goals is not None:
            results.append(_result(home, away, goals, day, rnd, "openfootball"))
    return results


def _openliga_goals(row):
    """After90Minutes points of a finished row; exactly one explicit entry is required."""
    entries = _field(row, "matchResults")
    if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
        raise ValueError("matchResults must be a list of objects")
    finals = [e for e in entries
              if e.get("resultTypeKind") == "After90Minutes" or e.get("resultTypeID") == 2]
    if len(finals) != 1:
        raise ValueError(f"finished match needs exactly one final result, found {len(finals)}")
    final = finals[0]
    if final.get("resultTypeKind") != "After90Minutes":
        raise ValueError(f"ambiguous final result: {final!r}")
    _int(final.get("resultTypeID"), 2, 2)
    return _int(_field(final, "pointsTeam1"), 0), _int(_field(final, "pointsTeam2"), 0)


def openliga(payload, expected_group=None):
    if expected_group is not None:
        _int(expected_group, 1, 38)
    if not isinstance(payload, list) or not payload:
        raise ValueError("OpenLigaDB response must be a non-empty list")
    group, seen, results = expected_group, {}, []
    for row in payload:
        _int(_field(row, "leagueId"), OPENLIGA_LEAGUE_ID, OPENLIGA_LEAGUE_ID)
        _int(_field(row, "leagueSeason"), OPENLIGA_SEASON, OPENLIGA_SEASON)
        rnd = _int(_field(_field(row, "group"), "groupOrderID"), 1, 38)
        if rnd != (group or rnd):
            raise ValueError(f"row group {rnd} does not match group {group}")
        group = rnd
        home = _club(OPENLIGA_NAMES, _field(_field(row, "team1"), "teamName"))
        away = _club(OPENLIGA_NAMES, _field(_field(row, "team2"), "teamName"))
        if home == away:
            raise ValueError(f"home equals away: {home}")
        day = _london_day(_field(row, "matchDateTimeUTC"))
        finished = _field(row, "matchIsFinished")
        if type(finished) is not bool:
            raise ValueError(f"matchIsFinished must be true or false: {finished!r}")
        goals = _openliga_goals(row) if finished else None
        if _remember(seen, home, away, (day, rnd, goals)) and goals is not None:
            results.append(_result(home, away, goals, day, rnd, "openligadb"))
    return results
