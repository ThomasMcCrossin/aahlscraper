#!/usr/bin/env python3
"""
Generate a lightweight weekly report with standings movement and simple headlines.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
REPORT_PATH = DATA_DIR / "weekly_report.json"
HEADLINES_PATH = DATA_DIR / "headlines.json"

try:
    from build_player_registry import main as build_player_registry_main
except ImportError:
    build_player_registry_main = None

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


def _parse_game_datetime(value: object) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _safe_int(value: object) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            try:
                return int(float(text))
            except (ValueError, TypeError):
                return None
    return None


def _team_name(game: Dict[str, object], side: str) -> Optional[str]:
    line = game.get(f"{side}_line")
    if isinstance(line, dict) and line.get("name"):
        return str(line["name"])
    value = game.get(side)
    if isinstance(value, str):
        return value
    return None


def _load_headline_index() -> Dict[str, Dict[str, object]]:
    raw = _load_json(HEADLINES_PATH)
    if isinstance(raw, dict):
        entries = raw.get("headlines", [])
    elif isinstance(raw, list):
        # Legacy format: discard auto-generated list to avoid duplicates
        entries = []
    else:
        entries = []

    index: Dict[str, Dict[str, object]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        identifier = entry.get("game_id")
        if not identifier:
            continue
        index[str(identifier)] = dict(entry)
    return index


def _compose_headline(game: Dict[str, object]) -> Optional[str]:
    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score"))
    away_score = _safe_int(game.get("away_score"))
    if (
        home is None
        or away is None
        or home_score is None
        or away_score is None
    ):
        return None

    margin = abs(home_score - away_score)
    if margin >= 5:
        tone = "dominates"
    elif margin == 1:
        tone = "edges"
    else:
        tone = "defeats"

    if home_score >= away_score:
        winner, loser = home, away
        winner_score, loser_score = home_score, away_score
    else:
        winner, loser = away, home
        winner_score, loser_score = away_score, home_score

    return f"{winner} {tone} {loser} {winner_score}-{loser_score}"


def _ensure_headlines(games: List[Dict[str, object]], existing: Dict[str, Dict[str, object]]) -> List[Dict[str, object]]:
    now_iso = datetime.now(timezone.utc).isoformat()
    entries: List[Dict[str, object]] = []

    def sort_key(game: Dict[str, object]) -> tuple[int, Optional[datetime]]:
        dt = _parse_game_datetime(game.get("datetime"))
        # Sort primarily by datetime descending, fallback to game id
        return (0 if dt else 1, dt or datetime.min.replace(tzinfo=timezone.utc))

    for game in sorted(games, key=sort_key):
        game_id = game.get("game_id")
        if not game_id:
            continue
        game_id_str = str(game_id)

        headline = _compose_headline(game)
        if not headline:
            continue

        existing_entry = existing.get(game_id_str, {})
        entry = dict(existing_entry)

        dt = _parse_game_datetime(game.get("datetime"))
        iso_dt = dt.isoformat() if dt else None

        if not entry:
            entry = {
                "game_id": game_id_str,
                "headline": headline,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        else:
            if entry.get("headline") != headline:
                entry["headline"] = headline
                entry["updated_at"] = now_iso

        entry["game_datetime"] = iso_dt
        entry["home_team"] = _team_name(game, "home")
        entry["away_team"] = _team_name(game, "away")
        entry["home_score"] = _safe_int(game.get("home_score"))
        entry["away_score"] = _safe_int(game.get("away_score"))
        entry["summary_url"] = game.get("summary_url")
        entry["box_score_url"] = game.get("box_score_url")
        entries.append(entry)

    # Most recent games first
    entries.sort(key=lambda item: (item.get("game_datetime") or "", item.get("game_id")), reverse=True)
    return entries


def _standing_points(team: Dict[str, object]) -> int:
    for key in ("points", "Points", "pts"):
        value = team.get(key)
        if value and str(value).isdigit():
            return int(value)
    return 0


def _standing_name(team: Dict[str, object]) -> str:
    for key in ("team", "Team"):
        value = team.get(key)
        if value:
            return str(value)
    return "Unknown"


def _load_standings_snapshot(path: Optional[Path]) -> Dict[str, Dict[str, object]]:
    if path is None:
        return {}
    data = _load_json(path)
    if not isinstance(data, list):
        return {}
    return {_standing_name(team): team for team in data}


def _compute_movements(
    current: Dict[str, Dict[str, object]],
    previous: Dict[str, Dict[str, object]],
) -> List[Dict[str, object]]:
    movements: List[Dict[str, object]] = []
    for team_name, team in current.items():
        current_points = _standing_points(team)
        previous_points = _standing_points(previous.get(team_name, {}))
        delta = current_points - previous_points
        movements.append(
            {
                "team": team_name,
                "current_points": current_points,
                "previous_points": previous_points,
                "points_change": delta,
            }
        )

    movements.sort(key=lambda item: item["points_change"], reverse=True)
    return movements


def _load_recent_results(days: int = 7) -> List[Dict[str, object]]:
    results = _load_json(DATA_DIR / "results.json")
    if not isinstance(results, list):
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent: List[Dict[str, object]] = []
    for game in results:
        dt = _parse_game_datetime(game.get("datetime"))
        if not dt:
            continue
        if dt >= cutoff:
            recent.append(game)
    return recent


def _summarize_recent_results(games: List[Dict[str, object]]) -> List[Dict[str, object]]:
    summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"played": 0, "wins": 0, "losses": 0})

    for game in games:
        home = str(game.get("home"))
        away = str(game.get("away"))
        try:
            home_score = int(game.get("home_score"))
            away_score = int(game.get("away_score"))
        except (TypeError, ValueError):
            continue

        if home_score > away_score:
            summary[home]["wins"] += 1
            summary[away]["losses"] += 1
        elif away_score > home_score:
            summary[away]["wins"] += 1
            summary[home]["losses"] += 1
        else:
            # treat ties as half-win/half-loss
            summary[home]["wins"] += 0
            summary[away]["wins"] += 0

        summary[home]["played"] += 1
        summary[away]["played"] += 1

    standings = [
        {"team": team, **stats}
        for team, stats in summary.items()
    ]
    standings.sort(key=lambda item: (item["wins"], -item["losses"]), reverse=True)
    return standings


def main() -> None:
    latest, previous = _latest_history(HISTORY_DIR / "standings")
    current_snapshot = _load_standings_snapshot(latest)
    previous_snapshot = _load_standings_snapshot(previous)

    movements = _compute_movements(current_snapshot, previous_snapshot)
    recent_games = _load_recent_results(days=7)
    recent_summary = _summarize_recent_results(recent_games)
    headline_index = _load_headline_index()
    headline_entries = _ensure_headlines(recent_games, headline_index)

    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        "generated_at": generated_at,
        "standings_snapshot": latest.name if latest else None,
        "previous_snapshot": previous.name if previous else None,
        "standings_movements": movements,
        "recent_team_form": recent_summary,
        "game_headlines": [
            {
                "game_id": entry["game_id"],
                "headline": entry["headline"],
                "game_datetime": entry.get("game_datetime"),
            }
            for entry in headline_entries
        ],
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    HEADLINES_PATH.write_text(
        json.dumps({"generated_at": generated_at, "headlines": headline_entries}, indent=2),
        encoding="utf-8",
    )

    if build_player_registry_main is not None:
        build_player_registry_main()


if __name__ == "__main__":
    main()
