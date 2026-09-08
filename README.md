# Valorant Round Predictor

Predicts which side wins a Valorant round from **pre-round state only** — map,
score, both teams' economy, and side — trained on professional match data
scraped from VLR.gg. Ships as an interactive web app where you set the board
state and watch the odds move.

> **Status:** in progress. Scraper fetch layer and schema are in; parsers,
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
- [ ] Match list + match page parsers
- [ ] Crawl to ~500 matches / ~40k rounds
- [ ] EDA and feature engineering
- [ ] Logistic baseline, then LightGBM
- [ ] Calibration curve + Brier score
- [ ] Export to ONNX
- [ ] Next.js app, deploy to Vercel

## License

MIT
