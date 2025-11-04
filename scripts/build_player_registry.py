#!/usr/bin/env python3
"""
Generate a canonical player registry with persistent IDs and attendance metrics.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
OUTPUT_PATH = DATA_DIR / "player_registry.json"

SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

UTILS_PATH = SRC_DIR / "aahlscraper" / "utils.py"
spec = importlib.util.spec_from_file_location("aahlscraper_utils", UTILS_PATH)
if spec is None or spec.loader is None:
    raise ImportError(f"Unable to load utilities module from {UTILS_PATH}")
_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_utils)

derive_player_id = getattr(_utils, "derive_player_id")
normalize_player_key = getattr(_utils, "normalize_player_key")
player_name_variants = getattr(_utils, "player_name_variants")
slugify = getattr(_utils, "slugify")


def _load_json(path: Path) -> Optional[object]:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _latest_history(folder: Path) -> Tuple[Optional[Path], Optional[Path]]:
    if not folder.exists():
        return None, None
    files = sorted(folder.glob("*.json"))
    if not files:
        return None, None
    latest = files[-1]
    previous = files[-2] if len(files) >= 2 else None
    return latest, previous


def _to_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return int(float(text))
        except ValueError:
            return default
    return default


def _to_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _build_roster_lookup(rosters: Iterable[Dict[str, object]]) -> Dict[Tuple[str, str], Dict[str, object]]:
    lookup: Dict[Tuple[str, str], Dict[str, object]] = {}
    for roster in rosters:
        team_slug = roster.get("team_slug")
        if not isinstance(team_slug, str):
            continue
        for player in roster.get("players", []):
            if not isinstance(player, dict):
                continue
            name = player.get("name", "")
            player_id = player.get("player_id")
            if not player_id:
                player_id = derive_player_id(team_slug, name, player.get("number"))
            payload = {
                "player_id": player_id,
                "name": name,
                "number": player.get("number"),
                "positions": player.get("positions") or [],
                "team_id": roster.get("team_id"),
                "team_name": roster.get("team_name"),
                "team_slug": team_slug,
                "meta": player,
            }
            for key in player_name_variants(str(name)):
                lookup.setdefault((team_slug, key), payload)
    return lookup


def _team_games_played(results: Iterable[Dict[str, object]]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for game in results:
        if not isinstance(game, dict):
            continue
        status = str(game.get("status", "")).lower()
        if status and status not in ("final", "completed"):
            continue
        for side_key in ("home_line", "away_line"):
            side = game.get(side_key)
            slug = None
            if isinstance(side, dict):
                slug = side.get("slug")
            if not slug:
                team_name = game.get("home") if side_key == "home_line" else game.get("away")
                if isinstance(team_name, str):
                    slug = slugify(team_name)
            if slug:
                counts[slug] += 1
    return counts


def _load_previous_stats() -> Dict[str, Dict[str, object]]:
    latest, previous = _latest_history(HISTORY_DIR / "player_stats")
    if not previous:
        return {}
    data = _load_json(previous)
    if not isinstance(data, list):
        return {}
    mapping: Dict[str, Dict[str, object]] = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        pid = row.get("player_id")
        if not pid:
            team_field = row.get("team") or row.get("Team")
            team_slug = slugify(team_field) if isinstance(team_field, str) else ""
            name = row.get("name") or row.get("player") or ""
            key = (team_slug, normalize_player_key(str(name)))
            mapping[str(key)] = row
        else:
            mapping[str(pid)] = row
    return mapping


def _lookup_previous(previous: Dict[str, Dict[str, object]], team_slug: str, player_id: str, name: str) -> Optional[Dict[str, object]]:
    if not previous:
        return None
    if player_id and str(player_id) in previous:
        return previous[str(player_id)]
    key = str((team_slug, normalize_player_key(name)))
    return previous.get(key)


def build_registry() -> List[Dict[str, object]]:
    rosters_data = _load_json(DATA_DIR / "rosters.json") or []
    stats_data = _load_json(DATA_DIR / "player_stats.json") or []
    results_data = _load_json(DATA_DIR / "results.json") or []

    if not isinstance(rosters_data, list):
        rosters_data = []
    if not isinstance(stats_data, list):
        stats_data = []
    if not isinstance(results_data, list):
        results_data = []

    roster_lookup = _build_roster_lookup(rosters_data)
    team_games = _team_games_played(results_data)
    previous_stats = _load_previous_stats()

    registry: Dict[str, Dict[str, object]] = {}

    # Seed registry from rosters so every player appears even if they have 0 GP.
    for payload in roster_lookup.values():
        pid = payload["player_id"]
        team_slug = payload["team_slug"]
        registry[pid] = {
            "player_id": pid,
            "name": payload["name"],
            "number": payload["number"],
            "positions": payload["positions"],
            "team_id": payload["team_id"],
            "team_name": payload["team_name"],
            "team_slug": team_slug,
            "games_played": 0,
            "goals": 0,
            "assists": 0,
            "points": 0,
            "penalty_minutes": 0,
            "points_per_game": 0.0,
            "team_games_played": team_games.get(team_slug, 0),
            "games_missed": team_games.get(team_slug, 0),
            "recent_points": None,
            "recent_games": None,
        }

    for stat in stats_data:
        if not isinstance(stat, dict):
            continue
        team_field = stat.get("team") or stat.get("Team")
        team_slug = slugify(team_field) if isinstance(team_field, str) else ""
        name = str(
            stat.get("name")
            or stat.get("player")
            or stat.get("player_name")
            or stat.get("playername")
            or ""
        )
        player_id = stat.get("player_id")
        if not player_id and team_slug:
            for key in player_name_variants(name):
                hit = roster_lookup.get((team_slug, key))
                if hit:
                    player_id = hit["player_id"]
                    break
        if not player_id and team_slug:
            player_id = derive_player_id(team_slug, name, stat.get("no"))

        team_games_played = team_games.get(team_slug, 0)
        games_played = _to_int(stat.get("gp"))
        goals = _to_int(stat.get("g"))
        assists = _to_int(stat.get("a"))
        points = _to_int(stat.get("pts")) or (goals + assists)
        pim = _to_int(stat.get("pim"))
        ppg = _to_float(stat.get("pts_g"))

        entry = registry.setdefault(
            player_id,
            {
                "player_id": player_id,
                "name": name,
                "number": stat.get("no") or stat.get("number"),
                "positions": stat.get("pos") or stat.get("positions") or [],
                "team_id": None,
                "team_name": team_field,
                "team_slug": team_slug or None,
                "games_played": 0,
                "goals": 0,
                "assists": 0,
                "points": 0,
                "penalty_minutes": 0,
                "points_per_game": 0.0,
                "team_games_played": team_games_played,
                "games_missed": team_games_played,
                "recent_points": None,
                "recent_games": None,
            },
        )

        if not entry.get("team_id"):
            roster_hit = roster_lookup.get((team_slug, normalize_player_key(name)))
            if roster_hit:
                entry["team_id"] = roster_hit["team_id"]
                entry["team_name"] = roster_hit["team_name"]
                entry["number"] = roster_hit["number"]
                entry["positions"] = roster_hit["positions"]

        entry["team_slug"] = team_slug or entry.get("team_slug")
        entry["team_games_played"] = team_games_played
        entry["name"] = name or entry.get("name")
        entry["games_played"] = games_played
        entry["goals"] = goals
        entry["assists"] = assists
        entry["points"] = points
        entry["penalty_minutes"] = pim
        entry["points_per_game"] = ppg if ppg else (points / games_played) if games_played else 0.0
        entry["games_missed"] = max(team_games_played - games_played, 0)

        previous = _lookup_previous(previous_stats, team_slug, player_id, name)
        if previous:
            prev_points = _to_int(previous.get("pts")) or (_to_int(previous.get("g")) + _to_int(previous.get("a")))
            prev_gp = _to_int(previous.get("gp"))
            delta_points = points - prev_points
            delta_gp = games_played - prev_gp
            entry["recent_points"] = delta_points
            entry["recent_games"] = delta_gp

    registry_list = list(registry.values())
    registry_list.sort(key=lambda item: (item.get("team_slug") or "", (item.get("number") or ""), item.get("name") or ""))
    return registry_list


def main() -> None:
    registry = build_registry()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()
    OUTPUT_PATH.write_text(json.dumps({"generated_at": timestamp, "players": registry}, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
