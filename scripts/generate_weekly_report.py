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

try:
    from openai_headlines import generate_ai_headline, enrich_games_with_ai, generate_rich_narrative
    OPENAI_HEADLINES_AVAILABLE = True
except ImportError:
    OPENAI_HEADLINES_AVAILABLE = False
    generate_ai_headline = None
    enrich_games_with_ai = None
    generate_rich_narrative = None

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


def _display_name(name: str) -> str:
    if "," in name:
        last, first = [segment.strip() for segment in name.split(",", 1)]
        return f"{first} {last}".strip()
    return name.strip()


def _player_statline(player: Dict[str, object]) -> Optional[tuple[str, str]]:
    goals = _safe_int(player.get("goals")) or 0
    assists = _safe_int(player.get("assists")) or 0
    if goals <= 0 and assists <= 0:
        return None

    parts: List[str] = []
    if goals >= 3:
        label = "hat trick"
        if goals > 3:
            label = f"hat trick ({goals}G)"
        parts.append(label)
    elif goals == 2:
        parts.append("brace (2G)")
    elif goals == 1:
        parts.append("1G")

    if assists:
        assist_label = f"{assists}A"
        if assists == 1:
            assist_label = "1A"
        if goals and assists:
            parts.append(f"{assist_label}")
        elif not goals:
            helper = "helpers" if assists > 1 else "helper"
            parts.append(f"{assists} {helper}")

    stat_text = " and ".join(parts)
    if not stat_text:
        stat_text = f"{assists}A"
    return _display_name(str(player.get("name", "Unknown"))), stat_text


def _pick_phrase(options: List[str], seed: int) -> str:
    if not options:
        return ""
    index = seed % len(options)
    return options[index]


def _headline_seed(game_id: str) -> int:
    if not game_id:
        return 0
    try:
        return int(game_id) % 97
    except ValueError:
        return sum(ord(ch) for ch in game_id)


def _player_highlight_phrase(game: Dict[str, object], winner_side: str) -> Optional[str]:
    stats = game.get("player_stats")
    if not isinstance(stats, dict):
        return None

    winners = stats.get(winner_side)
    if not isinstance(winners, list):
        return None

    enriched: List[tuple[int, int, int, Dict[str, object]]] = []
    for player in winners:
        if not isinstance(player, dict):
            continue
        goals = _safe_int(player.get("goals")) or 0
        assists = _safe_int(player.get("assists")) or 0
        points = goals + assists
        if points <= 0:
            continue
        enriched.append((goals, points, assists, player))

    if not enriched:
        return None

    enriched.sort(key=lambda item: (item[0], item[1], item[2], str(item[3].get("name", ""))), reverse=True)
    primary_player = enriched[0][3]
    primary = _player_statline(primary_player)
    if not primary:
        return None

    primary_seed = sum(ord(ch) for ch in primary[0])
    primary_leads = [
        "sparked by",
        "powered by",
        "fueled by",
        "driven by",
        "lifted by",
    ]
    phrase = f"{_pick_phrase(primary_leads, primary_seed)} {primary[0]}'s {primary[1]}"

    secondary = None
    for _, _, _, candidate in enriched[1:]:
        match = _player_statline(candidate)
        if match:
            secondary = match
            break

    if secondary:
        secondary_seed = sum(ord(ch) for ch in secondary[0])
        secondary_leads = [
            "while",
            "as",
            "with",
            "and",
        ]
        secondary_verbs = [
            "adding",
            "chipping in",
            "contributing",
            "supplying",
        ]
        phrase += (
            f", {_pick_phrase(secondary_leads, secondary_seed)} {secondary[0]}"
            f" {_pick_phrase(secondary_verbs, secondary_seed + primary_seed)} {secondary[1]}"
        )

    return phrase


def _result_verb(margin: int, winner_score: int, loser_score: int, game_id: str) -> str:
    blowout = ["obliterates", "thrashes", "trounces", "routs"]
    big_win = ["steamrolls", "dominates", "dismantles", "pummels"]
    comfortable = ["crushes", "cruises past", "handles", "dispatches"]
    moderate = ["tops", "outduels", "overcomes", "best"]
    tight = ["edges", "nips", "squeaks by", "slips past"]
    shootout = ["outguns", "outlasts", "surges past", "prevails over"]

    seed = _headline_seed(game_id)

    if margin >= 6:
        return _pick_phrase(blowout, seed)
    if margin >= 4:
        return _pick_phrase(big_win, seed)
    if margin == 3:
        return _pick_phrase(comfortable, seed)
    if margin == 2:
        return _pick_phrase(moderate, seed)
    if margin == 1:
        return _pick_phrase(tight, seed)
    return _pick_phrase(shootout if winner_score >= 6 else moderate, seed)


