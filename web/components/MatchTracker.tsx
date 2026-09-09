"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MODEL, isOutOfDistribution } from "@/lib/model";
import { adviseBuyOrSave } from "@/lib/advice";
import {
  currentRound,
  estimateConfidence,
  estimateEconomy,
  matchResult,
  newMatch,
  score,
  youAreAttacking,
  type MatchState,
  type RoundOutcome,
} from "@/lib/economy";

const money = (n: number) => n.toLocaleString("en-US").replace(/,/g, " ");

// The watcher runs on your own machine, beside the game.
const WATCHER_URL = "http://127.0.0.1:8731";

const AUTO_STATUS: Record<"off" | "connecting" | "live" | "error", string> = {
  off: "you tap each round",
  connecting: "looking for the watcher...",
  live: "watching the scoreline",
  error: "watcher not running",
};

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
  const [auto, setAuto] = useState(false);
  const [autoStatus, setAutoStatus] = useState<"off" | "connecting" | "live" | "error">("off");
  // how many rounds from the watcher have already been applied to this match
  const appliedRef = useRef(0);

  const undo = () =>
    setMatch((prev) => (prev ? { ...prev, history: prev.history.slice(0, -1) } : prev));

  /**
   * Polls the local watcher, which reports round outcomes it saw on screen.
   *
   * The watcher is a dumb sensor: it says "won" or "lost" and nothing else.
   * All the match logic stays here, so the two cannot drift apart. It cannot
   * see a spike plant, so plant bonuses still need a tap - which is why the
   * plant buttons stay on screen in auto mode.
   */
  const pollWatcher = useCallback(async () => {
    try {
      const res = await fetch(`${WATCHER_URL}/state`, { cache: "no-store" });
      if (!res.ok) throw new Error(String(res.status));
      const data: { rounds: { outcome: string; planted: boolean }[] } = await res.json();
      setAutoStatus("live");

      const fresh = data.rounds.slice(appliedRef.current);
      if (fresh.length === 0) return;
      appliedRef.current = data.rounds.length;

      setMatch((prev) => {
        if (!prev) return prev;
        let next = prev;
        for (const seen of fresh) {
          if (matchResult(next)) break; // stop at match point
          if (seen.outcome !== "won" && seen.outcome !== "lost") continue;

          // A plant is recorded whoever made it. The watcher sees the spike go
          // down without knowing whose it was, and it does not need to: the
          // bonus goes to whichever side was attacking that round, which the
          // economy already works out from the round record. Dropping the flag
          // on defending rounds would quietly cost the enemy the $300 they
          // actually earned.
          const attacking = youAreAttacking(next);
          const outcome: RoundOutcome = seen.planted
            ? seen.outcome === "won"
              ? "won-planted"
              : "lost-planted"
            : (seen.outcome as RoundOutcome);

          next = {
            ...next,
            history: [
              ...next.history,
              { round: currentRound(next), outcome, youAttacking: attacking },
            ],
            enemyCreditsOverride: null,
            yourCreditsOverride: null,
          };
        }
        return next;
      });
    } catch {
      setAutoStatus("error");
    }
  }, []);

  useEffect(() => {
    if (!auto) {
      setAutoStatus("off");
      return;
    }
    setAutoStatus("connecting");
    void pollWatcher();
    const id = setInterval(() => void pollWatcher(), 2000);
    return () => clearInterval(id);
  }, [auto, pollWatcher]);

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
            onClick={() => {
              appliedRef.current = 0;
              void fetch(`${WATCHER_URL}/reset`, { method: "POST" }).catch(() => {});
              setMatch(newMatch(setupMap, setupAttacking));
            }}
          >
            START MATCH
          </button>
          <div className="muted">
            After each round, tap what happened. Both economies carry forward from the credit
            rules. Yours you can correct at a glance, since your credits are on your screen;
            theirs are never shown anywhere, so they stay an estimate.
          </div>
        </div>
      </section>
    );
  }

  const result = matchResult(match);
  if (result) {
    const won = result.winner === "you";
    return (
      <section className="panel">
        <div className="panel-head">
          <span>{match.map} &middot; final</span>
          <span>{result.wentToOvertime ? "overtime" : "regulation"}</span>
        </div>
        <div className="panel-body">
          <div className="verdict" style={{ borderColor: won ? "var(--def)" : "var(--atk)" }}>
            <div className="call" style={{ color: won ? "var(--def)" : "var(--atk)" }}>
              {won ? "Won" : "Lost"}
            </div>
            <div className="pct">
              {result.you} &ndash; {result.them}
              {result.wentToOvertime ? " in overtime" : ""}
            </div>
          </div>

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
              New match
            </button>
          </div>
          <div className="muted">
            Undo if you tapped the wrong result and the match ended early.
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
  const ood = isOutOfDistribution(round, eco.you, eco.them);

  const advice = adviseBuyOrSave({
    map: match.map,
    youCredits: eco.you,
    themCredits: eco.them,
    scoreYou: sc.you,
    scoreThem: sc.them,
    youAttacking: attacking,
  });

  // Updates go through the functional form because two taps landing before a
  // re-render would otherwise overwrite each other, silently dropping a round.
  // A dropped round corrupts every economy estimate after it.
  const record = (outcome: RoundOutcome) =>
    setMatch((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        history: [
          ...prev.history,
          { round: currentRound(prev), outcome, youAttacking: youAreAttacking(prev) },
        ],
        // a recorded round invalidates any manual correction
        enemyCreditsOverride: null,
        yourCreditsOverride: null,
      };
    });

  const nudgeEnemy = (delta: number) =>
    setMatch((prev) => {
      if (!prev) return prev;
      const current = estimateEconomy(prev).them;
      return {
        ...prev,
        enemyCreditsOverride: Math.max(0, Math.min(9000, current + delta)),
      };
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
            <div className="call">
              {ood ? "—" : advice.isPistolRound ? "Pistol" : advice.call}
            </div>
            <div className="pct">
              {ood ? (
                <>no reliable read on this state</>
              ) : advice.isPistolRound ? (
                <>
                  {Math.round(advice.probability * 100)}% to win &middot; everyone buys, so there
                  is nothing to decide
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

          {ood && (
            <div className="notice">
              <b>Off the map</b>
              <span>
                A pistol round with real money in it never happens, so the model has never seen
                this and any number it gave you would be invented. Check the credits above.
              </span>
            </div>
          )}

          <div className="econ">
            <div className="box">
              <span className="label">You</span>
              <input
                type="number"
                className="v"
                value={eco.you}
                min={0}
                max={9000}
                step={100}
                aria-label="Your credits"
                onChange={(e) => {
                  const v = Math.max(0, Math.min(9000, Number(e.target.value)));
                  setMatch((prev) => (prev ? { ...prev, yourCreditsOverride: v } : prev));
                }}
                style={{
                  color: "var(--def)",
                  background: "transparent",
                  border: "1px solid var(--line)",
                  padding: "2px 6px",
                  width: "100%",
                }}
              />
              <span className="muted">
                {advice.yourBracket} &middot;{" "}
                {match.yourCreditsOverride === null ? "estimated, type to correct" : "yours, exact"}
              </span>
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
          <span>{auto ? "Watching the scoreline" : "What happened last round?"}</span>
          <span>{attacking ? "you were attacking" : "you were defending"}</span>
        </div>
        <div className="panel-body">
          <div className="field">
            <div className="field-row">
              <span className="label">Record rounds</span>
              <span className="muted">{AUTO_STATUS[autoStatus]}</span>
            </div>
            <div className="seg">
              <button
                type="button"
                className="control"
                aria-pressed={!auto}
                onClick={() => setAuto(false)}
              >
                By hand
              </button>
              <button
                type="button"
                className="control"
                aria-pressed={auto}
                onClick={() => setAuto(true)}
              >
                Automatic
              </button>
            </div>
          </div>

          {auto && autoStatus === "error" && (
            <div className="notice">
              <b>Cannot reach the watcher</b>
              <span>
                Start it with <code>python -m watcher.run</code> in the project folder. If the
                page is open on the deployed site, use the local one instead - a page served
                over https is not allowed to talk to a program on your own machine.
              </span>
            </div>
          )}

          {auto && (
            <div className="muted">
              Rounds record themselves from the result banner, with the scoreline as a
              fallback. A spike going down is picked up from the timer, so plants are counted
              too - the buttons below stay for correcting anything it gets wrong.
            </div>
          )}

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
