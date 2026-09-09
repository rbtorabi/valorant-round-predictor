"""Reads a number off the HUD - your credits, specifically.

The score detector only needs to notice that something changed. Credits are
different: the value itself is the point, so the digits have to be read.

Doing that without OCR works because the HUD font never varies. A crop is
reduced to bright pixels, split into glyphs by columns of ink, and each glyph
is matched against stored examples. Three things make the split reliable:

* the currency symbol is shorter than a digit (8 pixels against 13),
* a comma is shorter still (4) and narrow,
* the round-bonus popup that sometimes sits above uses a much larger face.

So keeping only glyphs of digit height isolates the number, whatever else the
crop happens to contain.

A glyph that matches nothing is reported as unknown rather than guessed at.
That matters: a wrong digit is a wrong economy, and there is no template for
7 or 9 yet - no round in the collected samples happened to show one.
"""

from pathlib import Path

import numpy as np
from PIL import Image

TEMPLATE_DIR = Path(__file__).resolve().parent / "fixtures" / "digits"

# Your credits, bottom right, above the client version line.
CREDITS_REGION = (0.9010, 0.9370, 0.0990, 0.0380)

BRIGHT_THRESHOLD = 200.0

# Digit glyphs measured on real frames: 13 tall, 4-8 wide. The currency symbol
# is 8 tall and a comma 4, so a height window alone separates them.
MIN_GLYPH_HEIGHT = 11
MAX_GLYPH_HEIGHT = 16
MIN_GLYPH_WIDTH = 2
MAX_GLYPH_WIDTH = 12

# Every glyph is scaled to this before comparison, so a digit is recognised
# regardless of where it sat or how the crop was aligned.
NORMAL_SIZE = (10, 14)

# Below this the glyph is not any digit we know.
MIN_SCORE = 0.72


def to_mask(image: np.ndarray | Image.Image) -> np.ndarray:
    if isinstance(image, Image.Image):
        image = np.asarray(image.convert("L")).astype(np.float32)
    return image > BRIGHT_THRESHOLD


def column_runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """Spans of columns that contain ink."""
    inked = mask.any(axis=0)
    runs, start = [], None
    for index, on in enumerate(inked):
        if on and start is None:
            start = index
        elif not on and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(inked)))
    return runs


def digit_boxes(mask: np.ndarray) -> list[tuple[int, int]]:
    """Column spans that look like digits, left to right."""
    boxes = []
    for left, right in column_runs(mask):
        rows = mask[:, left:right].any(axis=1).nonzero()[0]
        if not len(rows):
            continue
        height = int(rows.max() - rows.min() + 1)
        width = right - left
        if (MIN_GLYPH_HEIGHT <= height <= MAX_GLYPH_HEIGHT
                and MIN_GLYPH_WIDTH <= width <= MAX_GLYPH_WIDTH):
            boxes.append((left, right))
    return boxes


def normalise(mask: np.ndarray, left: int, right: int) -> np.ndarray:
    """One glyph, cropped to its ink and scaled to a common size."""
    piece = mask[:, left:right]
    rows = piece.any(axis=1).nonzero()[0]
    piece = piece[rows.min(): rows.max() + 1]
    image = Image.fromarray((piece * 255).astype(np.uint8))
    image = image.resize(NORMAL_SIZE, Image.NEAREST)
    return np.asarray(image) > 127


def load_templates() -> dict[str, list[np.ndarray]]:
    templates: dict[str, list[np.ndarray]] = {}
    if not TEMPLATE_DIR.exists():
        return templates
    for path in sorted(TEMPLATE_DIR.glob("*.png")):
        digit = path.stem.split(".")[0]
        arr = np.asarray(Image.open(path).convert("L")) > 127
        templates.setdefault(digit, []).append(arr)
    return templates


def match_glyph(glyph: np.ndarray, templates: dict[str, list[np.ndarray]]) -> tuple[str | None, float]:
    best, best_score = None, 0.0
    for digit, examples in templates.items():
        for template in examples:
            if template.shape != glyph.shape:
                continue
            union = np.logical_or(glyph, template).sum()
            if union == 0:
                continue
            score = float(np.logical_and(glyph, template).sum()) / float(union)
            if score > best_score:
                best, best_score = digit, score
    if best_score < MIN_SCORE:
        return None, best_score
    return best, best_score


def read_number(frame: np.ndarray | Image.Image,
                templates: dict[str, list[np.ndarray]] | None = None) -> int | None:
    """The number in the crop, or None if any glyph could not be read."""
    templates = load_templates() if templates is None else templates
    if not templates:
        return None

    mask = to_mask(frame)
    boxes = digit_boxes(mask)
    if not boxes:
        return None

    text = ""
    for left, right in boxes:
        digit, _ = match_glyph(normalise(mask, left, right), templates)
        if digit is None:
            return None  # an unknown glyph makes the whole number untrustworthy
        text += digit
    return int(text) if text else None
