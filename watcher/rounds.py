"""Decides that a round ended, from whichever evidence is available.

Two independent signals, in order of trust:

1. The result banner. It says WON or LOST outright, so there is nothing to
   infer. This is the primary source.
2. The scoreline changing. Weaker, because it only tells us a number moved
   and we work out the rest, but it still fires when the banner was missed -
   a dropped frame, an unusual message, a template we have not collected.

Both feed one debounce, so a round that trips both is still one round. A
Valorant round cannot end twice in twenty seconds, which makes that safe.

Alongside them the timer is watched for the spike being down. That is not a
round signal - it decides whether the round carried a plant, which is worth
$300 to the attacking side and is otherwise invisible in the result.
"""

import time
from dataclasses import dataclass, field

import numpy as np

from watcher.banner import classify
from watcher.detect import RoundDetector
from watcher.spike import PlantWatcher

RESULT_BANNERS = {"won": "won", "lost": "lost"}


@dataclass
class RoundSource:
    """Combines the banner reader and the score watcher into one verdict."""

    change_fraction: float = 0.25
    debounce_seconds: float = 20.0
    stable_frames: int = 3

    _score: RoundDetector = field(init=False, repr=False)
    _last_emit: float | None = field(default=None, repr=False)
    _last_banner: str | None = field(default=None, repr=False)
    # whether the spike went down at any point in the round being played
    _planted_this_round: bool = field(default=False, repr=False)
    _plant: PlantWatcher = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._plant = PlantWatcher()
        self._score = RoundDetector(
            change_fraction=self.change_fraction,
            # the shared debounce below is what actually spaces rounds out
            debounce_seconds=0.0,
            stable_frames=self.stable_frames,
        )

    def _debounced(self, now: float) -> bool:
        return self._last_emit is not None and now - self._last_emit < self.debounce_seconds

    def update(
        self,
        ally_frame: np.ndarray,
        enemy_frame: np.ndarray,
        banner_frame: np.ndarray | None = None,
        timer_frame: np.ndarray | None = None,
        now: float | None = None,
    ) -> tuple[str, str, bool] | None:
        """Returns (outcome, source, planted) or None.

        `source` is 'banner' or 'score'. `planted` says whether the spike was
        down at any point during the round that just ended.
        """
        now = time.monotonic() if now is None else now

        # A plant seen anywhere in the round counts, so this latches until the
        # round is reported and then resets. The watcher underneath insists the
        # timer stays red for several samples, because a single red frame
        # turned out to be something else entirely on a red-lit map.
        if timer_frame is not None and self._plant.update(timer_frame):
            self._planted_this_round = True

        banner_label = None
        if banner_frame is not None:
            banner_label, _ = classify(banner_frame)

        # the banner persists for several seconds, so only act on its arrival
        arrived = banner_label != self._last_banner
        self._last_banner = banner_label

        score_outcome = self._score.update(ally_frame, enemy_frame, now=now)

        if self._debounced(now):
            return None

        if arrived and banner_label in RESULT_BANNERS:
            return self._emit(RESULT_BANNERS[banner_label], "banner", now)

        if score_outcome:
            return self._emit(score_outcome, "score", now)

        return None

    def _emit(self, outcome: str, source: str, now: float) -> tuple[str, str, bool]:
        planted = self._planted_this_round
        self._planted_this_round = False
        self._plant.reset()
        self._last_emit = now
        return outcome, source, planted
