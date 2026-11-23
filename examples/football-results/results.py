"""Reconcile two independent full-time sources against immutable accepted results.

Each team meets every other club once at home and once away. Conflicting scores
and dates are reported for review. The standings use on-field results only.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

__all__ = ["CombineResult", "combine_results", "build_table", "LEAGUE_SIZE"]

LEAGUE_SIZE = 20
MAX_ROUND = 2 * (LEAGUE_SIZE - 1)  # 38 rounds, 380 fixtures

_FIELDS = ("home", "away", "home_goals", "away_goals", "date", "round", "source")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class CombineResult:
    """New confirmed fixtures, review findings and the complete accepted set."""

    accepted: tuple
    added: tuple
    held: tuple
    conflicts: tuple
    rejected: tuple
    source_status: dict


class _Invalid(Exception):
    """A record failed validation; the message is the reason."""


# Validation helpers

def _clean_teams(teams):
    if not isinstance(teams, (list, tuple)):
        raise ValueError("teams must be a list or tuple of team names")
    if len(teams) != LEAGUE_SIZE:
        raise ValueError(f"teams must contain exactly {LEAGUE_SIZE} names")
    for t in teams:
        if type(t) is not str or not t.strip() or t != t.strip():
            raise ValueError(f"invalid team name: {t!r}")
    if len(set(teams)) != len(teams):
        raise ValueError("teams contains duplicates")
    return tuple(teams)


def _name_map(teams, aliases):
    names = {t: t for t in teams}
    if aliases is None:
        return names
    if not isinstance(aliases, Mapping):
        raise ValueError("aliases must be a mapping of alias -> canonical team")
    canonical = set(teams)
    for alias, target in aliases.items():
        if type(alias) is not str or type(target) is not str:
            raise ValueError("aliases must map strings to strings")
        if target not in canonical:
            raise ValueError(f"alias target is not a canonical team: {target!r}")
        if alias in canonical:
            raise ValueError(f"alias collides with a canonical team: {alias!r}")
        names[alias] = target
    return names


def _validate(raw, names):
    """Return a clean 7-field record (canonical team names) or raise _Invalid."""
    if not isinstance(raw, Mapping):
        raise _Invalid("record is not a mapping")
    missing = [f for f in _FIELDS if f not in raw]
    if missing:
        raise _Invalid("missing fields: " + ", ".join(missing))
    teams = []
    for field in ("home", "away"):
        value = raw[field]
        if type(value) is not str or value not in names:
            raise _Invalid(f"unknown team in {field}: {value!r}")
        teams.append(names[value])
    if teams[0] == teams[1]:
        raise _Invalid("fixture has the same team on both sides")
    for field in ("home_goals", "away_goals"):
        value = raw[field]
        if type(value) is not int or value < 0:  # type() check also rejects bool
            raise _Invalid(f"{field} must be a non-negative int: {value!r}")
    date = raw["date"]
    if type(date) is not str or not _DATE_RE.fullmatch(date):
        raise _Invalid(f"date must be an ISO YYYY-MM-DD string: {date!r}")
    try:
        _dt.date.fromisoformat(date)
    except ValueError:
        raise _Invalid(f"date is not a real calendar date: {date!r}") from None
    rnd = raw["round"]
    if type(rnd) is not int or not 1 <= rnd <= MAX_ROUND:
        raise _Invalid(f"round must be an int from 1 to {MAX_ROUND}: {rnd!r}")
    source = raw["source"]
    if type(source) is not str or not source.strip():
        raise _Invalid("source must be a non-empty string")
    return {
        "home": teams[0],
        "away": teams[1],
        "home_goals": raw["home_goals"],
        "away_goals": raw["away_goals"],
        "date": date,
        "round": rnd,
        "source": source,
    }


def _checked_records(raw_list, names, label):
    """Validate a whole trusted list (baseline / accepted); raise ValueError."""
    if not isinstance(raw_list, (list, tuple)):
        raise ValueError(f"{label} must be a list or tuple of records")
    records, seen = [], set()
    for index, raw in enumerate(raw_list):
        try:
            rec = _validate(raw, names)
        except _Invalid as exc:
            raise ValueError(f"{label}[{index}]: {exc}") from None
        key = (rec["home"], rec["away"])
        if key in seen:
            raise ValueError(f"{label}[{index}]: fixture {_name(key)} appears twice")
        seen.add(key)
        records.append({**raw, **rec})
    occupied = {}
    for rec in records:
        for team in (rec["home"], rec["away"]):
            slot = (rec["round"], team)
            if slot in occupied:
                raise ValueError(
                    f"{label}: {team} plays twice in round {rec['round']} "
                    f"({_name(occupied[slot])} and {_name((rec['home'], rec['away']))})"
                )
            occupied[slot] = (rec["home"], rec["away"])
    return records


# Small helpers

def _name(key):
    return f"{key[0]} v {key[1]}"


def _score(rec):
    return (rec["home_goals"], rec["away_goals"])


def _when(rec):
    return (rec["date"], rec["round"])


def _fixture_order(rec):
    return (rec["round"], rec["date"], rec["home"], rec["away"])


def _describe(raw):
    if isinstance(raw, Mapping):
        return "{" + ", ".join(sorted(f"{k!r}: {v!r}" for k, v in raw.items())) + "}"
    return repr(raw)


def _report(rec):
    sources = rec.get("sources") or (rec["source"],)
    return {
        "source": " + ".join(sources),
        "home_goals": rec["home_goals"],
        "away_goals": rec["away_goals"],
        "date": rec["date"],
        "round": rec["round"],
    }


def _report_order(rep):
    return (rep["source"], rep["home_goals"], rep["away_goals"], rep["date"], rep["round"])


def _conflict(key, kind, baseline, reports, note):
    return {
        "home": key[0],
        "away": key[1],
        "kind": kind,
        "baseline": dict(baseline) if baseline is not None else None,
        "reports": tuple(sorted(reports, key=_report_order)),
        "note": note,
    }


def _held(key, reason):
    return {"home": key[0], "away": key[1], "reason": reason}


# Feed reading

class _Feed:
    def __init__(self, label):
        self.label = label
        self.problem = None      # None when usable
        self.rows = {}           # key -> collapsed record with "sources" tuple
        self.conflicting = {}    # key -> list of conflicting duplicate records
        self.tainted = set()     # keys that had a malformed record
        self.rejected = []


def _guess_key(raw, names):
    """Fixture key of a malformed record, if its team names are still usable."""
    if not isinstance(raw, Mapping):
        return None
    home, away = raw.get("home"), raw.get("away")
    if type(home) is str and type(away) is str and home in names and away in names:
        if names[home] != names[away]:
            return (names[home], names[away])
    return None


def _read_feed(label, raw_feed, names):
    feed = _Feed(label)
    if raw_feed is None:
        feed.problem = "missing"
        return feed
    if not isinstance(raw_feed, (list, tuple)):
        feed.problem = "not a list of records"
        return feed
    grouped = defaultdict(list)
    for raw in raw_feed:
        try:
            rec = _validate(raw, names)
        except _Invalid as exc:
            feed.rejected.append(
                {"feed": label, "reason": str(exc), "record": _describe(raw)}
            )
            key = _guess_key(raw, names)
            if key is not None:
                feed.tainted.add(key)
            continue
        grouped[(rec["home"], rec["away"])].append(rec)
    for key, recs in grouped.items():
        distinct = {(*_score(r), *_when(r)) for r in recs}
        if len(distinct) == 1:
            merged = dict(recs[0])
            merged["sources"] = tuple(sorted({r["source"] for r in recs}))
            feed.rows[key] = merged
        else:
            feed.conflicting[key] = recs
    return feed


# Public API

def combine_results(teams, baseline, feed_a, feed_b, *, as_of, aliases=None):
    """Combine a trusted baseline with two independent feeds, failing closed.

    teams    the 20 canonical team names.
    baseline list of accepted fixture records (checked; ValueError if invalid).
    feed_a / feed_b
             lists of records, or None / anything else for a failed source.
    as_of    ``datetime.date``; fixtures dated after it are never promoted.
    aliases  optional {alias: canonical team} applied to feed records only.

    Inputs are never mutated. See the module docstring for the rules.
    """
    teams = _clean_teams(teams)
    if type(as_of) is not _dt.date:
        raise ValueError("as_of must be a datetime.date")
    names = _name_map(teams, aliases)
    base_list = _checked_records(baseline, {t: t for t in teams}, "baseline")
    base_by_key = {(r["home"], r["away"]): r for r in base_list}

    feeds = [_read_feed("feed_a", feed_a, names), _read_feed("feed_b", feed_b, names)]
    usable = [f for f in feeds if f.problem is None]
    both_usable = len(usable) == 2

    keys = set()
    for f in usable:
        keys |= set(f.rows) | set(f.conflicting) | f.tainted

    held, conflicts, candidates = [], [], {}

    for key in sorted(keys):
        base = base_by_key.get(key)
        rows = sorted((f.rows[key] for f in usable if key in f.rows),
                      key=lambda r: r["sources"])
        shaky = any(key in f.conflicting or key in f.tainted for f in usable)

        for f in usable:
            if key in f.conflicting:
                conflicts.append(_conflict(
                    key, "duplicate_conflict", base,
                    [_report(r) for r in f.conflicting[key]],
                    "one feed gave conflicting rows for this fixture; none was chosen",
                ))

        if base is not None:
            # Baseline always wins. Only log what the feeds disagree about.
            reports = [_report(r) for r in rows]
            differing = [r for r in rows if _score(r) != _score(base)]
            if differing:
                agreed_correction = (
                    not shaky and len(rows) == 2 and len(differing) == 2
                    and _score(rows[0]) == _score(rows[1])
                )
                if agreed_correction:
                    conflicts.append(_conflict(
                        key, "correction_pending", base, reports,
                        "both feeds report a different score than the accepted baseline; "
                        "baseline kept, manual confirmation required",
                    ))
                else:
                    conflicts.append(_conflict(
                        key, "baseline_score_conflict", base, reports,
                        "feed score differs from the accepted baseline and the feeds "
                        "do not agree on a correction; baseline kept",
                    ))
            elif any(_when(r) != _when(base) for r in rows):
                conflicts.append(_conflict(
                    key, "date_or_round_mismatch", base, reports,
                    "feed date or round differs from the accepted baseline; baseline kept",
                ))
            continue

        # Not in the baseline: a candidate addition.
        if not both_usable:
            held.append(_held(key, "source_failure"))
            continue
        if shaky:
            held.append(_held(key, "unreliable_source_data"))
            continue
        if len(rows) < 2:
            held.append(_held(key, "single_source"))
            continue
        a, b = rows
        reports = [_report(a), _report(b)]
        if _score(a) != _score(b):
            conflicts.append(_conflict(
                key, "score_conflict", None, reports,
                "the two feeds report different full-time scores",
            ))
            held.append(_held(key, "score_conflict"))
        elif _when(a) != _when(b):
            conflicts.append(_conflict(
                key, "date_or_round_mismatch", None, reports,
                "the two feeds report a different date or round",
            ))
            held.append(_held(key, "date_or_round_mismatch"))
        elif set(a["sources"]) & set(b["sources"]):
            held.append(_held(key, "sources_not_independent"))
        elif _dt.date.fromisoformat(a["date"]) > as_of:
            held.append(_held(key, "future_fixture"))
        else:
            candidates[key] = (a, b)

    # A team may play only once per round, across baseline and candidates.
    occupancy = defaultdict(set)
    for rec in base_list:
        for team in (rec["home"], rec["away"]):
            occupancy[(rec["round"], team)].add((rec["home"], rec["away"]))
    for key, (a, _b) in candidates.items():
        for team in key:
            occupancy[(a["round"], team)].add(key)

    added = []
    for key in sorted(candidates):
        a, b = candidates[key]
        others = set()
        for team in key:
            others |= occupancy[(a["round"], team)]
        others.discard(key)
        if others:
            listed = ", ".join(sorted(_name(o) for o in others))
            conflicts.append(_conflict(
                key, "round_clash", None, [_report(a), _report(b)],
                f"a team would play twice in round {a['round']}; also scheduled: {listed}",
            ))
            held.append(_held(key, "round_clash"))
            continue
        confirmed_by = tuple(sorted(set(a["sources"]) | set(b["sources"])))
        added.append({
            "home": key[0],
            "away": key[1],
            "home_goals": a["home_goals"],
            "away_goals": a["away_goals"],
            "date": a["date"],
            "round": a["round"],
            "source": "+".join(confirmed_by),
            "confirmed_by": confirmed_by,
        })

    added.sort(key=_fixture_order)
    accepted = sorted(base_list + added, key=_fixture_order)
    rejected = sorted(
        (r for f in feeds for r in f.rejected),
        key=lambda r: (r["feed"], r["reason"], r["record"]),
    )
    return CombineResult(
        accepted=tuple(accepted),
        added=tuple(added),
        held=tuple(sorted(held, key=lambda h: (h["home"], h["away"], h["reason"]))),
        conflicts=tuple(sorted(
            conflicts,
            key=lambda c: (c["home"], c["away"], c["kind"], repr(c["reports"])),
        )),
        rejected=tuple(rejected),
        source_status={
            f.label: "ok" if f.problem is None else f"unusable: {f.problem}"
            for f in feeds
        },
    )


def build_table(teams, fixtures):
    """Build the league table from accepted fixtures.

    Returns one dict per team with keys rank, team, P, W, D, L, GF, GA, GD, Pts.
    Order: Pts, GD, GF descending; teams level on all three share a rank
    (1, 1, 3 ...) and are listed alphabetically. Every team appears, even with
    no games. Raises ValueError for invalid, duplicate or clashing fixtures.
    """
    teams = _clean_teams(teams)
    records = _checked_records(fixtures, {t: t for t in teams}, "fixtures")
    stats = {
        t: {"rank": 0, "team": t, "P": 0, "W": 0, "D": 0, "L": 0,
            "GF": 0, "GA": 0, "GD": 0, "Pts": 0}
        for t in teams
    }
    for rec in records:
        hg, ag = rec["home_goals"], rec["away_goals"]
        for team, scored, conceded in ((rec["home"], hg, ag), (rec["away"], ag, hg)):
            row = stats[team]
            row["P"] += 1
            row["GF"] += scored
            row["GA"] += conceded
            if scored > conceded:
                row["W"] += 1
                row["Pts"] += 3
            elif scored == conceded:
                row["D"] += 1
                row["Pts"] += 1
            else:
                row["L"] += 1
    rows = list(stats.values())
    for row in rows:
        row["GD"] = row["GF"] - row["GA"]
    rows.sort(key=lambda r: (-r["Pts"], -r["GD"], -r["GF"], r["team"].casefold(), r["team"]))
    previous, rank = None, 0
    for position, row in enumerate(rows, start=1):
        level = (row["Pts"], row["GD"], row["GF"])
        if level != previous:
            rank, previous = position, level
        row["rank"] = rank
    return rows
