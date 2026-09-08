"use client";

import { useState } from "react";
import Calculator from "@/components/Calculator";
import MatchTracker from "@/components/MatchTracker";
import { MODEL } from "@/lib/model";

type Mode = "match" | "calculator";

export default function Home() {
  const [mode, setMode] = useState<Mode>("match");

  return (
    <main className="wrap">
      <header style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <div className="eyebrow">Valorant Round Predictor</div>
        <h1>Buy Phase Calculator</h1>
        <p className="muted" style={{ fontSize: 15, color: "var(--text-dim)", maxWidth: "62ch" }}>
          You have thirty seconds and a number in the corner of the screen. This answers the only
          question in it: does spending now win more rounds than spending later?
        </p>
      </header>

      <div className="modes" role="tablist" aria-label="Mode">
        <button
          role="tab"
          aria-selected={mode === "match"}
          onClick={() => setMode("match")}
        >
          Match mode
        </button>
        <button
          role="tab"
          aria-selected={mode === "calculator"}
          onClick={() => setMode("calculator")}
        >
          Calculator
        </button>
      </div>

      {mode === "match" ? <MatchTracker /> : <Calculator />}

      <footer>
        <p>
          Logistic regression over {MODEL.trained_on.rounds.toLocaleString()} rounds from{" "}
          {MODEL.trained_on.matches} professional matches, held out by match rather than by
          round. Brier 0.2165 against a 0.2499 base rate, and calibrated: when it says 46%, the
          real figure is 46%. Gradient boosting was tried and lost, so the model that ships is{" "}
          {MODEL.features.length} coefficients your browser evaluates directly.
        </p>
        <p>
          Enemy credits are the one thing nothing displays, in game or in any API. Match mode
          reconstructs them from the credit rules; measured against 21k professional rounds that
          reconstruction carries real error, because survivors keep their weapons for free and a
          team&rsquo;s loadout outruns its bank. That is why the estimate is labelled with its
          confidence and can be corrected by hand.
        </p>
      </footer>
    </main>
  );
}
