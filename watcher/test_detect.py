"""Checks the change detector on synthetic frames.

The capture half needs Valorant on screen, but this half does not, and it is
the half that can be wrong in ways you would not notice while playing: a
missed round silently corrupts every economy estimate that follows it.

    python -m watcher.test_detect
"""

import numpy as np

from watcher.detect import RoundDetector

QUIET = np.zeros((24, 18), dtype=np.float32)
DIGIT = QUIET.copy()
DIGIT[4:20, 4:14] = 255.0          # a bright blob, like a drawn numeral
FLICKER = QUIET.copy()
FLICKER[0, 0] = 255.0              # a single stray pixel


def fresh() -> RoundDetector:
    d = RoundDetector(debounce_seconds=20.0)
    d.update(QUIET, QUIET, now=0.0)  # prime both watchers
    return d


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    results = []

    d = fresh()
    results.append(check(
        "ally score changing reports a win",
        d.update(DIGIT, QUIET, now=1.0), "won"))

    d = fresh()
    results.append(check(
        "enemy score changing reports a loss",
        d.update(QUIET, DIGIT, now=1.0), "lost"))

    d = fresh()
    results.append(check(
        "nothing moving reports nothing",
        d.update(QUIET, QUIET, now=1.0), None))

    d = fresh()
    results.append(check(
        "a single stray pixel is ignored",
        d.update(FLICKER, QUIET, now=1.0), None))

    d = fresh()
    results.append(check(
        "both sides moving at once is refused",
        d.update(DIGIT, DIGIT, now=1.0), None))

    # a round cannot end twice in a few seconds
    d = fresh()
    first = d.update(DIGIT, QUIET, now=1.0)
    second = d.update(QUIET, QUIET, now=3.0)
    results.append(check("debounce blocks an immediate second fire",
                         (first, second), ("won", None)))

    # ...but a later change is honoured
    d = fresh()
    d.update(DIGIT, QUIET, now=1.0)
    d.update(DIGIT, QUIET, now=30.0)
    results.append(check("a change after the debounce window is reported",
                         d.update(QUIET, QUIET, now=60.0), "won"))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
