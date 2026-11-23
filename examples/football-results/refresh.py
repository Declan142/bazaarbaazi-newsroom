"""Refresh the public results snapshot from two centrally fetched open datasets."""

import argparse
import json
import os
import re
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from adapters import CANON, openfootball, openliga
from results import build_table, combine_results

ROOT = Path(__file__).resolve().parent
OPENLIGA = 'https://api.openligadb.de'
OPENFOOTBALL_REPO = 'https://github.com/openfootball/football.json'
OPENFOOTBALL_FILE = '2026-27/en.1.json'
USER_AGENT = 'MercatoWire open results/1.0 (+https://mercatowire.com/contact/)'


def fetch_json(url):
    """A central, bounded request. Rate limits and transient errors get backoff."""
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'application/json'}), timeout=18) as response:
                body = response.read(2_000_001)
            if len(body) > 2_000_000:
                raise ValueError('Upstream JSON exceeded the size bound')
            return json.loads(body)
        except HTTPError as exc:
            if (exc.code != 429 and exc.code < 500) or attempt == 2:
                raise
            requested = exc.headers.get('Retry-After', '')
            wait = max(5 * 2**attempt, int(requested) if requested.isdecimal() else 0)
            if wait > 40:
                raise
            time.sleep(wait)
        except (TimeoutError, URLError):
            if attempt == 2:
                raise
            time.sleep(5 * 2**attempt)


def write_json(path, payload):
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    if path.exists() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_bytes(encoded)
    os.replace(temp, path)
    return True


def openfootball_feed(cache, fetch):
    history = fetch('https://api.github.com/repos/openfootball/football.json/commits?path=2026-27%2Fen.1.json&per_page=1')
    revision = history[0]['sha']
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{40}', revision):
        raise ValueError('Missing OpenFootball revision')
    if cache.get('revision') != revision:
        url = f'https://raw.githubusercontent.com/openfootball/football.json/{revision}/{OPENFOOTBALL_FILE}'
        body = fetch(url)
        if len(body['matches']) != 380:
            raise ValueError('OpenFootball season is incomplete')
        cache = {'revision': revision, 'finals': openfootball(body)}
    return cache


def openliga_feed(cache, candidates, observed, fetch):
    group = fetch(f'{OPENLIGA}/getcurrentgroup/pl')['groupOrderID']
    if type(group) is not int or not 1 <= group <= 38:
        raise ValueError('Invalid current OpenLigaDB group')
    # Two current rounds and one rotating outstanding round keep publisher load low.
    wanted = {max(group - 1, 1), group}
    if candidates:
        wanted.add(candidates[observed.toordinal() % len(candidates)])
    for number in sorted(wanted):
        key = str(number)
        marker = fetch(f'{OPENLIGA}/getlastchangedate/pl/2026/{number}')
        if not isinstance(marker, str):
            raise ValueError('OpenLigaDB change date is invalid')
        datetime.fromisoformat(marker)
        if cache.get(key, {}).get('changed') == marker:
            continue
        rows = fetch(f'{OPENLIGA}/getmatchdata/pl/2026/{number}')
        if len(rows) != 10:
            raise ValueError(f'Incomplete OpenLigaDB round {number}')
        finals = openliga(rows, expected_group=number)
        cache[key] = {'changed': marker, 'finals': finals}
    return cache


def key(row):
    return row['home'], row['away']


def outcome(row):
    return row['date'], row['round'], row['home_goals'], row['away_goals']


def utc_stamp(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('A check time must use UTC')
    return datetime.fromisoformat(value)


def evidence_hosts(links):
    if not isinstance(links, list):
        raise ValueError('Evidence links must be a list')
    hosts = set()
    for href in links:
        link = urlsplit(href)
        if link.scheme != 'https' or not link.hostname or link.username or link.password:
            raise ValueError('Evidence must use a public HTTPS URL')
        hosts.add(link.hostname.removeprefix('www.'))
    if len(hosts) < 2:
        raise ValueError('Two independent evidence hosts are required')


def checked_document(snapshot):
    if (type(snapshot.get('schema')) is not int or snapshot['schema'] != 1 or snapshot.get('season') != '2026-27'
            or snapshot.get('competition') != 'English Premier League' or snapshot.get('clubs') != list(CANON)):
        raise ValueError('Unexpected snapshot contract')
    rows = snapshot['results']
    checked_at = utc_stamp(snapshot['updated_at'])
    if not rows:
        raise ValueError('Empty result snapshot')
    for row in rows:
        evidence_hosts(row['references'])
        if utc_stamp(row['checked_at']) > checked_at or date.fromisoformat(row['date']) > checked_at.astimezone(ZoneInfo('Europe/London')).date():
            raise ValueError('A result is later than the confirmed snapshot')
    if snapshot['table'] != build_table(snapshot['clubs'], rows) or snapshot['through'] != max(row['date'] for row in rows):
        raise ValueError('Table or cutoff does not agree with the accepted matches')
    return snapshot


def refreshed(snapshot, cache, timestamp, fetch=fetch_json):
    checked_document(snapshot)
    observed = timestamp.astimezone(ZoneInfo('Europe/London')).date()
    prior = {key(row): row for row in snapshot['results']}
    football = openfootball_feed(cache.get('openfootball', {}), fetch)
    candidates = sorted({row['round'] for row in football['finals'] if key(row) not in prior or outcome(prior[key(row)]) != outcome(row)})
    liga = openliga_feed(dict(cache.get('openligadb', {})), candidates, observed, fetch)
    liga_finals = [row for group in liga.values() for row in group['finals']]
    decision = combine_results(snapshot['clubs'], snapshot['results'], football['finals'], liga_finals, as_of=observed)
    if decision.rejected:
        raise ValueError('Invalid provider rows after normalization')
    print(f"OpenFootball: {len(football['finals'])} explicit finals. OpenLigaDB: {len(liga_finals)} explicit finals in {len(liga)} cached rounds.")
    for issue in decision.conflicts:
        print(f"Review {issue['home']} v {issue['away']}: {issue['kind']}. Accepted score retained.")
    print(f'Newly confirmed: {len(decision.added)}. Pending one-source or conflicting fixtures: {len(decision.held)}.')
    next_cache = {'openfootball': football, 'openligadb': liga}
    if not decision.added:
        return snapshot, next_cache
    checked = timestamp.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
    settled = list(snapshot['results'])
    for row in decision.added:
        refs = [f"{OPENFOOTBALL_REPO}/blob/{football['revision']}/{OPENFOOTBALL_FILE}", f"{OPENLIGA}/getmatchdata/pl/2026/{row['round']}"]
        settled.append({**row, 'confirmed_by': list(row['confirmed_by']), 'checked_at': checked, 'references': refs})
    settled.sort(key=lambda row: (row['date'], row['home'], row['away']))
    updated = {**snapshot, 'updated_at': checked, 'through': max(row['date'] for row in settled), 'results': settled,
               'table': build_table(snapshot['clubs'], settled)}
    return checked_document(updated), next_cache


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'snapshot.json')
    parser.add_argument('--cache', type=Path, default=ROOT.parents[1] / '_runtime' / 'open-football-inputs' / 'checked.json')
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text())
    cache = json.loads(args.cache.read_text()) if args.cache.exists() else {}
    updated, cache = refreshed(snapshot, cache, datetime.now(timezone.utc))
    write_json(args.cache, cache)
    changed = write_json(args.snapshot, updated) if updated is not snapshot else False
    print(f"{'Advanced' if changed else 'Retained'} {len(updated['results'])} confirmed matches through {updated['through']}.")


if __name__ == '__main__':
    main()
