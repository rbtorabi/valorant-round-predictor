"""Simulates each team's credits round by round.

This exists because enemy credits are the single feature the model leans on
hardest, and they are never observable - not on screen, not in any API. They
can only be reconstructed by replaying the economy rules over the round
history, which is the same arithmetic experienced players do in their heads.

Drift is bounded rather than unbounded: credits reset to a known 800 at the
start of each half, so any accumulated error is wiped at halftime and can
never span a whole match.

MEASURED RESULT (21k rounds, 831 maps): this does not work well enough to
drive dollar-level advice, and the failure is structural rather than a matter
of tuning.

    mean absolute error   $5,924
    buy-bracket accuracy  35.1%  vs a 57.8% majority-class baseline

Three things defeat it, in order of severity:

1. Weapon carry-over. Survivors keep their guns for free, so a team holding
   $15k in credits can field a $25k loadout. Credits and loadout are simply
   different quantities, and the gap depends on who lived - which round
   outcomes do not tell you.
2. Spending is a choice. Two teams with identical credits and identical
   histories buy differently.
3. Kills pay $200 each, up to $1000 a round, invisibly.

The bias is systematic and one-directional: the simulator underestimates,
guessing semi-buy for 18,270 rounds that were actually full buys - exactly
what carry-over predicts.

What this means for the project: an automatic live tool cannot estimate enemy
economy from win/loss alone. It needs survivor counts per round, which are
visible on the round-end screen and therefore readable, plus kill counts. The
training pipeline is unaffected, because VLR reports real loadout values.

Kept rather than deleted: the measurement is the point, and it is what says
which inputs the live version actually requires.
"""

from dataclasses import dataclass, field

# Everything here is in TEAM credits - five players' worth - because that is
# the unit VLR reports, and comparing against it in per-player credits was the
# bug that made the first version of this look uncorrelated.
TEAM = 5

START_CREDITS = 800 * TEAM        # 4,000
OVERTIME_CREDITS = 5_000 * TEAM   # 25,000
MAX_CREDITS = 9_000 * TEAM        # 45,000

WIN_REWARD = 3_000 * TEAM
LOSS_BONUS = (1_900 * TEAM, 2_400 * TEAM, 2_900 * TEAM)
PLANT_REWARD = 300 * TEAM         # to attackers, paid even in a loss
KILL_REWARD = 200                 # per kill, not per team

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


def buy_policy(credits: int) -> int:
    """How much a team is assumed to spend, given what it has.

    Real spending is unobservable, so this stands in for it: teams full-buy
    when they comfortably can, save hard when they clearly cannot, and force
    in between. Deliberately crude - `validate.py` measures what it costs.
    """
    if credits >= 20_000:          # comfortable full buy
        return int(credits * 0.85)
    if credits >= 12_000:          # force or half buy
        return int(credits * 0.75)
    return int(credits * 0.35)     # save, keeping most of it back


def simulate_match(rounds: list[dict]) -> list[dict]:
    """Replay stored rounds, returning the predicted economy before each one.

    `rounds` are dicts as produced by the scraper, ordered by round number.
    """
    sim = EconomySimulator()
    predicted = []

    for r in rounds:
        # what a team can field this round, before it spends anything
        pre_atk, pre_def = sim.atk.credits, sim.deff.credits
        # Spending cannot be read off loadout value, because survivors carry
        # weapons into the next round for free - loadout overstates spend by
        # whatever the team kept. So spend is modelled by policy instead.
        sim.spend(
            atk_spend=buy_policy(sim.atk.credits),
            def_spend=buy_policy(sim.deff.credits),
        )
        # bank is what VLR records: money left AFTER buying
        predicted.append({
            "round_num": r["round_num"],
            # pre-buy: comparable to loadout value / buy bracket
            "pred_atk_pre": pre_atk,
            "pred_def_pre": pre_def,
            # post-buy: comparable to VLR's bank figure
            "pred_atk_credits": sim.atk.credits,
            "pred_def_credits": sim.deff.credits,
        })
        sim.resolve(
            r["winner_side"],
            planted=r.get("win_condition") in ("spike", "defuse"),
        )

    return predicted
