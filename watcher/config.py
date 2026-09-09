"""Screen regions the watcher looks at, and where they are saved.

Only two regions matter: the two score numbers at the top of the HUD. The
watcher never reads what they say - it only notices when one of them changes,
which is enough to know a round ended and who won it. That is why there is no
OCR here, and why this works at any resolution or in any language.

Defaults are expressed as fractions of the screen, because the HUD is centred
and scales with resolution. They were measured off a real 1920x1080 frame and
should carry to other 16:9 displays; check with `python -m watcher.preview` and
correct data/watcher.json if your crops miss.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "watcher.json"


@dataclass
class Region:
    """A screen rectangle, in fractions of screen width and height."""

    left: float
    top: float
    width: float
    height: float

    def to_pixels(self, screen_width: int, screen_height: int) -> dict:
        return {
            "left": int(self.left * screen_width),
            "top": int(self.top * screen_height),
            "width": max(1, int(self.width * screen_width)),
            "height": max(1, int(self.height * screen_height)),
        }


@dataclass
class WatcherConfig:
    """Both score numbers, plus how twitchy the change detector should be."""

    # The score sits either side of the round timer, top centre.
    ally_score: Region = None  # type: ignore[assignment]
    enemy_score: Region = None  # type: ignore[assignment]

    # How much two glyph shapes must disagree to count as a different
    # numeral, relative to how much ink they hold.
    change_fraction: float = 0.25
    # A new shape must persist this many samples before it is believed.
    stable_frames: int = 3
    # A round cannot end twice inside this window. Buy phase alone is thirty
    # seconds before a round that runs to a hundred, so consecutive round ends
    # are a minute apart at the very least. Set at 20 originally, which let two
    # spurious detections through in a live match at gaps of 27 and 30 seconds.
    debounce_seconds: float = 35.0
    # How often to sample the screen.
    poll_seconds: float = 0.5

    def __post_init__(self) -> None:
        # Measured off a real 1920x1080 frame, as fractions so they carry to
        # other 16:9 resolutions. Wide enough for a two-digit score.
        if self.ally_score is None:
            self.ally_score = Region(left=0.4073, top=0.0222, width=0.0365, height=0.0481)
        if self.enemy_score is None:
            self.enemy_score = Region(left=0.5510, top=0.0222, width=0.0365, height=0.0481)


def load() -> WatcherConfig:
    if not CONFIG_PATH.exists():
        return WatcherConfig()
    raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return WatcherConfig(
        ally_score=Region(**raw["ally_score"]),
        enemy_score=Region(**raw["enemy_score"]),
        change_fraction=raw.get("change_fraction", 0.25),
        stable_frames=raw.get("stable_frames", 3),
        debounce_seconds=raw.get("debounce_seconds", 35.0),
        poll_seconds=raw.get("poll_seconds", 0.5),
    )


def save(config: WatcherConfig) -> Path:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(config), indent=2), encoding="utf-8")
    return CONFIG_PATH
