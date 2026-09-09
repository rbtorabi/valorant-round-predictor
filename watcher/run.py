"""Watches the score and reports each round as it ends.

    python -m watcher.run

Leave it running beside the game. Open the web app on localhost, switch match
mode to Auto, and rounds record themselves.

Check the regions are aimed correctly first:

    python -m watcher.preview
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from PIL import Image

from watcher import config as config_module
from watcher.banner import classify
from watcher.digits import load_templates, read_number
from watcher.spike import red_fraction
from watcher.capture import ScreenSource
from watcher.rounds import RoundSource
from watcher.server import PORT, WatcherState, serve

LABEL = {"won": "round won", "lost": "round lost"}

# Detections are appended here as they happen. The state the web app polls is
# held in memory and dies with the process, which lost a whole match's worth
# of evidence once - the terminal had printed it and nothing had kept it.
LOG_PATH = Path(__file__).resolve().parents[1] / "data" / "detections.jsonl"
DIAG_PATH = Path(__file__).resolve().parents[1] / "data" / "diagnostics.jsonl"
DEBUG_SHOTS = Path(__file__).resolve().parents[1] / "data" / "debug_banners"
MAX_DEBUG_SHOTS = 400


def append_json(path: Path, entry: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def record_to_log(outcome: str, source: str, planted: bool) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "outcome": outcome,
        "source": source,
        "planted": planted,
    }
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch the Valorant scoreline.")
    parser.add_argument("--monitor", type=int, default=1,
                        help="which monitor the game is on (1 = primary)")
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--debug", action="store_true",
                        help="log what each signal sees, for diagnosing misses")
    args = parser.parse_args()

    cfg = config_module.load()
    source = ScreenSource(cfg, monitor_index=args.monitor)
    detector = RoundSource(
        change_fraction=cfg.change_fraction,
        debounce_seconds=cfg.debounce_seconds,
        stable_frames=cfg.stable_frames,
    )
    state = WatcherState()
    serve(state, port=args.port)

    samples = 0
    shots = 0
    digit_templates = load_templates()
    if not digit_templates:
        print("note: no digit templates, so credits will not be read")

    print(f"watching monitor {args.monitor} at {source.width}x{source.height}")
    print(f"serving detected rounds on http://127.0.0.1:{args.port}/state")
    print(f"logging detections to {LOG_PATH}")
    if args.debug:
        print(f"debug: recording every sample to {DIAG_PATH}")
    print("switch the web app to Auto. ctrl-c to stop.\n")

    try:
        while True:
            ally, enemy, banner, timer, credits_crop = source.frames()

            # Your own credits are on screen, so there is no reason to
            # estimate them. An unreadable frame reports nothing rather
            # than a guess, and the app falls back to its estimate.
            state.set_credits(read_number(credits_crop, digit_templates))

            if args.debug:
                # Recording what the signals saw is the only way to explain a
                # missed round after the fact. Guessing from the outcome alone
                # already sent me down one wrong path.
                label, score = classify(banner)
                ink = float((banner > 240.0).mean())
                # Keep the pixels behind any frame that had lettering at all.
                # Numbers alone could not distinguish "the region is wrong"
                # from "no message was showing", and guessing between those
                # wasted a whole round trip.
                if ink > 0.002 and shots < MAX_DEBUG_SHOTS:
                    DEBUG_SHOTS.mkdir(parents=True, exist_ok=True)
                    Image.fromarray(banner.astype("uint8")).save(
                        DEBUG_SHOTS / f"{shots:04d}_{ink:.4f}.png")
                    shots += 1
                # written as it happens, not buffered - a killed process
                # would otherwise take the evidence with it, which is the
                # mistake that lost a whole match's detections already
                append_json(DIAG_PATH, {
                    "at": datetime.now().isoformat(timespec="seconds"),
                    "banner": label,
                    "banner_score": round(score, 3),
                    "banner_ink": round(ink, 4),
                    "ally_ink": round(float((ally > 240.0).mean()), 4),
                    "enemy_ink": round(float((enemy > 240.0).mean()), 4),
                    "red": round(red_fraction(timer), 3),
                    "credits": state.credits,
                })
                samples += 1

            found = detector.update(ally, enemy, banner, timer)
            if found:
                outcome, how, planted = found
                state.add(outcome, planted)
                record_to_log(outcome, how, planted)
                spike = ", spike planted" if planted else ""
                print(f"  {time.strftime('%H:%M:%S')}  {LABEL[outcome]}{spike}"
                      f"  (from the {how}, {len(state.snapshot())} rounds seen)")
            time.sleep(cfg.poll_seconds)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        source.close()
        if samples:
            print(f"wrote {samples} diagnostic samples to {DIAG_PATH}")
        if shots:
            print(f"saved {shots} banner crops to {DEBUG_SHOTS}")


if __name__ == "__main__":
    main()
