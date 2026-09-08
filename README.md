# Valorant Round Predictor

Predicts which side wins a Valorant round from **pre-round state only** — map,
score, both teams' economy, and side — trained on professional match data
scraped from VLR.gg. Ships as an interactive web app where you set the board
state and watch the odds move.

> **Status:** model trained and calibrated on 17,308 rounds. Web app next.
> See [Results](#results) and [Roadmap](#roadmap).

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

## Results

Trained on 17,308 rounds from 332 professional matches, held out **by match**
rather than by round - rounds inside one match share teams, form and economy,
so a random round split leaks across the boundary and flatters the score.

| model | Brier | log loss | AUC | accuracy |
| --- | --- | --- | --- | --- |
| baseline (always the base rate) | 0.2499 | 0.6930 | 0.500 | 0.511 |
| **logistic regression** | **0.2165** | **0.6204** | **0.701** | **0.636** |
| gradient boosting | 0.2175 | 0.6223 | 0.693 | 0.626 |

Logistic regression edges out gradient boosting, so the relationship is close
to linear in log-odds and the extra machinery earns nothing. The simpler model
ships - which also makes in-browser inference almost free.

Calibration on held-out matches, which matters more here than accuracy:

| predicted | actual | n |
| --- | --- | --- |
| 15% | 17% | 258 |
| 36% | 37% | 387 |
| 46% | 46% | 1,361 |
| 54% | 57% | 1,031 |
| 77% | 81% | 176 |
| 92% | 91% | 180 |

Every bucket lands within a few points of its stated probability.

### What the data says about buying

Attacker win rate by attacker bracket, holding defenders at a full buy:

| attacker bracket | n | win rate |
| --- | --- | --- |
| eco | 37 | 5.4% |
| semi-eco | 814 | 19.0% |
| semi-buy | 2,541 | 39.3% |
| full-buy | 6,387 | 48.4% |

An earlier version of this table, computed without holding the defender economy
fixed, appeared to show semi-buy performing as well as a full buy. That was a
confound: it pooled rounds where the defenders were also broke. Controlling for
it, the relationship is monotonic with real gaps throughout.

## Where the data comes from

Two pages are needed per match, because they carry different halves of a round:

| Page | Provides |
| --- | --- |
| match page | winner, side, and win condition (elim / spike / defuse / time) |
| `?tab=economy` | loadout value and bank for both teams, per round |

They join on `(game_id, round_num)`. Loadout value and bank are different
numbers and both are kept: loadout is what a team is holding and drives who wins
the round, bank is what they have left and drives what they can afford next.

Loadout value is bucketed into VLR's own
buy types — eco `<$5k`, semi-eco `$5-10k`, semi-buy `$10-20k`, full-buy `$20k+`.

**Coverage is uneven, and that is upstream.** Lower-tier events (smaller
regional leagues) often have no economy tab and no round-outcome icons at all —
not a parsing failure, simply data VLR never recorded. Those rounds are still
stored, since map and score features remain valid, but the training set requires
non-null credits. Expect to lose roughly a fifth of raw rounds this way.

Parser correctness is checked against invariants rather than by eyeballing:
attacking and defending sides must swap between rounds 12 and 13, round totals
must match the economy table's row count, and no round may be missing credits.

## A measured negative result

Enemy credits are never observable, so the plan was to reconstruct them by
replaying the economy rules over round outcomes. Measured against 21k real
rounds, that fails: **$5,924 mean absolute error, and 35.1% buy-bracket
accuracy against a 57.8% majority-class baseline.**

The cause is structural. Survivors carry weapons into the next round for free,
so credits and loadout value are different quantities and the gap depends on
who lived. The simulator's error is one-directional in exactly the way that
predicts - it called 18,270 full-buy rounds semi-buy.

The consequence is a design constraint, not a dead end: a live tool needs
survivor and kill counts per round, both readable from the round-end screen,
not just who won. Model training is unaffected, since VLR reports real loadout
values. The simulator and its validation are kept in the repo because the
measurement is what tells you which inputs the live version requires.

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
model/     economy simulator, features, training, evaluation
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
