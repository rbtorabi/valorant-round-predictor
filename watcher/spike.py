"""Detects that the spike is down, from the timer turning red.

The obvious approach was to read the SPIKE PLANTED message, and it kept
failing: the message shows for a couple of seconds and sampling repeatedly
landed either side of it. What we caught instead was SPIKE INITIATING, which
is the plant in progress and pays nothing if it gets cancelled.

The timer is the better signal. Once the spike is down, the round timer is
replaced by a red spike icon that stays for the whole fuse - some forty-five
seconds - so it cannot be missed at any sane sampling rate. It is also
unambiguous in a way the message is not: it is there because the spike is
actually planted, not because someone started planting.

Measured on collected frames: planted frames carried 0.245-0.251 strongly-red
pixels against 0.08 or less elsewhere. That separation held on the maps those
samples came from and then failed in a live match on a different one, where
every round was reported as planted - including a round that ended on the
timer expiring, which by definition had no spike down.

A single red frame is therefore not enough. A plant holds the timer red for
the whole fuse, some forty-five seconds, so requiring the red to persist for
several consecutive samples costs nothing real and rejects a transient flash,
a red-lit skybox drifting past, or a damage vignette.
"""

import numpy as np
from PIL import Image

# The round timer, as a fraction of the screen.
TIMER_REGION = (0.4600, 0.0200, 0.0800, 0.0500)

# A pixel counts as spike-red only if red clearly dominates both other
# channels; merely warm scenery does not qualify.
CHANNEL_MARGIN = 60.0

# Measured separation is wide, so this sits well clear of both sides.
MIN_RED_FRACTION = 0.15


def red_fraction(frame: np.ndarray | Image.Image) -> float:
    """How much of the timer region is spike-red."""
    if isinstance(frame, Image.Image):
        frame = np.asarray(frame.convert("RGB")).astype(np.float32)
    if frame.ndim != 3 or frame.shape[2] < 3:
        raise ValueError("spike detection needs a colour frame")

    red, green, blue = frame[:, :, 0], frame[:, :, 1], frame[:, :, 2]
    strong = (red - green > CHANNEL_MARGIN) & (red - blue > CHANNEL_MARGIN)
    return float(strong.mean())


def is_planted(frame: np.ndarray | Image.Image) -> bool:
    return red_fraction(frame) >= MIN_RED_FRACTION


# A plant holds for the whole fuse, so insisting on several consecutive red
# samples loses nothing and rejects transient red.
MIN_CONSECUTIVE = 5


class PlantWatcher:
    """Reports a plant only once the timer has been red for a while."""

    def __init__(self, min_consecutive: int = MIN_CONSECUTIVE) -> None:
        self.min_consecutive = min_consecutive
        self._run = 0

    def update(self, timer_frame) -> bool:
        """True while the spike is confirmed down."""
        if is_planted(timer_frame):
            self._run += 1
        else:
            self._run = 0
        return self._run >= self.min_consecutive

    def reset(self) -> None:
        self._run = 0
