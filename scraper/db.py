"""SQLite schema and helpers for scraped VLR.gg match data.

One row per round is the training unit. Everything above it (match, map)
exists so a round can be traced back to its source and re-scraped without
duplicating work.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "valorant.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id            INTEGER PRIMARY KEY,
    vlr_match_id  TEXT UNIQUE NOT NULL,
    url           TEXT NOT NULL,
    event         TEXT,
    series        TEXT,
    played_at     TEXT,
    team_a        TEXT,
    team_b        TEXT,
    scraped_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS maps (
    id            INTEGER PRIMARY KEY,
    match_id      INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    map_name      TEXT NOT NULL,
    map_index     INTEGER NOT NULL,
    score_a       INTEGER,
    score_b       INTEGER,
    UNIQUE (match_id, map_index)
);

-- The training table. `winner_side` is the label; every other column must be
-- knowable BEFORE the round starts, or it is leakage.
CREATE TABLE IF NOT EXISTS rounds (
    id             INTEGER PRIMARY KEY,
    map_id         INTEGER NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    round_num      INTEGER NOT NULL,
    atk_team       TEXT NOT NULL,
    def_team       TEXT NOT NULL,
    atk_score_pre  INTEGER NOT NULL,
    def_score_pre  INTEGER NOT NULL,
    atk_buy        TEXT,   -- eco | semi-eco | semi-buy | full-buy
    def_buy        TEXT,
    atk_credits    INTEGER,
    def_credits    INTEGER,
    winner_side    TEXT NOT NULL CHECK (winner_side IN ('atk', 'def')),
    win_condition  TEXT,   -- elim | spike | defuse | time
    UNIQUE (map_id, round_num)
);

CREATE INDEX IF NOT EXISTS idx_rounds_map ON rounds(map_id);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(path: Path = DB_PATH) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def scraped_match_ids(conn: sqlite3.Connection) -> set[str]:
    """Used to make scraping resumable across runs."""
    rows = conn.execute("SELECT vlr_match_id FROM matches").fetchall()
    return {r["vlr_match_id"] for r in rows}


if __name__ == "__main__":
    init_db()
    print(f"initialized {DB_PATH}")
