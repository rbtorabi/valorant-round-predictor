"""Fetch layer for VLR.gg.

Deliberately polite: one request at a time, a real delay between them, and an
on-disk cache so re-parsing never re-downloads. Parsing lives in parse.py so
that changing a selector does not cost another crawl.
"""

import hashlib
import time
from pathlib import Path

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://www.vlr.gg"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
USER_AGENT = "valorant-round-predictor/0.1 (personal research project)"
DELAY_SECONDS = 1.5

_client = httpx.Client(
    headers={"User-Agent": USER_AGENT},
    timeout=20.0,
    follow_redirects=True,
)


def _cache_path(url: str) -> Path:
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    return CACHE_DIR / f"{key}.html"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(min=2, max=30))
def _download(url: str) -> str:
    resp = _client.get(url)
    resp.raise_for_status()
    return resp.text


def fetch(url: str, *, use_cache: bool = True) -> str:
    """Return page HTML, from disk cache when available."""
    path = _cache_path(url)
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")

    html = _download(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    time.sleep(DELAY_SECONDS)
    return html


# TODO(next session): inspect a real match page and write the parsers.
#   - parse_match_list(html) -> list[match_url]
#   - parse_match(html)      -> match / maps / rounds dicts
# Held back on purpose: writing selectors against a page I have not read yet
# produces code that looks done and is not.
