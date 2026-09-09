"""Reads the message card at the top of the HUD.

That one region carries more than the scoreline does. Across a match it shows
BUY PHASE with the round number and your side, SPIKE PLANTED, YOU HAVE THE
SPIKE, and the round result itself. The result banner is the valuable one: it
states who won directly, rather than making us infer it from a score that
changed.

Recognition is deliberately crude and works because the card is always drawn
at the same place in the same font. Each frame is reduced to a mask of its
bright glyph pixels - the same trick the score detector uses to survive being
drawn over the live world - and compared against stored masks by intersection
over union. No OCR, no font handling, no per-resolution work beyond the region
being expressed as a fraction of the screen.

Templates live in fixtures/banners/ and are cropped from real frames. To add
one, collect samples with `python -m watcher.collect`, find the frame, and run
`python -m watcher.banner --learn <label> <file>`.
"""

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

TEMPLATE_DIR = Path(__file__).resolve().parent / "fixtures" / "banners"

# The message card, as fractions of the screen. Matches watcher.collect's
# "phase" region so collected samples can be used as templates directly.
BANNER_REGION = (0.3800, 0.1100, 0.2400, 0.1100)

# Measured on real frames: banner text clears 240 while even sunlit walls
# do not. At 195 the mask was 60% scenery and comparisons were meaningless.
BRIGHT_THRESHOLD = 240.0
# Below this overlap a match is not believable; better to report nothing.
MIN_OVERLAP = 0.45
# A card with almost no bright pixels is an empty region, not a message.
MIN_INK = 0.02

# Some messages share furniture - "YOU HAVE THE SPIKE" and "SPIKE PLANTED"
# draw the same icon beneath different words, and they mean opposite things.
# Rather than guess between two close matches, report nothing unless the best
# beats the runner-up by this margin.
MIN_MARGIN = 0.08


def to_mask(image: np.ndarray | Image.Image) -> np.ndarray:
    if isinstance(image, Image.Image):
        image = np.asarray(image.convert("L")).astype(np.float32)
    return image > BRIGHT_THRESHOLD


def overlap(a: np.ndarray, b: np.ndarray) -> float:
    """Intersection over union of two glyph masks."""
    if a.shape != b.shape:
        return 0.0
    union = int(np.logical_or(a, b).sum())
    if union == 0:
        return 0.0
    return float(np.logical_and(a, b).sum()) / union


def load_templates() -> dict[str, np.ndarray]:
    if not TEMPLATE_DIR.exists():
        return {}
    templates = {}
    for path in sorted(TEMPLATE_DIR.glob("*.png")):
        templates[path.stem] = to_mask(Image.open(path))
    return templates


def classify(frame: np.ndarray | Image.Image,
             templates: dict[str, np.ndarray] | None = None) -> tuple[str | None, float]:
    """Best matching banner label, or (None, score) when nothing matches."""
    templates = load_templates() if templates is None else templates
    mask = to_mask(frame)

    if mask.mean() < MIN_INK:
        return None, 0.0

    scored = sorted(
        ((overlap(mask, template), label) for label, template in templates.items()),
        reverse=True,
    )
    if not scored:
        return None, 0.0

    best_score, best_label = scored[0]
    if best_score < MIN_OVERLAP:
        return None, best_score

    # two different messages scoring alike means we cannot tell them apart
    runner_up = next(
        (s for s, l in scored[1:] if l.split(".")[0] != best_label.split(".")[0]), 0.0
    )
    if best_score - runner_up < MIN_MARGIN:
        return None, best_score
    # templates are named like "won" or "buy_phase.2"; the suffix is just a
    # second example of the same message
    return best_label.split(".")[0], best_score


def learn(label: str, source: Path) -> Path:
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    target = TEMPLATE_DIR / f"{label}.png"
    index = 2
    while target.exists():
        target = TEMPLATE_DIR / f"{label}.{index}.png"
        index += 1
    Image.open(source).convert("L").save(target)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description="Banner templates.")
    parser.add_argument("--learn", nargs=2, metavar=("LABEL", "FILE"),
                        help="store FILE as a template for LABEL")
    parser.add_argument("--test", metavar="FILE", help="classify one frame")
    parser.add_argument("--list", action="store_true", help="list known templates")
    args = parser.parse_args()

    if args.learn:
        label, file = args.learn
        print("stored", learn(label, Path(file)))
    elif args.test:
        label, score = classify(Image.open(args.test))
        print(f"{Path(args.test).name}: {label or 'no match'} ({score:.2f})")
    elif args.list:
        for name, mask in load_templates().items():
            print(f"  {name:20} {mask.shape}  ink={mask.mean():.3f}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
