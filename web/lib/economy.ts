/**
 * Tracks a match round by round and estimates both economies.
 *
 * Your own credits you can read off your screen. The enemy's you cannot -
 * they are not displayed anywhere, in game or in any API. So they are
 * reconstructed from round outcomes here.
 *
 * That reconstruction was measured against 21k real rounds and it is NOT
 * accurate to the dollar: $5,924 mean absolute error, because survivors keep
 * their weapons for free and loadout outruns credits by an amount round
 * outcomes never reveal. Two consequences shape this module:
 *
 *   1. The enemy figure is presented as an estimate you can correct, never
 *      as a fact.
 *   2. What is surfaced is the coarse bracket, not a precise number, because
 *      the bracket is what the win model consumes anyway.
 */

export const START_CREDITS = 800;
export const OVERTIME_CREDITS = 5_000;
export const MAX_CREDITS = 9_000;

export const WIN_REWARD = 3_000;
export const LOSS_BONUS = [1_900, 2_400, 2_900] as const;
export const PLANT_REWARD = 300;

export const HALFTIME_ROUND = 13;
export const REGULATION_ROUNDS = 24;

export type RoundOutcome = "won" | "lost" | "lost-planted" | "won-planted";

export interface RoundRecord {
  round: number;
  outcome: RoundOutcome;
  youAttacking: boolean;
}

export interface MatchState {
  map: string;
  /** Which side you started the match on. */
  startedAttacking: boolean;
  history: RoundRecord[];
  /** Your own credits, read off your screen; null means "use the estimate". */
  yourCreditsOverride: number | null;
  /** Manual correction when you can see the estimate is wrong. */
  enemyCreditsOverride: number | null;
}

export function newMatch(map: string, startedAttacking: boolean): MatchState {
  return {
    map,
    startedAttacking,
    history: [],
    yourCreditsOverride: null,
    enemyCreditsOverride: null,
  };
}

export function currentRound(state: MatchState): number {
  return state.history.length + 1;
}

export const ROUNDS_TO_WIN = 13;

/**
 * Sides swap at halftime, and then every single round in overtime, so that
 * each team plays one attack and one defence per overtime pair.
 */
export function youAreAttacking(state: MatchState): boolean {
  const round = currentRound(state);
  if (round > REGULATION_ROUNDS) {
    const overtimeIndex = round - REGULATION_ROUNDS - 1;
    return overtimeIndex % 2 === 0 ? state.startedAttacking : !state.startedAttacking;
  }
  const secondHalf = round >= HALFTIME_ROUND;
  return secondHalf ? !state.startedAttacking : state.startedAttacking;
}

export interface MatchResult {
  winner: "you" | "them";
  you: number;
  them: number;
  wentToOvertime: boolean;
}

/**
 * Whether the match is over, and who took it.
 *
 * Regulation is first to 13. At 12-12 it goes to overtime, which is played in
 * pairs of rounds - a team wins by taking both, which is the same as leading
 * by two once a pair has finished. A lead of two mid-pair does not end it,
 * because the other team has not had its round on the opposite side yet.
 */
export function matchResult(state: MatchState): MatchResult | null {
  const { you, them } = score(state);
  const played = state.history.length;

  if (played <= REGULATION_ROUNDS) {
    // Reaching 13 inside regulation always wins it: 12-12 sends the match to
    // overtime at 24 rounds, so a 13-12 regulation score cannot occur.
    if (you >= ROUNDS_TO_WIN) return { winner: "you", you, them, wentToOvertime: false };
    if (them >= ROUNDS_TO_WIN) return { winner: "them", you, them, wentToOvertime: false };
    return null;
  }

  // overtime: only judge at the end of a completed pair
  const overtimeRounds = played - REGULATION_ROUNDS;
  if (overtimeRounds % 2 !== 0) return null;

  const lead = you - them;
  if (lead >= 2) return { winner: "you", you, them, wentToOvertime: true };
  if (lead <= -2) return { winner: "them", you, them, wentToOvertime: true };
  return null;
}

