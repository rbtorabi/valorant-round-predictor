"""Trains and evaluates the round win probability model.

Two things matter more than accuracy here:

* Splitting by MATCH, not by round. Rounds inside one match share teams, form
  and economy state, so a random round split leaks information across the
  boundary and flatters the score.
* Calibration. A model that says 70% should be right about 70% of the time.
  Brier score and a reliability table say whether it is; accuracy does not.

    python -m model.train
"""

import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import StandardScaler

from model.features import load, matrix


def report(name: str, y_true, p_pred) -> dict:
    return {
        "model": name,
        "brier": brier_score_loss(y_true, p_pred),
        "log_loss": log_loss(y_true, p_pred),
        "auc": roc_auc_score(y_true, p_pred),
        "accuracy": accuracy_score(y_true, (p_pred >= 0.5).astype(int)),
    }


def reliability(y_true, p_pred, bins: int = 10) -> None:
    """Does a stated probability match the observed frequency?"""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.digitize(p_pred, edges) - 1
    print(f"\n  {'predicted':>12} {'actual':>8} {'n':>7}   calibration")
    for b in range(bins):
        mask = idx == b
        if mask.sum() < 30:
            continue
        pred, actual = p_pred[mask].mean(), y_true[mask].mean()
        off = actual - pred
        bar = "#" * int(abs(off) * 100)
        print(f"  {pred:>11.0%} {actual:>8.0%} {mask.sum():>7,}   {bar} {off:+.0%}")


def main() -> None:
    df = load()
    X = matrix(df)
    y = df["y"].to_numpy()
    groups = df["match_id"].to_numpy()

    print(f"{len(df):,} rounds from {df['match_id'].nunique():,} matches")
    print(f"{X.shape[1]} features, attacker win rate {y.mean():.3f}")

    # hold out whole matches, never individual rounds
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=17)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    Xtr, Xte = X.iloc[train_idx], X.iloc[test_idx]
    ytr, yte = y[train_idx], y[test_idx]
    print(f"train {len(Xtr):,} rounds / test {len(Xte):,} rounds "
          f"({df.iloc[test_idx]['match_id'].nunique()} held-out matches)")

    rows = []

    base = DummyClassifier(strategy="prior").fit(Xtr, ytr)
    rows.append(report("baseline (always base rate)", yte, base.predict_proba(Xte)[:, 1]))

    scaler = StandardScaler().fit(Xtr)
    logit = LogisticRegression(max_iter=2000).fit(scaler.transform(Xtr), ytr)
    p_logit = logit.predict_proba(scaler.transform(Xte))[:, 1]
    rows.append(report("logistic regression", yte, p_logit))

    gbm = HistGradientBoostingClassifier(
        max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=17,
    ).fit(Xtr, ytr)
    p_gbm = gbm.predict_proba(Xte)[:, 1]
    rows.append(report("gradient boosting", yte, p_gbm))

    print(f"\n  {'model':<28} {'brier':>7} {'logloss':>8} {'auc':>6} {'acc':>6}")
    for r in rows:
        print(f"  {r['model']:<28} {r['brier']:>7.4f} {r['log_loss']:>8.4f} "
              f"{r['auc']:>6.3f} {r['accuracy']:>6.3f}")

    best = min(rows[1:], key=lambda r: r["brier"])
    print(f"\ncalibration of {best['model']}:")
    reliability(yte, p_gbm if best["model"].startswith("gradient") else p_logit)


if __name__ == "__main__":
    main()
