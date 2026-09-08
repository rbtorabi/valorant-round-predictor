"""Simulates each team's credits round by round.

This exists because enemy credits are the single feature the model leans on
hardest, and they are never observable - not on screen, not in any API. They
can only be reconstructed by replaying the economy rules over the round
history, which is the same arithmetic experienced players do in their heads.

Drift is bounded rather than unbounded: credits reset to a known 800 at the
start of each half, so any accumulated error is wiped at halftime and can
never span a whole match.

Unmodelled term: kill rewards. Each kill pays $200, so a round can swing a
team's bank by up to $1000 in a direction this simulator cannot see without
per-round kill data. `validate.py` measures how much that actually costs.
"""

from dataclasses import dataclass, field

START_CREDITS = 800
OVERTIME_CREDITS = 5_000
MAX_CREDITS = 9_000

WIN_REWARD = 3_000
LOSS_BONUS = (1_900, 2_400, 2_900)   # by consecutive losses, capped at the third
PLANT_REWARD = 300                   # to attackers, paid even in a loss
KILL_REWARD = 200

REGULATION_ROUNDS = 24
HALFTIME_ROUND = 13


@dataclass
class TeamEconomy:
    credits: int = START_CREDITS
    loss_streak: int = 0

    def loss_bonus(self) -> int:
        return LOSS_BONUS[min(self.loss_streak, len(LOSS_BONUS) - 1)]


@dataclass
class EconomySimulator:
    """Replays a match's rounds and tracks both teams' credits.

    Credits are per player. Spending is not modelled: what a team actually
    bought is unobservable, so `spend()` is called explicitly when a loadout
    value is known, and left alone otherwise.
    """

    atk: TeamEconomy = field(default_factory=TeamEconomy)
    deff: TeamEconomy = field(default_factory=TeamEconomy)
    round_num: int = 1

    def _clamp(self, value: int) -> int:
        return max(0, min(MAX_CREDITS, value))

    def reset_half(self, overtime: bool = False) -> None:
        start = OVERTIME_CREDITS if overtime else START_CREDITS
        self.atk = TeamEconomy(credits=start)
        self.deff = TeamEconomy(credits=start)

    def spend(self, atk_spend: int = 0, def_spend: int = 0) -> None:
        self.atk.credits = self._clamp(self.atk.credits - atk_spend)
        self.deff.credits = self._clamp(self.deff.credits - def_spend)

    def resolve(
        self,
        winner_side: str,
        *,
        planted: bool = False,
        atk_kills: int = 0,
        def_kills: int = 0,
    ) -> None:
        """Apply one round's outcome and advance to the next round."""
        if winner_side not in ("atk", "def"):
            raise ValueError(f"winner_side must be 'atk' or 'def', got {winner_side!r}")

        winner, loser = (self.atk, self.deff) if winner_side == "atk" else (self.deff, self.atk)

        winner.credits = self._clamp(winner.credits + WIN_REWARD)
        loser.credits = self._clamp(loser.credits + loser.loss_bonus())

        winner.loss_streak = 0
        loser.loss_streak += 1

        # attackers are paid for a plant whether or not they go on to win
        if planted:
            self.atk.credits = self._clamp(self.atk.credits + PLANT_REWARD)

        self.atk.credits = self._clamp(self.atk.credits + atk_kills * KILL_REWARD)
        self.deff.credits = self._clamp(self.deff.credits + def_kills * KILL_REWARD)

        self.round_num += 1

        # sides swap at halftime and both economies reset to a known state
        if self.round_num == HALFTIME_ROUND:
            self.reset_half()
            self.atk, self.deff = self.deff, self.atk
        elif self.round_num == REGULATION_ROUNDS + 1:
            self.reset_half(overtime=True)

    def state(self) -> dict:
        return {
            "round": self.round_num,
            "atk_credits": self.atk.credits,
            "def_credits": self.deff.credits,
            "atk_loss_streak": self.atk.loss_streak,
            "def_loss_streak": self.deff.loss_streak,
        }


def simulate_match(rounds: list[dict]) -> list[dict]:
    """Replay stored rounds, returning the predicted economy before each one.

    `rounds` are dicts as produced by the scraper, ordered by round number.
    """
    sim = EconomySimulator()
    predicted = []

    for r in rounds:
        predicted.append({
            "round_num": r["round_num"],
            "pred_atk_credits": sim.atk.credits,
            "pred_def_credits": sim.deff.credits,
        })
        # spending is inferred from what they fielded, when that is known
        sim.spend(
            atk_spend=min(sim.atk.credits, (r.get("atk_loadout") or 0) // 5),
            def_spend=min(sim.deff.credits, (r.get("def_loadout") or 0) // 5),
        )
        sim.resolve(
            r["winner_side"],
            planted=r.get("win_condition") in ("spike", "defuse"),
        )

    return predicted
