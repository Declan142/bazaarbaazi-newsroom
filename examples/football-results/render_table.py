"""Render a plain public table from the same checked results file used by readers."""

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from refresh import ROOT, checked_document


def render(snapshot):
    checked_document(snapshot)
    through = date.fromisoformat(snapshot['through'])
    heading = through.strftime('%-d %B %Y')
    lines = ['# Premier League table', '',
             f"England, 2026/27. **{len(snapshot['results'])} confirmed matches through {heading}.**", '',
             '| Pos | Club | P | W | D | L | GF | GA | GD | Pts |',
             '| --: | :--- | --: | --: | --: | --: | --: | --: | --: | --: |']
    for row in snapshot['table']:
        values = [row[key] for key in ('rank', 'team', 'P', 'W', 'D', 'L', 'GF', 'GA')]
        values += [f"{row['GD']:+d}" if row['GD'] > 0 else row['GD'], row['Pts']]
        lines.append('| ' + ' | '.join(map(str, values)) + ' |')
    lines += ['', f'## Confirmed finals on {heading}', '']
    for match in snapshot['results']:
        if match['date'] != snapshot['through']:
            continue
        score = f"{match['home']} {match['home_goals']}-{match['away_goals']} {match['away']}"
        links = ', '.join(f"[{urlsplit(link).hostname.removeprefix('www.')}]({link})" for link in match['references'])
        lines.append(f'- **{score}**. {links}.')
    for field, label in (('corrections', 'Corrections'), ('source_notes', 'Source notes')):
        notices = snapshot.get(field, [])
        if notices:
            lines += ['', f'## {label}', '']
        for notice in notices:
            checked = date.fromisoformat(notice['checked_at'][:10]).strftime('%-d %B %Y')
            match_date = notice.get('date') or notice['after']['date']
            played = date.fromisoformat(match_date).strftime('%-d %B %Y')
            links = ', '.join(f"[{urlsplit(link).hostname.removeprefix('www.')}]({link})" for link in notice['references'])
            lines.append(f"- {notice['home']} v {notice['away']}, played {played}. {notice['reason']} Checked {checked}. {links}.")
    lines += ['', 'The table counts points won on the pitch. Clubs level on points, goal difference and goals scored share a rank. '
              'The [official league table](https://www.premierleague.com/en/tables/premier-league/2026-27) records league rulings.', '',
              'Data from [OpenLigaDB](https://www.openligadb.de/en/license) under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/), '
              '[OpenFootball](https://github.com/openfootball/football.json) under CC0 and independently checked match results. '
              '[Download every result and its sources](snapshot.json).']
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, default=ROOT / 'snapshot.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'standings.md')
    args = parser.parse_args()
    content = render(json.loads(args.snapshot.read_text()))
    if not args.output.exists() or args.output.read_text() != content:
        args.output.write_text(content, encoding='utf-8')
