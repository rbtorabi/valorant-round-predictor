"""Saves what the watcher is looking at, so you can check it is aimed right.

    python -m watcher.preview

Run it with Valorant on screen. It counts down first, so you can switch back to
the game before the screen is grabbed - whatever is focused when you press
Enter is the terminal, not Valorant.

It writes three images to data/preview/: the full screen with the two regions
outlined, and each region on its own. If the crops do not contain the two score
numbers, edit data/watcher.json - the values are fractions of the screen, so
nudging `left` by 0.01 moves the box one percent of the screen width.
"""

import argparse
import time
from pathlib import Path

from PIL import Image, ImageDraw

from watcher import config as config_module
from watcher.capture import ScreenSource, open_screen

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "preview"


def countdown(seconds: float) -> None:
    for remaining in range(int(seconds), 0, -1):
        print(f"grabbing in {remaining}... switch to Valorant", end="\r", flush=True)
        time.sleep(1)
    print(" " * 50, end="\r")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the watcher regions.")
    parser.add_argument("--monitor", type=int, default=1,
                        help="which monitor the game is on (1 = primary)")
    parser.add_argument("--scale", type=int, default=6,
                        help="how much to enlarge the crops, for readability")
    parser.add_argument("--delay", type=float, default=6.0,
                        help="seconds before grabbing, so you can switch to the game")
    args = parser.parse_args()

    if args.delay > 0:
        countdown(args.delay)

    cfg = config_module.load()
    source = ScreenSource(cfg, monitor_index=args.monitor)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with open_screen() as sct:
        monitor = sct.monitors[args.monitor]
        full = Image.frombytes(
            "RGB", (monitor["width"], monitor["height"]), sct.grab(monitor).rgb
        )

    draw = ImageDraw.Draw(full)
    for box, colour in ((source.ally_box, "#4fb3a6"), (source.enemy_box, "#e45c4a")):
        x = box["left"] - monitor["left"]
        y = box["top"] - monitor["top"]
        draw.rectangle([x, y, x + box["width"], y + box["height"]], outline=colour, width=3)

    full.save(OUT_DIR / "screen.png")

    for name, box in (("ally", source.ally_box), ("enemy", source.enemy_box)):
        left = box["left"] - monitor["left"]
        top = box["top"] - monitor["top"]
        crop = full.crop((left, top, left + box["width"], top + box["height"]))
        crop = crop.resize((crop.width * args.scale, crop.height * args.scale), Image.NEAREST)
        crop.save(OUT_DIR / f"{name}.png")

    source.close()
    print(f"wrote {OUT_DIR}")
    print("  screen.png  - full screen, regions outlined (teal = yours, red = theirs)")
    print("  ally.png    - should contain your score digit, and nothing else")
    print("  enemy.png   - should contain their score digit, and nothing else")


if __name__ == "__main__":
    main()
