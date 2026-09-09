"""Watches the score and reports each round as it ends.

    python -m watcher.run

Leave it running beside the game. Open the web app on localhost, switch match
mode to Auto, and rounds record themselves.

Check the regions are aimed correctly first:

    python -m watcher.preview
"""

import argparse
import time

from watcher import config as config_module
from watcher.capture import ScreenSource
from watcher.detect import RoundDetector
from watcher.server import PORT, WatcherState, serve

LABEL = {"won": "round won", "lost": "round lost"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Watch the Valorant scoreline.")
    parser.add_argument("--monitor", type=int, default=1,
                        help="which monitor the game is on (1 = primary)")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()

    cfg = config_module.load()
    source = ScreenSource(cfg, monitor_index=args.monitor)
    detector = RoundDetector(
        change_fraction=cfg.change_fraction,
        debounce_seconds=cfg.debounce_seconds,
        stable_frames=cfg.stable_frames,
    )
    state = WatcherState()
    serve(state, port=args.port)

    print(f"watching monitor {args.monitor} at {source.width}x{source.height}")
    print(f"serving detected rounds on http://127.0.0.1:{args.port}/state")
    print("switch the web app to Auto. ctrl-c to stop.\n")

    try:
        while True:
            ally, enemy = source.frames()
            outcome = detector.update(ally, enemy)
            if outcome:
                state.add(outcome)
                print(f"  {time.strftime('%H:%M:%S')}  {LABEL[outcome]}"
                      f"  ({len(state.snapshot())} rounds seen)")
            time.sleep(cfg.poll_seconds)
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        source.close()


if __name__ == "__main__":
    main()
