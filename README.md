# Valorant Round Predictor

Predicts which side wins a Valorant round from **pre-round state only** — map,
score, both teams' economy, and side — trained on professional match data
scraped from VLR.gg. Ships as an interactive web app where you set the board
state and watch the odds move.

> **Status:** in progress. Scraping and parsing work end to end; the crawl,
> model, and web app are next. See [Roadmap](#roadmap).

## Why pre-round, and not a live win-probability curve

The obvious version of this project is an esports-style win probability *curve*
that updates second by second. That needs timestamped kill events, and the
public data does not have them — VLR.gg publishes round-level results
(winner, win condition, buy type, economy) but not a within-round event log.

So the model is scoped to what the data actually supports: **P(attackers win)
evaluated at round start.** A mid-round state explorer is a stretch goal that
would require hand-labeling or extracting events from VODs, and it is tracked
as such rather than promised.

## Design notes

**Leakage is the main hazard.** Any feature computed from what happened *during*
the round — final credits, kills, plant status — leaks the label. The `rounds`
table is built so that everything except `winner_side` and `win_condition` is
knowable before the round begins, and that invariant is documented in the schema
itself rather than left to memory.

**Calibration over accuracy.** A round predictor that is 60% accurate but well
calibrated is more useful than one that is 63% accurate and overconfident. The
headline metric is Brier score plus a reliability curve, not accuracy.

**Scraping is cached and resumable.** Pages are written to `data/raw/` on first
fetch, and already-scraped match IDs are skipped, so re-parsing costs nothing
and an interrupted crawl picks up where it stopped.

## Where the data comes from

Two pages are needed per match, because they carry different halves of a round:

| Page | Provides |
| --- | --- |
| match page | winner, side, and win condition (elim / spike / defuse / time) |
| `?tab=economy` | exact loadout value and bank for both teams, per round |

They join on `(game_id, round_num)`. Loadout value is bucketed into VLR's own
buy types — eco `<$5k`, semi-eco `$5-10k`, semi-buy `$10-20k`, full-buy `$20k+`.

**Coverage is uneven, and that is upstream.** Lower-tier events (smaller
regional leagues) often have no economy tab and no round-outcome icons at all —
not a parsing failure, simply data VLR never recorded. Those rounds are still
stored, since map and score features remain valid, but the training set requires
non-null credits. Expect to lose roughly a fifth of raw rounds this way.

Parser correctness is checked against invariants rather than by eyeballing:
attacking and defending sides must swap between rounds 12 and 13, round totals
must match the economy table's row count, and no round may be missing credits.

## Stack

| Layer | Choice |
| --- | --- |
| Scraping | Python, httpx, selectolax, tenacity |
| Storage | SQLite |
| Modeling | pandas, scikit-learn, LightGBM |
| Serving | ONNX exported to the browser — no backend to keep alive |
| Frontend | Next.js, TypeScript, Tailwind (deployed on Vercel) |

## Layout

```
scraper/   fetch layer, schema, parsers
model/     feature engineering, training, evaluation
data/      SQLite db and raw HTML cache (gitignored)
notebooks/ exploratory analysis
web/       Next.js app (not yet created)
```

## Getting started

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m scraper.db
```

## Roadmap

- [x] Repo, schema, polite cached fetch layer
- [x] Match list + match page parsers
- [x] Resumable crawler (`python -m scraper.run --pages N`)
- [ ] Crawl to ~500 matches / ~40k rounds
- [ ] EDA and feature engineering
- [ ] Logistic baseline, then LightGBM
- [ ] Calibration curve + Brier score
- [ ] Export to ONNX
- [ ] Next.js app, deploy to Vercel

## License

MIT
