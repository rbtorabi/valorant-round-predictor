"use client";

import { useState } from "react";
import { MODEL } from "@/lib/model";
import { adviseBuyOrSave } from "@/lib/advice";
import {
  currentRound,
  estimateConfidence,
  estimateEconomy,
  newMatch,
  score,
  youAreAttacking,
  type MatchState,
  type RoundOutcome,
} from "@/lib/economy";

const money = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");

const CONFIDENCE_COPY: Record<ReturnType<typeof estimateConfidence>, string> = {
  exact: "known exactly",
  good: "estimate, close",
  rough: "estimate, drifting",
};

export default function MatchTracker() {
  const [match, setMatch] = useState<MatchState | null>(null);
  const [setupMap, setSetupMap] = useState(
    MODEL.maps.includes("Ascent") ? "Ascent" : MODEL.maps[0]
  );
  const [setupAttacking, setSetupAttacking] = useState(true);

  if (!match) {
    return (
      <section className="panel">
        <div className="panel-head">
          <span>Start a match</span>
          <span>round 1</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <span className="label">Map</span>
            <select value={setupMap} onChange={(e) => setSetupMap(e.target.value)}>
              {MODEL.maps.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <span className="label">You start</span>
            <div className="seg">
              <button
                type="button"
                className="control"
                aria-pressed={setupAttacking}
                onClick={() => setSetupAttacking(true)}
              >
                Attacking
              </button>
              <button
                type="button"
                className="control"
                aria-pressed={!setupAttacking}
                onClick={() => setSetupAttacking(false)}
              >
                Defending
              </button>
            </div>
          </div>
          <button
            type="button"
            className="control"
            style={{ padding: "14px", fontFamily: "var(--display)", letterSpacing: "0.1em" }}
            onClick={() => setMatch(newMatch(setupMap, setupAttacking))}
          >
            START MATCH
          </button>
          <div className="muted">
            After each round, tap what happened. Your economy and theirs are carried forward
            from the credit rules, so you never type a number again.
          </div>
        </div>
      </section>
    );
  }

  const round = currentRound(match);
  const attacking = youAreAttacking(match);
  const sc = score(match);
  const eco = estimateEconomy(match);
  const confidence = estimateConfidence(match);

  const advice = adviseBuyOrSave({
    map: match.map,
    youCredits: eco.you,
    themCredits: eco.them,
    scoreYou: sc.you,
    scoreThem: sc.them,
    youAttacking: attacking,
  });

  const record = (outcome: RoundOutcome) =>
    setMatch({
      ...match,
      history: [...match.history, { round, outcome, youAttacking: attacking }],
      // a recorded round invalidates any manual correction
      enemyCreditsOverride: null,
      yourCreditsOverride: null,
    });

  const undo = () =>
    setMatch({ ...match, history: match.history.slice(0, -1) });

  const nudgeEnemy = (delta: number) =>
    setMatch({
      ...match,
      enemyCreditsOverride: Math.max(0, Math.min(9000, eco.them + delta)),
    });

  return (
    <div className="glance">
      <section className="panel">
        <div className="panel-head">
          <span>
            {match.map} &middot; round {round} &middot; {attacking ? "attacking" : "defending"}
          </span>
          <span className="num">
            {sc.you} &ndash; {sc.them}
          </span>
        </div>

        <div className="panel-body">
          <div className="verdict">
            <div className="call">{advice.isPistolRound ? "Pistol" : advice.call}</div>
            <div className="pct">
              {advice.isPistolRound ? (
                <>
                  {Math.round(advice.probability * 100)}% to win &middot; both sides have $800,
                  so there is nothing to decide
                </>
              ) : (
                <>
                  {Math.round(advice.probability * 100)}% to win this round &middot;{" "}
                  {advice.call === "Buy"
                    ? advice.buyValue.toFixed(2)
                    : advice.saveValue.toFixed(2)}{" "}
                  expected over two
                </>
              )}
            </div>
          </div>

          <div className="econ">
            <div className="box">
              <span className="label">You</span>
              <span className="v" style={{ color: "var(--def)" }}>
                {money(eco.you)}
              </span>
              <span className="muted">{advice.yourBracket}</span>
            </div>
            <div className="box">
              <span className="label">Enemy</span>
              <span className="v" style={{ color: "var(--atk)" }}>
                {money(eco.them)}
              </span>
              <span className="muted">
                {advice.theirBracket} &middot; {CONFIDENCE_COPY[confidence]}
              </span>
            </div>
          </div>

          {confidence === "rough" && (
            <div className="notice">
              <b>Enemy figure is drifting</b>
              <span>
                Survivors carry weapons over for free, so their loadout can outrun their bank
                by an amount round results never reveal. If you saw what they were holding,
                correct it below. Halftime resets it to exact.
              </span>
            </div>
          )}

          <div className="field">
            <span className="label">Correct the enemy estimate</span>
            <div className="seg">
              <button type="button" className="control" onClick={() => nudgeEnemy(-1000)}>
                &minus;1000
              </button>
              <button type="button" className="control" onClick={() => nudgeEnemy(-500)}>
                &minus;500
              </button>
              <button type="button" className="control" onClick={() => nudgeEnemy(500)}>
                +500
              </button>
              <button type="button" className="control" onClick={() => nudgeEnemy(1000)}>
                +1000
              </button>
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <span>What happened last round?</span>
          <span>{attacking ? "you were attacking" : "you were defending"}</span>
        </div>
        <div className="panel-body">
          <div className="outcomes">
            <button type="button" className="win" onClick={() => record("won")}>
              Won
            </button>
            <button type="button" className="loss" onClick={() => record("lost")}>
              Lost
            </button>
            {attacking && (
              <>
                <button type="button" className="win" onClick={() => record("won-planted")}>
                  Won + planted
                </button>
                <button type="button" className="loss" onClick={() => record("lost-planted")}>
                  Lost + planted
                </button>
              </>
            )}
          </div>

          {match.history.length > 0 && (
            <>
              <div className="timeline" aria-label="round history">
                {match.history.map((r, i) => (
                  <i
                    key={i}
                    className={r.outcome.startsWith("won") ? "w" : "l"}
                    title={`Round ${r.round}: ${r.outcome}`}
                  />
                ))}
              </div>
              <div className="seg">
                <button type="button" className="control" onClick={undo}>
                  Undo last round
                </button>
                <button type="button" className="control" onClick={() => setMatch(null)}>
                  End match
                </button>
              </div>
            </>
          )}
        </div>
      </section>
    </div>
  );
}
