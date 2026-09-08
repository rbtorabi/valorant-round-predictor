"""Measures how accurately the economy simulator reconstructs real credits.

The simulator has to work without per-round kill data, and kills pay $200 each,
so up to $1000 a round is invisible to it. This script quantifies that gap by
replaying every scraped map and comparing predicted credits against the bank
values VLR actually recorded.

    python -m model.validate
"""

import statistics

from scraper import db
from model.economy import simulate_match


def load_maps(conn) -> list[list[dict]]:
    """Every map that has bank data, as an ordered list of round dicts."""
    map_ids = [
        r["id"] for r in conn.execute(
            """SELECT DISTINCT mp.id
               FROM maps mp JOIN rounds r ON r.map_id = mp.id
               WHERE r.atk_bank IS NOT NULL"""
        )
    ]
    maps = []
    for map_id in map_ids:
        rounds = [dict(r) for r in conn.execute(
            """SELECT round_num, winner_side, win_condition,
                      atk_loadout, def_loadout, atk_bank, def_bank
               FROM rounds WHERE map_id = ? ORDER BY round_num""",
            (map_id,),
        )]
        if rounds:
            maps.append(rounds)
    return maps


def main() -> None:
    conn = db.connect()
    maps = load_maps(conn)
    print(f"validating against {len(maps)} maps")

    errors: list[int] = []
    by_round: dict[int, list[int]] = {}

    for rounds in maps:
        predicted = simulate_match(rounds)
        for actual, pred in zip(rounds, predicted):
            for side in ("atk", "def"):
                truth = actual[f"{side}_bank"]
                if truth is None:
                    continue
                err = abs(pred[f"pred_{side}_credits"] - truth)
                errors.append(err)
                by_round.setdefault(actual["round_num"], []).append(err)

    if not errors:
        print("no bank data in database - rebuild it first")
        return

    within = lambda n: 100 * sum(e <= n for e in errors) / len(errors)
    print(f"\ncomparisons      {len(errors):,}")
    print(f"mean abs error   ${statistics.mean(errors):,.0f}")
    print(f"median abs error ${statistics.median(errors):,.0f}")
    print(f"within $500      {within(500):.1f}%")
    print(f"within $1000     {within(1000):.1f}%")

    # --- the decision-relevant question -----------------------------------
    # Dollars are not what the win model consumes; buy brackets are. Brackets
    # are far coarser than banks, so ask directly how often the simulator puts
    # a team in the right one.
    from scraper.parse import buy_type

    hits = total = 0
    confusion: dict[tuple, int] = {}
    for rounds in maps:
        predicted = simulate_match(rounds)
        for actual, pred in zip(rounds, predicted):
            for side in ("atk", "def"):
                truth_loadout = actual[side + "_loadout"]
                if truth_loadout is None:
                    continue
                truth = buy_type(truth_loadout)
                guess = buy_type(pred["pred_" + side + "_pre"])
                total += 1
                hits += (truth == guess)
                key = (truth, guess)
                confusion[key] = confusion.get(key, 0) + 1

    majority = max(
        sum(v for (tr, _), v in confusion.items() if tr == label)
        for label in {tr for tr, _ in confusion}
    )
    print("")
    print(f"buy-bracket accuracy   {100*hits/total:.1f}%   (n={total:,})")
    print(f"majority-class baseline {100*majority/total:.1f}%")
    print("")
    print("most common outcomes:")
    for (tr, gu), n in sorted(confusion.items(), key=lambda kv: -kv[1])[:6]:
        mark = "ok" if tr == gu else "MISS"
        print(f"  actual {str(tr):9} guessed {str(gu):9} {n:>6,}  {mark}")

    print("\nerror by round (drift should reset at 13):")
    for rnum in sorted(by_round)[:16]:
        errs = by_round[rnum]
        bar = "#" * int(statistics.mean(errs) / 120)
        print(f"  r{rnum:<3} n={len(errs):<5} ${statistics.mean(errs):>6,.0f}  {bar}")


if __name__ == "__main__":
    main()
