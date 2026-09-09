"""Collects sample crops of candidate HUD regions while you play.

Locating a HUD element needs a frame that actually contains it, and most of
them only appear for a few seconds - the round-end banner, the spike timer,
the buy phase card. Guessing coordinates from memory does not work; this
gathers the evidence instead.

    python -m watcher.collect --seconds 300

Each run writes to its own timestamped folder under data/collect/, so a new
capture never mixes with the last one. Nothing is uploaded anywhere; the files
sit on your disk for inspection.
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from watcher.capture import open_screen

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "collect"

# Fractions of the screen, deliberately generous - better to catch the element
# with slack around it than to miss it and learn nothing.
CANDIDATES = {
    # your credits, bottom right, above the client version line
    "credits": (0.9010, 0.9370, 0.0990, 0.0380),
    # the card that says BUY PHASE / ROUND N / your side, top centre
    "phase": (0.3800, 0.1100, 0.2400, 0.1100),
    # round timer, or the spike timer once it is planted
    "timer": (0.4600, 0.0200, 0.0800, 0.0500),
    # where the round result appears at the end of a round
    "result": (0.3300, 0.3600, 0.3400, 0.1600),
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect HUD samples while playing.")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--every", type=float, default=1.5)
    parser.add_argument("--monitor", type=int, default=1)
    parser.add_argument("--full-every", type=int, default=15,
                        help="also save a whole frame this often, in samples")
    args = parser.parse_args()

    # Each run gets its own folder. Writing into a shared one meant a new
    # capture silently mixed with the previous one, and frames had to be told
    # apart by modification time.
    session = OUT_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
    for name in CANDIDATES:
        (session / name).mkdir(parents=True, exist_ok=True)
    (session / "full").mkdir(parents=True, exist_ok=True)
    print(f"writing to {session}")

    sct = open_screen()
    monitor = sct.monitors[args.monitor]
    width, height = monitor["width"], monitor["height"]
    print(f"collecting from {width}x{height} for {args.seconds:.0f}s - keep playing")

    deadline = time.time() + args.seconds
    index = 0
    try:
        while time.time() < deadline:
            shot = sct.grab(monitor)
            frame = Image.frombytes("RGB", (shot.width, shot.height), shot.rgb)

            for name, (l, t, w, h) in CANDIDATES.items():
                box = (
                    int(l * width),
                    int(t * height),
                    int((l + w) * width),
                    int((t + h) * height),
                )
                frame.crop(box).save(session / name / f"{index:04d}.png")

            if index % args.full_every == 0:
                frame.save(session / "full" / f"{index:04d}.jpg", quality=70)

            index += 1
            if index % 15 == 0:
                print(f"  {index} samples", end="\r", flush=True)
            time.sleep(args.every)
    except KeyboardInterrupt:
        print("\nstopped early")
    finally:
        sct.close()

    print(f"\nwrote {index} samples per region to {session}")


if __name__ == "__main__":
    main()
