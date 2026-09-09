"""Turns screen changes into round outcomes.

The whole detector rests on one observation: you do not need to know what the
score says, only that it changed. When the left number's pixels change, your
team scored; when the right number's do, theirs did. That sidesteps OCR, fonts,
resolutions and localisation entirely.

Two things stop it from firing on noise:

* a change must move a meaningful fraction of the region, not a few pixels, so
  antialiasing and compression flicker are ignored;
* a score cannot change twice inside the debounce window, because a Valorant
  round cannot end twice in twenty seconds.
"""

import time
from dataclasses import dataclass, field

import numpy as np


@dataclass
class RegionWatcher:
    """Notices when one region stops looking like it did before."""

    pixel_threshold: int
    change_fraction: float
    debounce_seconds: float

    _previous: np.ndarray | None = field(default=None, repr=False)
    # None means "never fired". Starting this at 0.0 would compare the first
    # detection against time zero, which silently swallows it on a machine
    # whose monotonic clock is still small - a recent reboot, for instance.
    _last_fired: float | None = field(default=None, repr=False)

    def changed(self, frame: np.ndarray, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        previous, self._previous = self._previous, frame

        if previous is None or previous.shape != frame.shape:
            return False

        diff = np.abs(frame.astype(np.int16) - previous.astype(np.int16))
        moved = float((diff > self.pixel_threshold).mean())
        if moved < self.change_fraction:
            return False

        if self._last_fired is not None and now - self._last_fired < self.debounce_seconds:
            return False

        self._last_fired = now
        return True


@dataclass
class RoundDetector:
    """Watches both score numbers and reports who won when one moves."""

    pixel_threshold: int = 40
    change_fraction: float = 0.04
    debounce_seconds: float = 20.0

    def __post_init__(self) -> None:
        kwargs = dict(
            pixel_threshold=self.pixel_threshold,
            change_fraction=self.change_fraction,
            debounce_seconds=self.debounce_seconds,
        )
        self.ally = RegionWatcher(**kwargs)
        self.enemy = RegionWatcher(**kwargs)

    def update(
        self,
        ally_frame: np.ndarray,
        enemy_frame: np.ndarray,
        now: float | None = None,
    ) -> str | None:
        """Returns 'won', 'lost', or None if nothing happened."""
        now = time.monotonic() if now is None else now
        ally_changed = self.ally.changed(ally_frame, now)
        enemy_changed = self.enemy.changed(enemy_frame, now)

        # Both at once means something moved that is not a score - a scoreboard
        # overlay, a resolution change, alt-tabbing. Better to report nothing
        # than to invent a round.
        if ally_changed and enemy_changed:
            return None
        if ally_changed:
            return "won"
        if enemy_changed:
            return "lost"
        return None
