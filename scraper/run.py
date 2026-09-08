"""Crawl VLR.gg results pages into the local SQLite database.

Resumable by design: match ids already in the database are skipped, and every
page fetched is cached on disk, so re-running after a crash or a parser fix
costs almost nothing.

    python -m scraper.run --pages 10
    python -m scraper.run --pages 50 --max-matches 500
"""

import argparse
import sqlite3
import sys
import traceback

from scraper import db
from scraper.parse import ParsedMatch, match_id_from_url, parse_match, parse_match_list
from scraper.vlr import BASE, fetch

RESULTS_URL = BASE + "/matches/results/?page={page}"


def insert_match(conn: sqlite3.Connection, m: ParsedMatch) -> int:
    cur = conn.execute(
        """INSERT INTO matches (vlr_match_id, url, event, series, played_at, team_a, team_b)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (m.vlr_match_id, m.url, m.event, m.series, m.played_at, m.team_a, m.team_b),
    )
    match_id = cur.lastrowid

    for mp in m.maps:
        cur = conn.execute(
            """INSERT INTO maps (match_id, map_name, map_index, score_a, score_b)
               VALUES (?, ?, ?, ?, ?)""",
            (match_id, mp["map_name"], mp["map_index"], mp["score_a"], mp["score_b"]),
        )
        map_id = cur.lastrowid

        conn.executemany(
            """INSERT INTO rounds (
                   map_id, round_num, atk_team, def_team,
                   atk_score_pre, def_score_pre,
                   atk_buy, def_buy,
                   atk_loadout, def_loadout, atk_bank, def_bank,
                   winner_side, win_condition
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    map_id, r["round_num"], r["atk_team"], r["def_team"],
                    r["atk_score_pre"], r["def_score_pre"],
                    r["atk_buy"], r["def_buy"],
                    r["atk_loadout"], r["def_loadout"], r["atk_bank"], r["def_bank"],
                    r["winner_side"], r["win_condition"],
                )
                for r in mp["rounds"]
            ],
        )
    return match_id


def scrape_match(conn: sqlite3.Connection, url: str) -> int:
    """Fetch, parse and store one match. Returns the number of rounds stored."""
    main_html = fetch(url)
    econ_html = fetch(url.rstrip("/") + "/?game=all&tab=economy")
    parsed = parse_match(main_html, econ_html, url)

    rounds = sum(len(mp["rounds"]) for mp in parsed.maps)
    if rounds == 0:
        # forfeits and cancelled matches have no round data - not an error
        return 0

    with conn:
        insert_match(conn, parsed)
    return rounds


def crawl(pages: int, max_matches: int | None) -> None:
    db.init_db()
    conn = db.connect()
    seen = db.scraped_match_ids(conn)
    print(f"{len(seen)} matches already in database")

    stored = skipped = empty = failed = 0
    total_rounds = 0

    for page in range(1, pages + 1):
        try:
            urls = parse_match_list(fetch(RESULTS_URL.format(page=page)))
        except Exception as exc:
            print(f"[page {page}] listing failed: {exc}", file=sys.stderr)
            continue

        print(f"[page {page}] {len(urls)} matches")

        for url in urls:
            if max_matches is not None and stored >= max_matches:
                print("reached --max-matches")
                _summary(conn, stored, skipped, empty, failed, total_rounds)
                return

            try:
                mid = match_id_from_url(url)
            except ValueError:
                failed += 1
                continue

            if mid in seen:
                skipped += 1
                continue

            try:
                rounds = scrape_match(conn, url)
            except Exception:
                failed += 1
                print(f"  FAIL {url}", file=sys.stderr)
                traceback.print_exc(limit=1, file=sys.stderr)
                continue

            seen.add(mid)
            if rounds == 0:
                empty += 1
            else:
                stored += 1
                total_rounds += rounds
                print(f"  ok {mid} ({rounds} rounds)")

    _summary(conn, stored, skipped, empty, failed, total_rounds)


def _summary(conn, stored, skipped, empty, failed, total_rounds) -> None:
    db_rounds = conn.execute("SELECT COUNT(*) FROM rounds").fetchone()[0]
    print(
        f"\nstored={stored} skipped={skipped} empty={empty} failed={failed}\n"
        f"rounds this run={total_rounds}  rounds in database={db_rounds}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl VLR.gg match results.")
    ap.add_argument("--pages", type=int, default=5, help="results pages to walk")
    ap.add_argument("--max-matches", type=int, default=None, help="stop after N new matches")
    args = ap.parse_args()
    crawl(args.pages, args.max_matches)


if __name__ == "__main__":
    main()
