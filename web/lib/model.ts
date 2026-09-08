import modelJson from "./model.json";

/**
 * The trained model, exported from scikit-learn.
 *
 * Logistic regression beat gradient boosting on Brier score, so the whole
 * model is a coefficient vector: standardise the features, take a dot
 * product, apply a sigmoid. No runtime, no WASM, about 2KB.
 */
export interface TrainedModel {
  features: string[];
  mean: number[];
  scale: number[];
  coef: number[];
  intercept: number;
  maps: string[];
  trained_on: { rounds: number; matches: number; base_rate: number };
}

export const MODEL = modelJson as TrainedModel;

export const TEAM_SIZE = 5;

export type Bracket = "eco" | "semi-eco" | "semi-buy" | "full-buy";

/** VLR's own bucketing, on team loadout value. */
export function bracket(loadout: number): Bracket {
  if (loadout < 5_000) return "eco";
  if (loadout < 10_000) return "semi-eco";
  if (loadout < 20_000) return "semi-buy";
  return "full-buy";
}

/**
 * Credits are per player everywhere in the UI, because that is the number a
 * player actually sees. The model works in team loadout value.
 *
 * The conversion is approximate on purpose: survivors carry weapons over for
 * free, so a team's loadout can exceed what its credits would buy. That gap
 * is exactly what defeated the economy simulator, and it is why enemy
 * economy is shown as an estimate rather than a fact.
 */
export function creditsToLoadout(creditsPerPlayer: number): number {
  return creditsPerPlayer * TEAM_SIZE;
}

export interface RoundState {
  map: string;
  atkLoadout: number;
  defLoadout: number;
  atkScore: number;
  defScore: number;
}

/** Probability that the attacking side wins this round. */
export function predictAttackerWin(state: RoundState): number {
  const round = state.atkScore + state.defScore + 1;

  const f: Record<string, number> = {
    round_num: round,
    atk_loadout: state.atkLoadout,
    def_loadout: state.defLoadout,
    loadout_diff: state.atkLoadout - state.defLoadout,
    loadout_ratio: state.atkLoadout / Math.max(1, state.defLoadout),
    atk_score_pre: state.atkScore,
    def_score_pre: state.defScore,
    score_diff: state.atkScore - state.defScore,
    is_pistol: round === 1 || round === 13 ? 1 : 0,
  };
  f[`map_name_${state.map}`] = 1;
  f[`atk_buy_${bracket(state.atkLoadout)}`] = 1;
  f[`def_buy_${bracket(state.defLoadout)}`] = 1;

  let z = MODEL.intercept;
  for (let i = 0; i < MODEL.features.length; i++) {
    const v = f[MODEL.features[i]] ?? 0;
    z += ((v - MODEL.mean[i]) / MODEL.scale[i]) * MODEL.coef[i];
  }
  return 1 / (1 + Math.exp(-z));
}

/**
 * A pistol round with real money in it never happens, so the model would be
 * extrapolating. Worth saying so rather than printing a confident number.
 */
export function isOutOfDistribution(
  round: number,
  atkCredits: number,
  defCredits: number
): boolean {
  return (round === 1 || round === 13) && (atkCredits > 1_500 || defCredits > 1_500);
}