def _compose_headline(game: Dict[str, object]) -> Optional[str]:
    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score"))
    away_score = _safe_int(game.get("away_score"))
    game_id = str(game.get("game_id", ""))
    if (
        home is None
        or away is None
        or home_score is None
        or away_score is None
    ):
        return None

    if home_score == away_score:
        tie_phrases = [
            "battle to a draw with",
            "skate to a draw with",
            "finish deadlocked with",
            "settle for a tie with",
        ]
        tone = _pick_phrase(tie_phrases, _headline_seed(game_id))
        return f"{home} {tone} {away} {home_score}-{away_score}"

    margin = abs(home_score - away_score)
    tone = _result_verb(margin, max(home_score, away_score), min(home_score, away_score), game_id)

    if home_score >= away_score:
        winner, loser = home, away
        winner_score, loser_score = home_score, away_score
        winner_side = "home"
    else:
        winner, loser = away, home
        winner_score, loser_score = away_score, home_score
        winner_side = "away"

    headline = f"{winner} {tone} {loser} {winner_score}-{loser_score}"

    highlight = _player_highlight_phrase(game, winner_side)
    if highlight:
        headline = f"{headline} {highlight}"

    return headline


def _ensure_headlines(
    games: List[Dict[str, object]],
    existing: Dict[str, Dict[str, object]],
    standings: Optional[List[Dict[str, object]]] = None
) -> List[Dict[str, object]]:
    now_iso = datetime.now(timezone.utc).isoformat()
    entries: List[Dict[str, object]] = []

    for game in games:
        game_id = game.get("game_id")
        if not game_id:
            continue
        game_id_str = str(game_id)

        # Try AI headline first, fall back to template
        headline = None
        ai_generated = False

        if OPENAI_HEADLINES_AVAILABLE and generate_ai_headline:
            try:
                headline = generate_ai_headline(game)
                if headline:
                    ai_generated = True
            except Exception as e:
                print(f"AI headline generation failed for game {game_id}: {e}")

        if not headline:
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
                "ai_generated": ai_generated,
                "created_at": now_iso,
                "updated_at": now_iso,
            }
        else:
            if entry.get("headline") != headline:
                entry["headline"] = headline
                entry["ai_generated"] = ai_generated
                entry["updated_at"] = now_iso

        # Generate rich narrative for recent games (last 5)
        narrative = entry.get("narrative")
        if not narrative and OPENAI_HEADLINES_AVAILABLE and generate_rich_narrative:
            try:
                narrative = generate_rich_narrative(game, standings=standings)
                if narrative:
                    entry["narrative"] = narrative
                    entry["updated_at"] = now_iso
            except Exception as e:
                print(f"Narrative generation failed for game {game_id}: {e}")

        entry["game_datetime"] = iso_dt
        entry["home_team"] = _team_name(game, "home")
        entry["away_team"] = _team_name(game, "away")
        entry["home_score"] = _safe_int(game.get("home_score"))
        entry["away_score"] = _safe_int(game.get("away_score"))
        entry["summary_url"] = game.get("summary_url")
        entry["box_score_url"] = game.get("box_score_url")
        entries.append(entry)

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


