"""Checks the credit reader against frames whose value is known.

Reading a number is less forgiving than noticing a change: a misread digit is
a wrong economy, silently. So the bar here is that a glyph it cannot place is
reported as unreadable rather than guessed - which is also why 7 and 9 having
no template yet is safe rather than dangerous.

    python -m watcher.test_digits
"""

from pathlib import Path

import numpy as np
from PIL import Image

from watcher.digits import (
    digit_boxes,
    load_templates,
    match_glyph,
    normalise,
    read_number,
    to_mask,
)

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "collect"

# values read off the frames by eye
KNOWN = {
    "20260908-194718/0001": 800,
    "20260908-194718/0012": 400,
    "20260908-194718/0046": 650,
    "20260908-194718/0083": 600,
    "20260908-194718/0086": 350,
    "20260908-194718/0116": 250,
    "20260908-194718/0079": 1150,
    "20260908-193522/0002": 2000,
    "20260908-193522/0029": 1650,
}


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    templates = load_templates()
    if not templates:
        print("no digit templates stored")
        raise SystemExit(1)

    results = []

    missing = [d for d in "0123456789" if d not in templates]
    print(f"  note  digits without a template: {missing or 'none'}")

    available = [p for p in KNOWN if (SAMPLES / p.split("/")[0]).exists()]
    if not available:
        print("  note  sample frames not on disk; skipping the read-back checks")
    for key in available:
        session, stem = key.split("/")
        path = SAMPLES / session / "credits" / f"{stem}.png"
        if not path.exists():
            continue
        results.append(check(f"reads {key}", read_number(Image.open(path), templates), KNOWN[key]))

    # an empty crop is unreadable, not zero - those mean different things
    blank = np.zeros((41, 190), dtype=np.float32)
    results.append(check("an empty crop reads as nothing", read_number(blank, templates), None))

    # a bright wall has no glyphs of digit shape
    wall = np.full((41, 190), 255.0, dtype=np.float32)
    results.append(check("a white crop reads as nothing", read_number(wall, templates), None))

    # every stored template must recognise itself
    self_ok = True
    for digit, examples in templates.items():
        for template in examples:
            got, _ = match_glyph(template, templates)
            self_ok = self_ok and got == digit
    results.append(check("every template recognises itself", self_ok, True))

    # a glyph that is not a digit must not be forced into one
    noise = np.zeros((14, 10), dtype=bool)
    noise[::3, ::2] = True
    label, _ = match_glyph(noise, templates)
    results.append(check("a nonsense glyph is refused", label, None))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
