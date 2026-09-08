"""Parsers for VLR.gg pages.

Two pages are needed per match and they carry different halves of a round:

* the main match page  -> win condition (elim / spike / defuse / time)
* the ?tab=economy page -> loadout value and bank for both teams

Loadout value is the worth of guns and armour a team is holding; bank is the
credits they have left. They are different numbers and both matter: loadout
drives who wins the round, bank drives what they can afford next.

They are joined on (game_id, round_num).

Buy-type thresholds follow VLR's own bucketing of loadout value:
eco < $5k, semi-eco $5-10k, semi-buy $10-20k, full-buy >= $20k.
"""

import re
from dataclasses import dataclass, field

from selectolax.parser import HTMLParser, Node

BASE = "https://www.vlr.gg"

WIN_CONDITIONS = {
    "elim": "elim",
    "boom": "spike",
    "defuse": "defuse",
    "time": "time",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _bank_value(node: Node) -> int | None:
    """VLR prints bank in thousands, e.g. "4.3k" -> 4300."""
    raw = _clean(node.text()).lower().replace("k", "")
    try:
        return int(round(float(raw) * 1000))
    except ValueError:
        return None


def buy_type(loadout: int | None) -> str | None:
    if loadout is None:
        return None
    if loadout < 5_000:
        return "eco"
    if loadout < 10_000:
        return "semi-eco"
    if loadout < 20_000:
        return "semi-buy"
    return "full-buy"


# --------------------------------------------------------------------------
# match list
# --------------------------------------------------------------------------

def parse_match_list(html: str) -> list[str]:
    """Absolute match URLs from a /matches/results listing page."""
    tree = HTMLParser(html)
    urls = []
    for a in tree.css("a.match-item"):
        href = a.attributes.get("href", "")
        if href.startswith("/"):
            urls.append(BASE + href)
    return urls


def match_id_from_url(url: str) -> str:
    m = re.search(r"vlr\.gg/(\d+)", url)
    if not m:
        raise ValueError(f"no match id in {url!r}")
    return m.group(1)


# --------------------------------------------------------------------------
# match page
# --------------------------------------------------------------------------

@dataclass
class ParsedMatch:
    vlr_match_id: str
    url: str
    event: str | None
    series: str | None
    played_at: str | None
    team_a: str | None
    team_b: str | None
    maps: list[dict] = field(default_factory=list)


def _teams(tree: HTMLParser) -> tuple[str | None, str | None]:
    names = [_clean(n.text()) for n in tree.css("div.match-header-vs .wf-title-med")]
    names = [n for n in names if n]
    if len(names) >= 2:
        return names[0], names[1]
    return (names[0] if names else None), None


def _game_blocks(tree: HTMLParser) -> list[tuple[str, Node]]:
    """(game_id, node) for real maps, skipping the aggregate 'all' block."""
    out = []
    for g in tree.css("div.vm-stats-game"):
        gid = g.attributes.get("data-game-id")
        if gid and gid != "all":
            out.append((gid, g))
    return out


def _map_name(block: Node) -> str | None:
    node = block.css_first("div.map div span")
    if node is None:
        return None
    # strips the "PICK" suffix VLR appends to the map-pick indicator
    return _clean(node.text()).replace("PICK", "").strip() or None


def _round_outcomes(block: Node) -> dict[int, dict]:
    """Winner, side and win condition per round, from the main match page."""
    rounds: dict[int, dict] = {}
    for col in block.css("div.vlr-rounds-row-col"):
        num_node = col.css_first("div.rnd-num")
        if num_node is None:
            continue
        try:
            rnum = int(_clean(num_node.text()))
        except ValueError:
            continue

        squares = col.css("div.rnd-sq")
        if len(squares) < 2:
            continue

        winner_idx = None
        winner_side = None
        for idx, sq in enumerate(squares[:2]):
            classes = sq.attributes.get("class", "")
            if "mod-win" in classes:
                winner_idx = idx
                winner_side = "atk" if "mod-t" in classes else "def"

        if winner_idx is None:
            continue

        condition = None
        img = squares[winner_idx].css_first("img")
        if img is not None:
            stem = img.attributes.get("src", "").rsplit("/", 1)[-1].split(".")[0]
            condition = WIN_CONDITIONS.get(stem)

        rounds[rnum] = {
            "winner_idx": winner_idx,      # 0 = team_a, 1 = team_b
            "winner_side": winner_side,
            "win_condition": condition,
            "score_after": col.attributes.get("title"),
        }
    return rounds


def _round_economy(block: Node) -> dict[int, dict]:
    """Loadout value and bank per round, from the economy tab."""
    econ: dict[int, dict] = {}
    for cell in block.css("td"):
        num_node = cell.css_first("div.round-num")
        if num_node is None:
            continue
        try:
            rnum = int(_clean(num_node.text()))
        except ValueError:
            continue

        squares = cell.css("div.rnd-sq")
        if len(squares) < 2:
            continue

        def loadout(sq: Node) -> int | None:
            raw = sq.attributes.get("title", "")
            digits = re.sub(r"[^\d]", "", raw)
            return int(digits) if digits else None

        banks = [_bank_value(b) for b in cell.css("div.bank")]

        econ[rnum] = {
            "loadout_a": loadout(squares[0]),
            "loadout_b": loadout(squares[1]),
            "bank_a": banks[0] if len(banks) > 0 else None,
            "bank_b": banks[1] if len(banks) > 1 else None,
        }
    return econ


def parse_match(main_html: str, econ_html: str, url: str) -> ParsedMatch:
    tree = HTMLParser(main_html)
    econ_tree = HTMLParser(econ_html)

    team_a, team_b = _teams(tree)
    # the event name lives in an <a>, not a <div>; the series label is separate
    event_node = tree.css_first("a.match-header-event div div")
    series_node = tree.css_first("div.match-header-event-series")
    date_node = tree.css_first("div.match-header-date div.moment-tz-convert")

    parsed = ParsedMatch(
        vlr_match_id=match_id_from_url(url),
        url=url,
        event=_clean(event_node.text()) if event_node else None,
        series=_clean(series_node.text()) if series_node else None,
        played_at=(date_node.attributes.get("data-utc-ts") if date_node else None),
        team_a=team_a,
        team_b=team_b,
    )

    econ_blocks = {gid: block for gid, block in _game_blocks(econ_tree)}

    for map_index, (gid, block) in enumerate(_game_blocks(tree)):
        outcomes = _round_outcomes(block)
        economy = _round_economy(econ_blocks[gid]) if gid in econ_blocks else {}
        if not outcomes:
            continue

        rounds = []
        score_a = score_b = 0
        for rnum in sorted(outcomes):
            o = outcomes[rnum]
            e = economy.get(rnum, {})

            a_is_atk = (o["winner_idx"] == 0) == (o["winner_side"] == "atk")
            atk_team, def_team = (team_a, team_b) if a_is_atk else (team_b, team_a)
            atk_load = e.get("loadout_a") if a_is_atk else e.get("loadout_b")
            def_load = e.get("loadout_b") if a_is_atk else e.get("loadout_a")
            atk_bank = e.get("bank_a") if a_is_atk else e.get("bank_b")
            def_bank = e.get("bank_b") if a_is_atk else e.get("bank_a")

            rounds.append({
                "round_num": rnum,
                "atk_team": atk_team,
                "def_team": def_team,
                # score BEFORE the round - the only leakage-safe form
                "atk_score_pre": score_a if a_is_atk else score_b,
                "def_score_pre": score_b if a_is_atk else score_a,
                "atk_loadout": atk_load,
                "def_loadout": def_load,
                "atk_bank": atk_bank,
                "def_bank": def_bank,
                "atk_buy": buy_type(atk_load),
                "def_buy": buy_type(def_load),
                "winner_side": o["winner_side"],
                "win_condition": o["win_condition"],
            })

            if o["winner_idx"] == 0:
                score_a += 1
            else:
                score_b += 1

        parsed.maps.append({
            "game_id": gid,
            "map_index": map_index,
            "map_name": _map_name(block),
            "score_a": score_a,
            "score_b": score_b,
            "rounds": rounds,
        })

    return parsed
