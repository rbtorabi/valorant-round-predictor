"""Checks that the two round signals combine without double counting.

The banner and the scoreline both fire on the same round. If they were allowed
to report independently, every round would be counted twice and the economy
would run away. The shared debounce is the thing under test.

    python -m watcher.test_rounds
"""

import numpy as np
from PIL import Image

from watcher.banner import TEMPLATE_DIR
from watcher.rounds import RoundSource

QUIET = np.zeros((24, 18), dtype=np.float32)
DIGIT = QUIET.copy()
# Keep the bright area under the fraction that marks a frame unreadable - a
# real numeral covers a small part of its box, and a blob covering a third of
# it is a flashbang as far as the detector is concerned.
DIGIT[8:18, 6:12] = 255.0


def banner(name: str) -> np.ndarray:
    """Any stored example of a message - templates are named label[.n].png."""
    matches = sorted(
        p for p in TEMPLATE_DIR.glob(f"{name}*.png") if p.stem.split(".")[0] == name
    )
    if not matches:
        raise FileNotFoundError(f"no template for {name!r}")
    return np.asarray(Image.open(matches[0]).convert("L")).astype(np.float32)


def blank_banner() -> np.ndarray:
    return np.zeros_like(banner("won"))


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    results = []
    blank = blank_banner()

    # the banner is trusted first
    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    results.append(check("a WON banner reports a win from the banner",
                         s.update(QUIET, QUIET, banner("won"), now=1.0), ("won", "banner", False)))

    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    results.append(check("a LOST banner reports a loss from the banner",
                         s.update(QUIET, QUIET, banner("lost"), now=1.0), ("lost", "banner", False)))

    # a banner lingers on screen; only its arrival counts
    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    first = s.update(QUIET, QUIET, banner("won"), now=1.0)
    lingering = [s.update(QUIET, QUIET, banner("won"), now=t) for t in (2.0, 3.0, 40.0)]
    results.append(check("a lingering banner is not a second round",
                         (first, set(lingering)), (("won", "banner", False), {None})))

    # banner and score describing the same round is still one round
    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    from_banner = s.update(QUIET, QUIET, banner("won"), now=1.0)
    from_score = [s.update(DIGIT, QUIET, blank, now=t) for t in (2.0, 2.5, 3.0, 3.5)]
    results.append(check("the score agreeing does not add a second round",
                         (from_banner, set(from_score)), (("won", "banner", False), {None})))

    # with no banner at all, the score still works
    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    scored = [s.update(DIGIT, QUIET, blank, now=t) for t in (1.0, 1.5, 2.0, 2.5)]
    results.append(check("the score still reports when no banner is seen",
                         next((x for x in scored if x), None), ("won", "score", False)))

    # a plant seen mid-round is reported with the round it belongs to
    planted_timer = np.asarray(
        Image.open(TEMPLATE_DIR.parent / "timer_planted.png").convert("RGB")
    ).astype(np.float32)
    clear_timer = np.asarray(
        Image.open(TEMPLATE_DIR.parent / "timer_normal.png").convert("RGB")
    ).astype(np.float32)

    s = RoundSource()
    s.update(QUIET, QUIET, blank, clear_timer, now=0.0)
    s.update(QUIET, QUIET, blank, planted_timer, now=1.0)      # spike goes down
    s.update(QUIET, QUIET, blank, clear_timer, now=2.0)        # and goes away
    results.append(check("a plant earlier in the round is reported with it",
                         s.update(QUIET, QUIET, banner("won"), clear_timer, now=3.0),
                         ("won", "banner", True)))

    # and does not carry into the next round
    got = s.update(QUIET, QUIET, banner("lost"), clear_timer, now=40.0)
    results.append(check("the plant does not carry into the next round",
                         got, ("lost", "banner", False)))

    # a buy phase card is not a round result
    s = RoundSource()
    s.update(QUIET, QUIET, blank, now=0.0)
    results.append(check("a BUY PHASE card is not a round",
                         s.update(QUIET, QUIET, banner("buy_phase"), now=1.0), None))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
