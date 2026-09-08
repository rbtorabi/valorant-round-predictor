"""Turns stored rounds into a leakage-safe training frame.

Every column here must be knowable while the buy phase is still running. The
label is the only thing from the round itself. In particular `atk_score_pre`
and `def_score_pre` are the score *before* the round, which is why the scraper
stores them that way rather than deriving them afterwards.
"""

import pandas as pd

from scraper import db

QUERY = """
    SELECT
        r.map_id,
        mp.match_id,
        mp.map_name,
        r.round_num,
        r.atk_score_pre,
        r.def_score_pre,
        r.atk_loadout,
        r.def_loadout,
        r.atk_buy,
        r.def_buy,
        r.winner_side
    FROM rounds r
    JOIN maps mp ON r.map_id = mp.id
    WHERE r.atk_loadout IS NOT NULL
      AND r.def_loadout IS NOT NULL
      AND mp.map_name IS NOT NULL
"""

NUMERIC = [
    "round_num",
    "atk_loadout",
    "def_loadout",
    "loadout_diff",
    "loadout_ratio",
    "atk_score_pre",
    "def_score_pre",
    "score_diff",
    "is_pistol",
]
CATEGORICAL = ["map_name", "atk_buy", "def_buy"]


def load() -> pd.DataFrame:
    conn = db.connect()
    df = pd.read_sql_query(QUERY, conn)

    df["loadout_diff"] = df["atk_loadout"] - df["def_loadout"]
    # ratio captures "twice as rich" separately from "richer by $10k"
    df["loadout_ratio"] = df["atk_loadout"] / df["def_loadout"].clip(lower=1)
    df["score_diff"] = df["atk_score_pre"] - df["def_score_pre"]
    # pistol rounds have a fixed economy and their own dynamics
    df["is_pistol"] = df["round_num"].isin([1, 13]).astype(int)

    df["y"] = (df["winner_side"] == "atk").astype(int)
    return df


def matrix(df: pd.DataFrame) -> pd.DataFrame:
    """One-hot encoded design matrix."""
    return pd.get_dummies(df[NUMERIC + CATEGORICAL], columns=CATEGORICAL, drop_first=False)
