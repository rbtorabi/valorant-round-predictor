"use client";

import { useState } from "react";
import { MODEL, isOutOfDistribution } from "@/lib/model";
import { adviseBuyOrSave } from "@/lib/advice";

const money = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");

export default function Calculator() {
  const [map, setMap] = useState(MODEL.maps.includes("Ascent") ? "Ascent" : MODEL.maps[0]);
  const [youAttacking, setYouAttacking] = useState(true);
  const [youCredits, setYouCredits] = useState(800);
  const [themCredits, setThemCredits] = useState(800);
  const [scoreYou, setScoreYou] = useState(0);
  const [scoreThem, setScoreThem] = useState(0);

  const round = scoreYou + scoreThem + 1;
  const advice = adviseBuyOrSave({
    map,
    youCredits,
    themCredits,
    scoreYou,
    scoreThem,
    youAttacking,
  });
  const pct = Math.round(advice.probability * 100);
  const ood = isOutOfDistribution(round, youCredits, themCredits);

  const step = (setter: (fn: (v: number) => number) => void, delta: number) =>
    setter((v) => Math.max(0, Math.min(24, v + delta)));

  return (
    <div className="grid2">
      <section className="panel">
        <div className="panel-head">
          <span>Round state</span>
          <span>Round {round}</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <span className="label">Map</span>
            <select value={map} onChange={(e) => setMap(e.target.value)}>
              {MODEL.maps.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div className="field">
            <span className="label">Your side</span>
            <div className="seg">
              <button
                type="button"
                className="control"
                aria-pressed={youAttacking}
                onClick={() => setYouAttacking(true)}
              >
                Attacking
              </button>
              <button
                type="button"
                className="control"
                aria-pressed={!youAttacking}
                onClick={() => setYouAttacking(false)}
              >
                Defending
              </button>
            </div>
          </div>

          <div className="field">
            <div className="field-row">
              <span className="label">Score</span>
              <span className="num">
                {scoreYou} &ndash; {scoreThem}
              </span>
            </div>
            <div className="grid2">
              <div className="seg">
                <button type="button" className="control" onClick={() => step(setScoreYou, -1)}>
                  &minus;
                </button>
                <button type="button" className="control" onClick={() => step(setScoreYou, 1)}>
                  +
                </button>
              </div>
              <div className="seg">
                <button type="button" className="control" onClick={() => step(setScoreThem, -1)}>
                  &minus;
                </button>
                <button type="button" className="control" onClick={() => step(setScoreThem, 1)}>
                  +
                </button>
              </div>
            </div>
            <div className="muted">Left adjusts your rounds, right adjusts theirs.</div>
          </div>

          <div className="field">
            <div className="field-row">
              <span className="label">Your credits</span>
              <span className="num">
                {money(youCredits)}
                <span className="tag">{advice.yourBracket}</span>
              </span>
            </div>
            <input
              type="range"
              min={800}
              max={9000}
              step={100}
              value={youCredits}
              onChange={(e) => setYouCredits(Number(e.target.value))}
            />
          </div>

          <div className="field">
            <div className="field-row">
              <span className="label">Enemy credits</span>
              <span className="num">
                {money(themCredits)}
                <span className="tag">{advice.theirBracket}</span>
              </span>
            </div>
            <input
              type="range"
              min={800}
              max={9000}
              step={100}
              value={themCredits}
              onChange={(e) => setThemCredits(Number(e.target.value))}
            />
            <div className="muted">
              Not shown anywhere in game. Match mode estimates this for you from the round
              history instead.
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <span>Prediction</span>
          <span>{youAttacking ? "attacking" : "defending"}</span>
        </div>
        <div className="panel-body">
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <div
              className="num"
              style={{
                fontFamily: "var(--display)",
                fontSize: "clamp(52px, 11vw, 78px)",
                lineHeight: 0.85,
                fontWeight: 700,
                color: youAttacking ? "var(--atk)" : "var(--def)",
              }}
            >
              {pct}%
            </div>
            <div className="label" style={{ maxWidth: "12ch" }}>
              chance you win this round
            </div>
          </div>

          <div className="oddsbar" aria-hidden="true">
            <span
              style={{
                flexBasis: `${pct}%`,
                background: youAttacking ? "var(--atk)" : "var(--def)",
              }}
            >
              YOU
            </span>
            <span
              style={{
                flexBasis: `${100 - pct}%`,
                background: youAttacking ? "var(--def)" : "var(--atk)",
                justifyContent: "flex-end",
              }}
            >
              THEM
            </span>
          </div>

          {ood && (
            <div className="notice">
              <b>Extrapolation</b>
              <span>
                Pistol rounds always start at $800, so this combination never occurs in the
                training data. Treat the figure above as unreliable.
              </span>
            </div>
          )}

          <div className="grid2">
            <div className="panel" style={{ padding: 14 }}>
              <div className="label">Buy now</div>
              <div className="num" style={{ fontSize: 26, fontWeight: 600 }}>
                {advice.buyValue.toFixed(2)}
              </div>
              <div className="muted">rounds expected over the next two</div>
            </div>
            <div className="panel" style={{ padding: 14 }}>
              <div className="label">Save</div>
              <div className="num" style={{ fontSize: 26, fontWeight: 600 }}>
                {advice.saveValue.toFixed(2)}
              </div>
              <div className="muted">rounds expected over the next two</div>
            </div>
          </div>

          <div className="notice">
            <b>{advice.isPistolRound ? "Pistol round" : advice.call}</b>
            <span>
              {advice.isPistolRound
                ? "Both sides start on $800 and everyone buys, so there is no buy-or-save decision to make here."
                : `Worth about ${advice.margin.toFixed(2)} more rounds across this round and the next. Saving concedes now to bank a loss bonus and a full loadout, which is why the comparison spans two rounds rather than one.`}
            </span>
          </div>
        </div>
      </section>
    </div>
  );
}