def _load_recent_results(days: Optional[int] = 7) -> List[Dict[str, object]]:
    results = _load_json(DATA_DIR / "results.json")
    if not isinstance(results, list):
        return []

    cutoff = None
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    recent: List[Dict[str, object]] = []
    for game in results:
        if str(game.get("status", "")).lower() != "final":
            continue
        dt = _parse_game_datetime(game.get("datetime"))
        if cutoff is not None and (not dt or dt < cutoff):
            continue
        game_copy = dict(game)
        if dt:
            game_copy["_dt"] = dt
        recent.append(game_copy)

    recent.sort(
        key=lambda item: item.get("_dt") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    for game in recent:
        game.pop("_dt", None)
    return recent


def _game_key(game: Dict[str, object]) -> tuple[str, str, str]:
    home_line = game.get("home_line") or {}
    away_line = game.get("away_line") or {}
    home_slug = str(home_line.get("slug") or game.get("home", "")).strip().lower()
    away_slug = str(away_line.get("slug") or game.get("away", "")).strip().lower()
    dt = str(
        game.get("datetime")
        or game.get("start_local")
        or game.get("start_utc")
        or game.get("game_id")
    )
    return (home_slug, away_slug, dt)


def _total_player_stats(game: Dict[str, object]) -> int:
    stats = game.get("player_stats")
    if not isinstance(stats, dict):
        return 0
    total = 0
    for roster in stats.values():
        if isinstance(roster, list):
            total += len(roster)
    return total


def _unique_games(games: List[Dict[str, object]]) -> List[Dict[str, object]]:
    best_by_key: Dict[tuple[str, str, str], Dict[str, object]] = {}
    winner_counts: Dict[tuple[str, str, str], int] = {}
    for game in games:
        key = _game_key(game)
        total_stats = _total_player_stats(game)
        scoreboard_len = len(game.get("scoreboard") or [])
        winner_side = "home" if (_safe_int(game.get("home_score")) or 0) >= (_safe_int(game.get("away_score")) or 0) else "away"
        stats = game.get("player_stats") or {}
        winner_stat_count = len(stats.get(winner_side, [])) if isinstance(stats.get(winner_side), list) else 0
        existing = best_by_key.get(key)
        if existing is None:
            best_by_key[key] = game
            winner_counts[key] = winner_stat_count
            continue

        existing_stats = _total_player_stats(existing)
        existing_scoreboard = len(existing.get("scoreboard") or [])
        existing_winner_stat = winner_counts.get(key, 0)

        if total_stats > existing_stats:
            best_by_key[key] = game
            winner_counts[key] = winner_stat_count
        elif total_stats == existing_stats and scoreboard_len > existing_scoreboard:
            best_by_key[key] = game
            winner_counts[key] = winner_stat_count
        elif total_stats == existing_stats and scoreboard_len == existing_scoreboard and winner_stat_count > existing_winner_stat:
            best_by_key[key] = game
            winner_counts[key] = winner_stat_count

    unique_games = list(best_by_key.values())
    unique_games.sort(
        key=lambda item: _parse_game_datetime(item.get("datetime"))
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return unique_games


def _sorted_games(games: List[Dict[str, object]]) -> List[Dict[str, object]]:
    enriched: List[tuple[datetime, Dict[str, object]]] = []
    for game in games:
        dt = _parse_game_datetime(game.get("datetime"))
        if dt is None:
            dt = datetime.min.replace(tzinfo=timezone.utc)
        enriched.append((dt, game))
    enriched.sort(key=lambda item: item[0], reverse=True)
    return [item[1] for item in enriched]


def _summarize_recent_results(games: List[Dict[str, object]]) -> List[Dict[str, object]]:
    summary: Dict[str, Dict[str, int]] = defaultdict(lambda: {"played": 0, "wins": 0, "losses": 0, "ties": 0})

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
            summary[home]["ties"] += 1
            summary[away]["ties"] += 1

        summary[home]["played"] += 1
        summary[away]["played"] += 1

    standings = [
        {"team": team, **stats}
        for team, stats in summary.items()
    ]
    standings.sort(key=lambda item: (item["wins"], item.get("ties", 0), -item["losses"]), reverse=True)
    return standings


def main() -> None:
    latest, previous = _latest_history(HISTORY_DIR / "standings")
    current_snapshot = _load_standings_snapshot(latest)
    previous_snapshot = _load_standings_snapshot(previous)

    movements = _compute_movements(current_snapshot, previous_snapshot)
    recent_games = _load_recent_results(days=7)
    all_games = _unique_games(_sorted_games(_load_recent_results(days=None)))
    recent_summary = _summarize_recent_results(recent_games)
    headline_index = _load_headline_index()

    # Load standings for narrative context
    standings_data = _load_json(DATA_DIR / "standings.json")
    standings_list = standings_data if isinstance(standings_data, list) else []

    headline_entries = _ensure_headlines(all_games, headline_index, standings=standings_list)

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
