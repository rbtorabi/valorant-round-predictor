"""Grabs the two score regions off the screen.

Passive reading only: this takes screenshots of your own display, the same
thing any recording software does. It never touches the game process, reads no
memory and injects nothing, which is what keeps it well clear of anything an
anti-cheat cares about.
"""

import numpy as np

try:
    import mss
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "mss is not installed. Run: pip install -r requirements.txt"
    ) from exc

from watcher.banner import BANNER_REGION
from watcher.config import Region, WatcherConfig
from watcher.digits import CREDITS_REGION
from watcher.spike import TIMER_REGION


def open_screen():
    """mss renamed its entry point; support both without a version pin."""
    factory = getattr(mss, "MSS", None) or mss.mss
    return factory()


class ScreenSource:
    """Repeatedly grabs the configured regions as greyscale arrays."""

    def __init__(self, config: WatcherConfig, monitor_index: int = 1) -> None:
        self._sct = open_screen()
        self._monitor = self._sct.monitors[monitor_index]
        self.width = self._monitor["width"]
        self.height = self._monitor["height"]

        ally = config.ally_score.to_pixels(self.width, self.height)
        enemy = config.enemy_score.to_pixels(self.width, self.height)
        # regions are absolute, so offset by the monitor's own origin
        self.ally_box = self._absolute(ally)
        self.enemy_box = self._absolute(enemy)

        # the HUD message card, which states the round result outright
        self.banner_box = self._absolute(
            Region(*BANNER_REGION).to_pixels(self.width, self.height)
        )
        # the round timer, which turns red for as long as the spike is down
        self.timer_box = self._absolute(
            Region(*TIMER_REGION).to_pixels(self.width, self.height)
        )
        # your own credits, which unlike the enemy's are right there on screen
        self.credits_box = self._absolute(
            Region(*CREDITS_REGION).to_pixels(self.width, self.height)
        )

    def _absolute(self, box: dict) -> dict:
        return {
            "left": self._monitor["left"] + box["left"],
            "top": self._monitor["top"] + box["top"],
            "width": box["width"],
            "height": box["height"],
        }

    def _grab(self, box: dict) -> np.ndarray:
        shot = self._sct.grab(box)
        pixels = np.asarray(shot)[:, :, :3].astype(np.float32)
        # luminance; the score is high-contrast so colour adds nothing
        return (0.299 * pixels[:, :, 2] + 0.587 * pixels[:, :, 1] + 0.114 * pixels[:, :, 0])

    def _grab_colour(self, box: dict) -> np.ndarray:
        """BGRA from the screen, returned as RGB - the spike test needs hue."""
        shot = self._sct.grab(box)
        pixels = np.asarray(shot)[:, :, :3].astype(np.float32)
        return pixels[:, :, ::-1]

    def frames(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Scores, the message card, the timer in colour, and your credits."""
        return (
            self._grab(self.ally_box),
            self._grab(self.enemy_box),
            self._grab(self.banner_box),
            self._grab_colour(self.timer_box),
            self._grab(self.credits_box),
        )

    def close(self) -> None:
        self._sct.close()
