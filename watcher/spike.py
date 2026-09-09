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

Measured on a real match: planted frames carry 0.245-0.251 strongly-red
pixels, every other frame 0.08 or less, including warm sunlit scenery behind
a translucent timer.
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
