#!/usr/bin/env python3
"""
Generate a lightweight weekly report with standings movement and simple headlines.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"
REPORT_PATH = DATA_DIR / "weekly_report.json"
HEADLINES_PATH = DATA_DIR / "headlines.json"


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

    cutoff = datetime.now() - timedelta(days=days)
    recent: List[Dict[str, object]] = []
    for game in results:
        dt_raw = game.get("datetime")
        if not dt_raw:
            continue
        try:
            dt = datetime.fromisoformat(str(dt_raw))
        except ValueError:
            continue
        if dt >= cutoff:
            recent.append(game)
    return recent


def _generate_headlines(games: List[Dict[str, object]]) -> List[str]:
    headlines: List[str] = []
    for game in games:
        home = game.get("home")
        away = game.get("away")
        home_score = game.get("home_score")
        away_score = game.get("away_score")
        if home is None or away is None or home_score == "" or away_score == "":
            continue

        margin = None
        try:
            margin = abs(int(home_score) - int(away_score))
        except (TypeError, ValueError):
            pass

        if margin is not None and margin >= 5:
            tone = "dominates"
        elif margin == 1:
            tone = "edges"
        else:
            tone = "defeats"

        winner = home if int(home_score) >= int(away_score) else away
        loser = away if winner == home else home
        winner_score, loser_score = (home_score, away_score) if winner == home else (away_score, home_score)

        headline = f"{winner} {tone} {loser} {winner_score}-{loser_score}"
        headlines.append(headline)

    return headlines


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
    headlines = _generate_headlines(recent_games)

    report = {
        "generated_at": datetime.now().isoformat(),
        "standings_snapshot": latest.name if latest else None,
        "previous_snapshot": previous.name if previous else None,
        "standings_movements": movements,
        "recent_team_form": recent_summary,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    HEADLINES_PATH.write_text(json.dumps(headlines, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
