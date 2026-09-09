"""Turns screen changes into round outcomes.

The idea is that you never need to read the score, only notice it changed. If
the left number changes you scored; if the right one does, they did. That
avoids OCR, fonts, digit templates, resolutions and localisation entirely.

The complication is that Valorant's scoreline is drawn over the live 3D world,
so the raw pixels behind the digits change every time you move the mouse. A
plain image diff would fire constantly. So each frame is first reduced to a
mask of just the bright glyph pixels - the numerals are near-white, the world
behind them is mid-tone - and it is those masks that get compared. Turning the
camera changes the background; it does not change the shape of the numeral.

Three further guards, each for a failure seen in real footage:

* a new shape must hold for several consecutive samples, so a muzzle flash or
  a flashbang cannot pass as a score change;
* a frame where too much of the region is bright is discarded as unreadable,
  which is what a flashbang actually looks like;
* a score cannot change twice inside the debounce window, because a Valorant
  round cannot end twice in twenty seconds.
"""

import time
from dataclasses import dataclass, field

import numpy as np

# Above this, a pixel is glyph rather than world. The numerals are drawn
# near-white over a mid-tone bar; measured separation is wide.
BRIGHT_THRESHOLD = 235.0

# If more of the region than this is bright, it is not a numeral on a bar -
# it is a flashbang, a white wall, or the scoreboard overlay. Unreadable.
MAX_BRIGHT_FRACTION = 0.25


def glyph_mask(frame: np.ndarray, threshold: float = BRIGHT_THRESHOLD) -> np.ndarray | None:
    """Just the bright pixels, or None when the frame cannot be trusted."""
    mask = frame > threshold
    if mask.mean() > MAX_BRIGHT_FRACTION:
        return None
    return mask


def shape_difference(a: np.ndarray, b: np.ndarray) -> float:
    """How much two glyph masks disagree, relative to how much ink they hold."""
    ink = int(a.sum()) + int(b.sum())
    if ink == 0:
        return 0.0
    return float(np.logical_xor(a, b).sum()) / ink


@dataclass
class RegionWatcher:
    """Notices when the numeral in one region becomes a different numeral."""

    change_fraction: float = 0.25
    debounce_seconds: float = 20.0
    stable_frames: int = 3

    _confirmed: np.ndarray | None = field(default=None, repr=False)
    _candidate: np.ndarray | None = field(default=None, repr=False)
    _candidate_seen: int = field(default=0, repr=False)
    # how far the current frame sits from what we last believed, kept so the
    # two regions can be compared when both look like they moved
    last_difference: float = field(default=0.0, repr=False)
    # None means "never fired"; starting at 0.0 would compare the first
    # detection against time zero and swallow it on a freshly booted machine.
    _last_fired: float | None = field(default=None, repr=False)

    def changed(self, frame: np.ndarray, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now

        mask = glyph_mask(frame)
        if mask is None:
            self._candidate, self._candidate_seen = None, 0
            return False

        if self._confirmed is None or self._confirmed.shape != mask.shape:
            self._confirmed = mask
            return False

        self.last_difference = shape_difference(mask, self._confirmed)
        if self.last_difference < self.change_fraction:
            # back to what we already knew; whatever we were tracking was noise
            self._candidate, self._candidate_seen = None, 0
            return False

        # something different is on screen - insist it stays there
        if self._candidate is not None and shape_difference(mask, self._candidate) < self.change_fraction:
            self._candidate_seen += 1
        else:
            self._candidate, self._candidate_seen = mask, 1

        if self._candidate_seen < self.stable_frames:
            return False

        self._confirmed = self._candidate
        self._candidate, self._candidate_seen = None, 0

        if self._last_fired is not None and now - self._last_fired < self.debounce_seconds:
            return False

        self._last_fired = now
        return True


@dataclass
class RoundDetector:
    """Watches both score numerals and reports who won when one of them moves."""

    change_fraction: float = 0.25
    debounce_seconds: float = 20.0
    stable_frames: int = 3

    def __post_init__(self) -> None:
        kwargs = dict(
            change_fraction=self.change_fraction,
            debounce_seconds=self.debounce_seconds,
            stable_frames=self.stable_frames,
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

        # Both at once is not a round. It is the scoreboard overlay, an
        # alt-tab, or a resolution change. Report nothing rather than invent.
        if ally_changed and enemy_changed:
            return None

        # A real round moves exactly one numeral, and moves it a lot. The bar
        # behind a numeral also shifts as players die, which is a small change
        # in the same region - and because confirming a change costs several
        # samples, that noise could be confirmed before the numeral that
        # actually moved, reporting the wrong side. Measured on a live match:
        # a lost round was reported as a win for exactly this reason.
        #
        # So a side only wins the call if it also moved more than the other.
        if ally_changed:
            if self.enemy.last_difference > self.ally.last_difference:
                return None
            return "won"
        if enemy_changed:
            if self.ally.last_difference > self.enemy.last_difference:
                return None
            return "lost"
        return None