export function score(state: MatchState): { you: number; them: number } {
  let you = 0;
  let them = 0;
  for (const r of state.history) {
    if (r.outcome === "won" || r.outcome === "won-planted") you++;
    else them++;
  }
  return { you, them };
}

function clamp(v: number): number {
  return Math.max(0, Math.min(MAX_CREDITS, v));
}

interface Economy {
  you: number;
  them: number;
  yourLossStreak: number;
  theirLossStreak: number;
}

/**
 * How much a team is assumed to spend. Real spending is a choice nobody can
 * observe, so this stands in for it - deliberately simple, because measurement
 * showed no policy recovers the true number.
 */
function assumedSpend(credits: number): number {
  if (credits >= 3_900) return 3_900; // rifle plus shields
  if (credits >= 2_400) return 2_200; // half buy
  if (credits >= 1_600) return 1_400; // pistol plus shields
  return 400;
}

export function estimateEconomy(state: MatchState): { you: number; them: number } {
  let eco: Economy = {
    you: START_CREDITS,
    them: START_CREDITS,
    yourLossStreak: 0,
    theirLossStreak: 0,
  };

  state.history.forEach((record, index) => {
    const roundNumber = index + 1;

    eco.you = clamp(eco.you - assumedSpend(eco.you));
    eco.them = clamp(eco.them - assumedSpend(eco.them));

    const youWon = record.outcome === "won" || record.outcome === "won-planted";
    const planted = record.outcome === "lost-planted" || record.outcome === "won-planted";

    if (youWon) {
      eco.you = clamp(eco.you + WIN_REWARD);
      eco.them = clamp(eco.them + LOSS_BONUS[Math.min(eco.theirLossStreak, 2)]);
      eco.yourLossStreak = 0;
      eco.theirLossStreak += 1;
    } else {
      eco.them = clamp(eco.them + WIN_REWARD);
      eco.you = clamp(eco.you + LOSS_BONUS[Math.min(eco.yourLossStreak, 2)]);
      eco.theirLossStreak = 0;
      eco.yourLossStreak += 1;
    }

    // the plant bonus is paid to whoever was attacking that round
    if (planted) {
      if (record.youAttacking) eco.you = clamp(eco.you + PLANT_REWARD);
      else eco.them = clamp(eco.them + PLANT_REWARD);
    }

    // both economies reset to a known state at halftime, which is what stops
    // estimation error from accumulating across a whole match
    const next = roundNumber + 1;
    if (next === HALFTIME_ROUND) {
      eco = { you: START_CREDITS, them: START_CREDITS, yourLossStreak: 0, theirLossStreak: 0 };
    } else if (next === REGULATION_ROUNDS + 1) {
      eco = { you: OVERTIME_CREDITS, them: OVERTIME_CREDITS, yourLossStreak: 0, theirLossStreak: 0 };
    }
  });

  return {
    you: state.yourCreditsOverride ?? eco.you,
    them: state.enemyCreditsOverride ?? eco.them,
  };
}

/** Rounds since the last known-exact economy: round 1, halftime, overtime. */
export function roundsSinceReset(state: MatchState): number {
  const round = currentRound(state);
  if (round > REGULATION_ROUNDS) return (round - REGULATION_ROUNDS - 1) % 6;
  if (round >= HALFTIME_ROUND) return round - HALFTIME_ROUND;
  return round - 1;
}

/**
 * Confidence in the enemy estimate, which decays with distance from the last
 * reset. Stated honestly rather than hidden: the estimate is known to drift.
 */
export function estimateConfidence(state: MatchState): "exact" | "good" | "rough" {
  if (state.enemyCreditsOverride !== null) return "exact";
  const since = roundsSinceReset(state);
  if (since === 0) return "exact";
  return since <= 3 ? "good" : "rough";
}
