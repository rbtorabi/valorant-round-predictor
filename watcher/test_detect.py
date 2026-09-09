"""Checks the change detector, including against real HUD frames.

The capture half needs Valorant on screen, but this half does not - and this
is the half that fails invisibly. A missed round silently corrupts every
economy estimate after it, and a spurious round does the same in reverse.

The fixtures are two real score numerals cropped from an actual match, which
matters because the scoreline is drawn over the live 3D world: the pixels
behind a numeral change every time the camera moves. The important test here
is that camera movement does NOT read as a score change.

    python -m watcher.test_detect
"""

from pathlib import Path

import numpy as np
from PIL import Image

from watcher.detect import RoundDetector

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name: str) -> np.ndarray:
    return np.asarray(Image.open(FIXTURES / f"{name}.png").convert("L")).astype(np.float32)


DIGIT_3 = load("digit_3")
DIGIT_0 = load("digit_0")


def with_moved_background(frame: np.ndarray, seed: int = 0) -> np.ndarray:
    """The same numeral, with a completely different world behind it.

    This is what turning the camera does: the glyph stays, everything else
    changes. Simulated by scrambling only the non-glyph pixels.
    """
    rng = np.random.default_rng(seed)
    out = frame.copy()
    background = frame <= 235.0
    out[background] = rng.uniform(60, 200, size=int(background.sum()))
    return out


def flashbanged(frame: np.ndarray) -> np.ndarray:
    return np.full_like(frame, 255.0)


def feed(detector: RoundDetector, ally, enemy, times) -> list:
    return [detector.update(ally, enemy, now=t) for t in times]


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    results = []

    # --- the critical one: moving the camera is not a score change ---------
    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    moves = [
        d.update(with_moved_background(DIGIT_3, i), with_moved_background(DIGIT_0, i), now=t)
        for i, t in enumerate(np.arange(1.0, 30.0, 0.5), start=1)
    ]
    results.append(check("camera movement behind the score is ignored",
                         set(moves), {None}))

    # --- a genuine score change ------------------------------------------
    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    got = feed(d, DIGIT_0, DIGIT_0, [1.0, 1.5, 2.0, 2.5])
    results.append(check("your numeral changing reports a win",
                         next((x for x in got if x), None), "won"))

    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    got = feed(d, DIGIT_3, DIGIT_3, [1.0, 1.5, 2.0, 2.5])
    results.append(check("their numeral changing reports a loss",
                         next((x for x in got if x), None), "lost"))

    # --- transient noise must not fire ------------------------------------
    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    got = feed(d, DIGIT_0, DIGIT_0, [1.0])          # one frame only
    got += feed(d, DIGIT_3, DIGIT_0, [1.5, 2.0])    # then back to normal
    results.append(check("a single odd frame is not a round", set(got), {None}))

    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    got = feed(d, flashbanged(DIGIT_3), DIGIT_0, [1.0, 1.5, 2.0, 2.5])
    results.append(check("a flashbang is discarded, not counted", set(got), {None}))

    # --- both sides at once is not a round --------------------------------
    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    got = feed(d, DIGIT_0, DIGIT_3, [1.0, 1.5, 2.0, 2.5])
    results.append(check("both numerals changing at once is refused",
                         set(got), {None}))

    # --- debounce ---------------------------------------------------------
    d = RoundDetector()
    feed(d, DIGIT_3, DIGIT_0, [0.0])
    feed(d, DIGIT_0, DIGIT_0, [1.0, 1.5, 2.0, 2.5])   # fires
    got = feed(d, DIGIT_3, DIGIT_0, [3.0, 3.5, 4.0, 4.5])  # immediately again
    results.append(check("a second change inside the debounce is blocked",
                         set(got), {None}))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
