"""Saves what the watcher is looking at, so you can check it is aimed right.

    python -m watcher.preview

Run it with Valorant on screen. It writes three images to data/preview/:
the full screen with the two regions outlined, and each region on its own.
If the crops do not contain the two score numbers, edit data/watcher.json -
the values are fractions of the screen, so nudging `left` by 0.01 moves the
box one percent of the screen width to the right.
"""

import argparse
from pathlib import Path

from PIL import Image, ImageDraw

from watcher import config as config_module
from watcher.capture import ScreenSource

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "preview"


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview the watcher regions.")
    parser.add_argument("--monitor", type=int, default=1)
    parser.add_argument("--scale", type=int, default=6,
                        help="how much to enlarge the crops, for readability")
    args = parser.parse_args()

    cfg = config_module.load()
    source = ScreenSource(cfg, monitor_index=args.monitor)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    import mss

    with mss.mss() as sct:
        monitor = sct.monitors[args.monitor]
        full = Image.frombytes("RGB", (monitor["width"], monitor["height"]),
                               sct.grab(monitor).rgb)

    draw = ImageDraw.Draw(full)
    for box, colour in ((source.ally_box, "#4fb3a6"), (source.enemy_box, "#e45c4a")):
        x = box["left"] - monitor["left"]
        y = box["top"] - monitor["top"]
        draw.rectangle([x, y, x + box["width"], y + box["height"]], outline=colour, width=3)

    full.save(OUT_DIR / "screen.png")

    for name, box in (("ally", source.ally_box), ("enemy", source.enemy_box)):
        crop = full.crop((
            box["left"] - monitor["left"],
            box["top"] - monitor["top"],
            box["left"] - monitor["left"] + box["width"],
            box["top"] - monitor["top"] + box["height"],
        ))
        crop = crop.resize((crop.width * args.scale, crop.height * args.scale), Image.NEAREST)
        crop.save(OUT_DIR / f"{name}.png")

    source.close()
    print(f"wrote {OUT_DIR}")
    print("  screen.png  - full screen, regions outlined (teal = yours, red = theirs)")
    print("  ally.png    - should contain your score digit, and nothing else")
    print("  enemy.png   - should contain their score digit, and nothing else")


if __name__ == "__main__":
    main()
