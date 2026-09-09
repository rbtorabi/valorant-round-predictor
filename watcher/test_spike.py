"""Checks spike detection against real timer frames.

Two planted frames from separate rounds, one ordinary frame, and one warm
sunlit frame that is the near miss worth guarding against - reddish scenery
behind a translucent timer is exactly what a naive colour test would call a
plant.

    python -m watcher.test_spike
"""

from pathlib import Path

import numpy as np
from PIL import Image

from watcher.spike import is_planted, red_fraction

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> Image.Image:
    return Image.open(FIXTURES / f"{name}.png")


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    results = []

    for name in ("timer_planted", "timer_planted.2"):
        frame = load(name)
        results.append(check(f"{name} reads as planted", is_planted(frame), True))
        print(f"       red fraction {red_fraction(frame):.3f}")

    for name in ("timer_normal", "timer_warm"):
        frame = load(name)
        results.append(check(f"{name} does not", is_planted(frame), False))
        print(f"       red fraction {red_fraction(frame):.3f}")

    # a flat red screen is not a spike icon in shape, but colour alone cannot
    # tell - worth knowing the detector does fire on it, so callers keep the
    # region tight rather than assuming shape is checked
    flat = np.zeros((20, 60, 3), dtype=np.float32)
    flat[:, :, 0] = 255.0
    results.append(check("a wholly red region reads as planted (colour only)",
                         is_planted(flat), True))

    grey = np.full((20, 60, 3), 128.0, dtype=np.float32)
    results.append(check("a grey region does not", is_planted(grey), False))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
