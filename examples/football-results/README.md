# A Premier League results desk

Read the [standings and latest finals](standings.md), or download the [season snapshot](snapshot.json) for each confirmed match date, score and source link. Both views use the same English Premier League 2026/27 results. The [MercatoWire match centre](https://mercatowire.com/premier-league/) also works with JavaScript switched off.

The first 110 matches cover 21 August to 23 November 2026. The original table was checked against all 20 rows in the [Premier League table](https://www.premierleague.com/en/tables/premier-league/2026-27) and [the Guardian](https://www.theguardian.com/football/premierleague/table). Games played, wins, draws, losses, goals and points agreed. The source notes record a September score where a community entry differed from [Brentford's official report](https://www.brentfordfc.com/en/matches/mens/bournemouth-v-brentford-premier-league-20260912).

## Follow a result

Look up the home and away teams in `results`. Each match records the date, score, round, check time and evidence links. `through` is the most recent match date in the file. `updated_at` is the last accepted change. A scheduled check does not advance either date by itself. The table assigns three points for a win and one for a draw. Clubs level on points, goal difference and goals scored share a rank and appear alphabetically. Administrative deductions and end-of-season tie rulings belong to the league's official table.

The [hosted job](../../.github/workflows/football-results.yml) runs daily at 23:47 UTC and can also be dispatched. It checks [OpenFootball](https://github.com/openfootball/football.json) and [OpenLigaDB](https://www.openligadb.de/en/terms-of-use). A new result needs a matching final score, match date and round from both. Community volunteers update these sources at different times. A blank, an old response or a plain pair without a full-time label cannot erase an accepted result. A discrepancy is reported in the run log. The input cache is shared centrally, so individual reader visits do not poll OpenLigaDB.

If a published result needs correction, verify it against two independent reports including a club or league source. Submit a reviewed change with the corrected result, recalculated table and a dated `corrections` entry naming the home and away clubs, `before` and `after` match details, the reason, `checked_at` and both reference URLs. Existing data remains available in Git history.

Run with Python 3.11 or newer from the repository root.

```sh
python3 -m unittest discover -s examples/football-results -q
python3 examples/football-results/refresh.py
python3 examples/football-results/render_table.py
```

## Reuse and credit

Data from [OpenLigaDB](https://www.openligadb.de/en/license), licensed under [ODbL 1.0](https://opendatacommons.org/licenses/odbl/1-0/). Club names and match dates have been normalized and standings calculated. The modified database is available in full under ODbL 1.0 in [snapshot.json](snapshot.json). [OpenFootball](https://github.com/openfootball/football.json) dedicates its data to the public domain under [CC0](https://creativecommons.org/publicdomain/zero/1.0/). Editorial source links identify independently checked facts. Use the source pages under their own terms. The example code follows the repository's [AGPL-3.0 licence](../../LICENSE).
