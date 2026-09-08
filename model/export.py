"""Exports the trained logistic model as JSON for in-browser inference.

Logistic regression won on Brier score, which has a useful consequence: the
whole model is a vector of coefficients. No ONNX runtime, no WASM bundle -
the browser computes a dot product and a sigmoid.

    python -m model.export
"""

import json
from pathlib import Path

from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from model.features import load, matrix

OUT = Path(__file__).resolve().parents[1] / "web" / "lib" / "model.json"


def main() -> None:
    df = load()
    X = matrix(df)
    y = df["y"].to_numpy()

    scaler = StandardScaler().fit(X)
    clf = LogisticRegression(max_iter=2000).fit(scaler.transform(X), y)

    payload = {
        "features": list(X.columns),
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": clf.coef_[0].tolist(),
        "intercept": float(clf.intercept_[0]),
        "trained_on": {
            "rounds": int(len(df)),
            "matches": int(df["match_id"].nunique()),
            "base_rate": float(y.mean()),
        },
        "maps": sorted(df["map_name"].dropna().unique().tolist()),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size:,} bytes)")
    print(f"{len(payload['features'])} features, {payload['trained_on']['rounds']:,} rounds")

    print("\nlargest effects (standardised):")
    ranked = sorted(zip(payload["features"], payload["coef"]), key=lambda kv: -abs(kv[1]))
    for name, c in ranked[:8]:
        print(f"  {name:<28} {c:+.3f}")


if __name__ == "__main__":
    main()
