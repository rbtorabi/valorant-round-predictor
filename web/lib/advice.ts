import { bracket, creditsToLoadout, predictAttackerWin, type Bracket } from "./model";
import { LOSS_BONUS, MAX_CREDITS, WIN_REWARD } from "./economy";

export interface Situation {
  map: string;
  youCredits: number;
  themCredits: number;
  scoreYou: number;
  scoreThem: number;
  youAttacking: boolean;
}

/** Probability that YOU win this round, whichever side you are on. */
export function yourWinProbability(s: Situation): number {
  const attackerWins = predictAttackerWin({
    map: s.map,
    atkLoadout: creditsToLoadout(s.youAttacking ? s.youCredits : s.themCredits),
    defLoadout: creditsToLoadout(s.youAttacking ? s.themCredits : s.youCredits),
    atkScore: s.youAttacking ? s.scoreYou : s.scoreThem,
    defScore: s.youAttacking ? s.scoreThem : s.scoreYou,
  });
  return s.youAttacking ? attackerWins : 1 - attackerWins;
}

export interface Advice {
  probability: number;
  buyValue: number;
  saveValue: number;
  call: "Buy" | "Save";
  margin: number;
  yourBracket: Bracket;
  theirBracket: Bracket;
  /**
   * Pistol rounds hand both sides the same $800 and everyone buys. There is
   * no decision to advise, so the call is suppressed rather than dressed up
   * as one.
   */
  isPistolRound: boolean;
}

const clamp = (v: number) => Math.max(0, Math.min(MAX_CREDITS, v));

/**
 * Compares buying now against saving, over this round and the next.
 *
 * Two rounds is the horizon the decision actually spans: saving concedes this
 * round more often, but banks a loss bonus and a full loadout for the next
 * one. Judging it on this round alone would always say buy.
 */
export function adviseBuyOrSave(s: Situation): Advice {
  const round = s.scoreYou + s.scoreThem + 1;
  const lossStreak = Math.min(2, Math.max(0, s.scoreThem - s.scoreYou));
  const bonus = LOSS_BONUS[lossStreak];

  const next = (youCredits: number, wonThisRound: boolean): Situation => ({
    ...s,
    youCredits,
    scoreYou: s.scoreYou + (wonThisRound ? 1 : 0),
    scoreThem: s.scoreThem + (wonThisRound ? 0 : 1),
  });

  // buying: spend now, so next round rests on the reward alone
  const buyNow = yourWinProbability(s);
  const buyNext =
    buyNow * yourWinProbability(next(clamp(WIN_REWARD), true)) +
    (1 - buyNow) * yourWinProbability(next(clamp(bonus), false));

  // saving: field almost nothing now, carry the credits plus the bonus forward
  const saveNow = yourWinProbability({ ...s, youCredits: 800 });
  const saved = clamp(s.youCredits + bonus);
  const saveNext =
    saveNow * yourWinProbability(next(clamp(saved + WIN_REWARD), true)) +
    (1 - saveNow) * yourWinProbability(next(saved, false));

  const buyValue = buyNow + buyNext;
  const saveValue = saveNow + saveNext;

  return {
    probability: buyNow,
    buyValue,
    saveValue,
    call: buyValue >= saveValue ? "Buy" : "Save",
    margin: Math.abs(buyValue - saveValue),
    yourBracket: bracket(creditsToLoadout(s.youCredits)),
    theirBracket: bracket(creditsToLoadout(s.themCredits)),
    isPistolRound: round === 1 || round === 13,
  };
}
