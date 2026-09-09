"""Checks the banner classifier against the stored templates.

The templates are crops of real frames, so this is a check that recognition
holds up on actual HUD pixels rather than something synthetic. It cannot prove
the classifier handles a message it has never seen - that needs more collected
samples - but it does catch a threshold or comparison change quietly breaking
everything, which is the likely regression.

    python -m watcher.test_banner
"""

import numpy as np
from PIL import Image

from watcher.banner import TEMPLATE_DIR, classify, load_templates


def check(name: str, got, want) -> bool:
    ok = got == want
    print(f"  {'ok  ' if ok else 'FAIL'} {name}: got {got!r}, want {want!r}")
    return ok


def main() -> None:
    templates = load_templates()
    if not templates:
        print("no templates stored - run watcher.banner --learn first")
        raise SystemExit(1)

    results = []

    # every stored template must recognise itself
    for path in sorted(TEMPLATE_DIR.glob("*.png")):
        expected = path.stem.split(".")[0]
        label, score = classify(Image.open(path), templates)
        results.append(check(f"{path.name} recognises itself", label, expected))

    shape = next(iter(templates.values())).shape

    # an empty card is not a message
    blank = np.zeros(shape, dtype=np.float32)
    results.append(check("an empty card matches nothing",
                         classify(blank, templates)[0], None))

    # a bright wall is not a message either
    wall = np.full(shape, 230.0, dtype=np.float32)
    results.append(check("a bright wall matches nothing",
                         classify(wall, templates)[0], None))

    # a whiteout is not a message
    flash = np.full(shape, 255.0, dtype=np.float32)
    results.append(check("a whiteout matches nothing",
                         classify(flash, templates)[0], None))

    print(f"\n{sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
