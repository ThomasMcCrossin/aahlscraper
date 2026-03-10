#!/usr/bin/env python3
"""
Generate a compact playoff- and season-analysis layer under data/v2.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = DATA_DIR / "v2"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aahlscraper import AmherstHockeyScraper
from aahlscraper.game_normalization import (
    canonical_game_key_for_mapping,
    dedupe_game_mappings,
    matchup_key_for_mapping,
    source_game_ids_for_mapping,
)
from aahlscraper.game_time import halifax_now, local_date_key, mapping_game_local_start, mapping_game_utc_start
from aahlscraper.utils import slugify

PLAYOFF_CONFIG_PATH = SRC_DIR / "aahlscraper" / "data" / "playoffs.json"


def _load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _safe_int(value: object, default: int = 0) -> int:
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


def _display_name(name: str) -> str:
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
        return f"{first} {last}".strip()
    return name.strip()


def _player_points(player: Mapping[str, object]) -> int:
    points = _safe_int(player.get("points"))
    if points:
        return points
    return _safe_int(player.get("goals")) + _safe_int(player.get("assists"))


def _load_players() -> List[Dict[str, object]]:
    registry = _load_json(DATA_DIR / "player_registry.json")
    if isinstance(registry, dict):
        players = registry.get("players", [])
    elif isinstance(registry, list):
        players = registry
    else:
        players = []
    return [player for player in players if isinstance(player, dict)]


def _load_standings() -> List[Dict[str, object]]:
    standings = _load_json(DATA_DIR / "standings.json")
    if not isinstance(standings, list):
        return []

    ranked: List[Dict[str, object]] = []
    for index, team in enumerate(standings, start=1):
        if not isinstance(team, dict):
            continue
        name = str(team.get("team") or team.get("Team") or "Unknown")
        ranked.append(
            {
                "rank": index,
                "team_name": name,
                "team_slug": slugify(name),
                "points": _safe_int(team.get("pts") or team.get("points")),
                "wins": _safe_int(team.get("wins")),
                "losses": _safe_int(team.get("losses")),
                "ties": _safe_int(team.get("ties")),
                "goals_for": _safe_int(team.get("gf")),
                "goals_against": _safe_int(team.get("ga")),
                "last_10": str(team.get("last_10") or ""),
                "streak": str(team.get("streak") or ""),
                "record": str(team.get("record") or ""),
            }
        )
    return ranked


def _load_team_meta() -> Dict[str, Dict[str, object]]:
    payload = _load_json(DATA_DIR / "teams.json")
    teams = payload.get("teams", []) if isinstance(payload, dict) else []
    lookup: Dict[str, Dict[str, object]] = {}
    for team in teams:
        if not isinstance(team, dict):
            continue
        slug = str(team.get("slug") or "").strip()
        if not slug:
            continue
        lookup[slug] = team
    return lookup


def _load_playoff_config() -> Dict[str, object]:
    payload = _load_json(PLAYOFF_CONFIG_PATH)
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid playoff config: {PLAYOFF_CONFIG_PATH}")
    return payload


def _load_live_source_metadata() -> Dict[Tuple[str, str, str, str], Dict[str, object]]:
    try:
        scraper = AmherstHockeyScraper(team_id="DSMALL")
        games = scraper._load_games()
    except Exception as exc:
        print(f"Warning: unable to load live source metadata: {exc}")
        return {}

    metadata: Dict[Tuple[str, str, str, str], Dict[str, object]] = {}
    for game in games:
        record = game.to_dict(include_source_metadata=True)
        metadata[canonical_game_key_for_mapping(record)] = record
    return metadata


def _series_definitions(playoffs: Mapping[str, object]) -> Dict[Tuple[str, str], Dict[str, object]]:
    definitions: Dict[Tuple[str, str], Dict[str, object]] = {}
    rounds = playoffs.get("rounds", [])
    if not isinstance(rounds, list):
        return definitions

    for round_entry in rounds:
        if not isinstance(round_entry, dict):
            continue
        for series in round_entry.get("series", []):
            if not isinstance(series, dict):
                continue
            matchup = tuple(
                sorted(
                    (
                        str(series.get("higher_seed_slug") or ""),
                        str(series.get("lower_seed_slug") or ""),
                    )
                )
            )
            if not matchup[0] or not matchup[1]:
                continue
            definitions[matchup] = {
                "round_id": round_entry.get("round_id"),
                "round_label": round_entry.get("label"),
                "round_start_date": round_entry.get("start_date"),
                "best_of": round_entry.get("best_of"),
                **series,
            }
    return definitions


def _playoff_assignment(game: Mapping[str, object], series_lookup: Mapping[Tuple[str, str], Dict[str, object]]) -> Dict[str, object]:
    matchup = matchup_key_for_mapping(game)
    series = series_lookup.get(matchup)
    if not series:
        return {"season_phase": "regular_season", "playoff_series_id": None, "playoff_round_id": None}

    game_date = local_date_key(mapping_game_local_start(game))
    round_start = str(series.get("round_start_date") or "")
    known_dates = {str(value) for value in series.get("known_game_dates", []) if value}

    if game_date and ((round_start and game_date >= round_start) or game_date in known_dates):
        return {
            "season_phase": "playoffs",
            "playoff_series_id": series.get("series_id"),
            "playoff_round_id": series.get("round_id"),
        }

    return {"season_phase": "regular_season", "playoff_series_id": None, "playoff_round_id": None}


def _notable_performers(game: Mapping[str, object], limit: int = 4) -> List[Dict[str, object]]:
    stats = game.get("player_stats")
    if not isinstance(stats, dict):
        return []

    enriched: List[Dict[str, object]] = []
    for side, roster in stats.items():
        if not isinstance(roster, list):
            continue
        team_name = str(game.get("home") if side == "home" else game.get("away") or "")
        team_slug = slugify(team_name)
        for player in roster:
            if not isinstance(player, dict):
                continue
            goals = _safe_int(player.get("goals"))
            assists = _safe_int(player.get("assists"))
            points = _player_points(player)
            if points <= 0 and goals <= 0 and assists <= 0:
                continue
            enriched.append(
                {
                    "player_id": player.get("player_id"),
                    "name": player.get("name"),
                    "display_name": _display_name(str(player.get("name") or "Unknown")),
                    "team_name": team_name,
                    "team_slug": team_slug,
                    "goals": goals,
                    "assists": assists,
                    "points": points,
                }
            )

    enriched.sort(
        key=lambda item: (item["points"], item["goals"], item["assists"], str(item["name"] or "")),
        reverse=True,
    )
    return enriched[:limit]


def _compact_game_record(
    game: Mapping[str, object],
    *,
    live_metadata: Mapping[Tuple[str, str, str, str], Dict[str, object]],
    series_lookup: Mapping[Tuple[str, str], Dict[str, object]],
) -> Dict[str, object]:
    key = canonical_game_key_for_mapping(game)
    live_record = live_metadata.get(key, {})
    local_start = mapping_game_local_start(game)
    utc_start = mapping_game_utc_start(game)
    assignment = _playoff_assignment(game, series_lookup)

    home_name = str(game.get("home") or "")
    away_name = str(game.get("away") or "")
    home_slug = slugify(home_name)
    away_slug = slugify(away_name)

    source_ids = source_game_ids_for_mapping(live_record) or source_game_ids_for_mapping(game)
    if not source_ids:
        game_id = str(game.get("game_id") or "").strip()
        if game_id:
            source_ids = [game_id]

    return {
        "canonical_game_id": str(game.get("game_id") or ""),
        "source_game_ids": source_ids,
        "source_game_count": len(source_ids),
        "status": game.get("status"),
        "season_phase": assignment["season_phase"],
        "playoff_round_id": assignment["playoff_round_id"],
        "playoff_series_id": assignment["playoff_series_id"],
        "location": game.get("location"),
        "division": game.get("division"),
        "start_local": local_start.isoformat() if local_start else None,
        "start_utc": utc_start.isoformat() if utc_start else None,
        "local_date": local_start.strftime("%Y-%m-%d") if local_start else None,
        "local_time": local_start.strftime("%I:%M %p").lstrip("0") if local_start else None,
        "home_team": home_name,
        "home_slug": home_slug,
        "away_team": away_name,
        "away_slug": away_slug,
        "home_score": _safe_int(game.get("home_score")) if game.get("home_score") not in ("", None) else None,
        "away_score": _safe_int(game.get("away_score")) if game.get("away_score") not in ("", None) else None,
        "result": game.get("result"),
        "box_score_url": game.get("box_score_url"),
        "summary_url": game.get("summary_url"),
        "scoring_event_count": len(game.get("scoring_summary") or []) if isinstance(game.get("scoring_summary"), list) else 0,
        "penalty_count": len(game.get("penalties") or []) if isinstance(game.get("penalties"), list) else 0,
        "notable_performers": _notable_performers(game),
    }


def _load_canonical_games() -> List[Dict[str, object]]:
    schedule = _load_json(DATA_DIR / "schedule.json")
    results = _load_json(DATA_DIR / "results.json")
    if not isinstance(schedule, list):
        schedule = []
    if not isinstance(results, list):
        results = []

    live_metadata = _load_live_source_metadata()
    playoffs = _load_playoff_config()
    series_lookup = _series_definitions(playoffs)

    combined = dedupe_game_mappings([*results, *schedule])
    compact = [
        _compact_game_record(game, live_metadata=live_metadata, series_lookup=series_lookup)
        for game in combined
    ]
    compact.sort(key=lambda game: (game.get("start_local") or "", game.get("canonical_game_id") or ""))
    return compact


def _leaderboards(players: Iterable[Mapping[str, object]], *, limit: int = 10) -> Dict[str, List[Dict[str, object]]]:
    player_list = [dict(player) for player in players]

    def top(metric: str) -> List[Dict[str, object]]:
        sorted_players = sorted(
            player_list,
            key=lambda player: (
                _safe_int(player.get(metric)),
                _player_points(player),
                _safe_int(player.get("goals")),
                str(player.get("name") or ""),
            ),
            reverse=True,
        )
        rows: List[Dict[str, object]] = []
        for player in sorted_players[:limit]:
            rows.append(
                {
                    "player_id": player.get("player_id"),
                    "name": player.get("name"),
                    "display_name": _display_name(str(player.get("name") or "Unknown")),
                    "team_slug": player.get("team_slug"),
                    "team_name": player.get("team_name"),
                    "games_played": _safe_int(player.get("games_played")),
                    "goals": _safe_int(player.get("goals")),
                    "assists": _safe_int(player.get("assists")),
                    "points": _player_points(player),
                }
            )
        return rows

    return {
        "points": top("points"),
        "goals": top("goals"),
        "assists": top("assists"),
    }


def _head_to_head_matrix(games: Iterable[Mapping[str, object]]) -> List[Dict[str, object]]:
    summary: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for game in games:
        if game.get("season_phase") != "regular_season" or str(game.get("status")) != "final":
            continue

        matchup = tuple(sorted((str(game.get("home_slug") or ""), str(game.get("away_slug") or ""))))
        if not matchup[0] or not matchup[1]:
            continue

        entry = summary.setdefault(
            matchup,
            {
                "matchup": list(matchup),
                "games_played": 0,
                "teams": {
                    matchup[0]: {"wins": 0, "losses": 0, "ties": 0, "goals_for": 0, "goals_against": 0},
                    matchup[1]: {"wins": 0, "losses": 0, "ties": 0, "goals_for": 0, "goals_against": 0},
                },
            },
        )

        home_slug = str(game.get("home_slug") or "")
        away_slug = str(game.get("away_slug") or "")
        home_score = _safe_int(game.get("home_score"), default=-1)
        away_score = _safe_int(game.get("away_score"), default=-1)
        if home_score < 0 or away_score < 0:
            continue

        entry["games_played"] += 1
        entry["teams"][home_slug]["goals_for"] += home_score
        entry["teams"][home_slug]["goals_against"] += away_score
        entry["teams"][away_slug]["goals_for"] += away_score
        entry["teams"][away_slug]["goals_against"] += home_score

        if home_score > away_score:
            entry["teams"][home_slug]["wins"] += 1
            entry["teams"][away_slug]["losses"] += 1
        elif away_score > home_score:
            entry["teams"][away_slug]["wins"] += 1
            entry["teams"][home_slug]["losses"] += 1
        else:
            entry["teams"][home_slug]["ties"] += 1
            entry["teams"][away_slug]["ties"] += 1

    rows = list(summary.values())
    rows.sort(key=lambda row: tuple(row["matchup"]))
    return rows


def _series_state_label(series: Mapping[str, object], wins: Mapping[str, int], team_meta: Mapping[str, Dict[str, object]]) -> str:
    higher = str(series.get("higher_seed_slug") or "")
    lower = str(series.get("lower_seed_slug") or "")
    higher_wins = wins.get(higher, 0)
    lower_wins = wins.get(lower, 0)
    wins_needed = (_safe_int(series.get("best_of"), 3) // 2) + 1

    higher_name = str(team_meta.get(higher, {}).get("name") or series.get("higher_seed_name") or higher)
    lower_name = str(team_meta.get(lower, {}).get("name") or series.get("lower_seed_name") or lower)

    if higher_wins >= wins_needed:
        return f"{higher_name} wins the series {higher_wins}-{lower_wins}"
    if lower_wins >= wins_needed:
        return f"{lower_name} wins the series {lower_wins}-{higher_wins}"
    if higher_wins == lower_wins:
        return f"Series tied {higher_wins}-{lower_wins}"
    if higher_wins > lower_wins:
        return f"{higher_name} leads {higher_wins}-{lower_wins}"
    return f"{lower_name} leads {lower_wins}-{higher_wins}"


def _build_series_data(
    games: List[Dict[str, object]],
    playoffs: Mapping[str, object],
    standings: List[Dict[str, object]],
    team_meta: Mapping[str, Dict[str, object]],
    head_to_head: List[Dict[str, object]],
) -> Dict[str, object]:
    standings_by_slug = {team["team_slug"]: team for team in standings}
    h2h_by_matchup = {tuple(row["matchup"]): row for row in head_to_head}
    all_series: List[Dict[str, object]] = []

    for matchup, series in _series_definitions(playoffs).items():
        series_games = [game for game in games if game.get("playoff_series_id") == series.get("series_id")]
        series_games.sort(key=lambda game: game.get("start_local") or "")

        wins: Dict[str, int] = defaultdict(int)
        completed_games: List[Dict[str, object]] = []
        upcoming_games: List[Dict[str, object]] = []
        for game in series_games:
            status = str(game.get("status") or "")
            if status == "final":
                completed_games.append(game)
                home_score = _safe_int(game.get("home_score"), default=-1)
                away_score = _safe_int(game.get("away_score"), default=-1)
                if home_score > away_score:
                    wins[str(game.get("home_slug") or "")] += 1
                elif away_score > home_score:
                    wins[str(game.get("away_slug") or "")] += 1
            else:
                upcoming_games.append(game)

        best_of = _safe_int(series.get("best_of"), 3)
        wins_needed = (best_of // 2) + 1
        higher_slug = str(series.get("higher_seed_slug") or "")
        lower_slug = str(series.get("lower_seed_slug") or "")
        next_game = None
        if upcoming_games:
            now = halifax_now().isoformat()
            future = [game for game in upcoming_games if (game.get("start_local") or "") >= now]
            next_game = future[0] if future else upcoming_games[0]

        series_payload = {
            "series_id": series.get("series_id"),
            "round_id": series.get("round_id"),
            "round_label": series.get("round_label"),
            "label": f"{series.get('higher_seed_name')} vs {series.get('lower_seed_name')}",
            "best_of": best_of,
            "wins_needed": wins_needed,
            "higher_seed": {
                "seed": _safe_int(series.get("higher_seed")),
                "team_slug": higher_slug,
                "team_name": team_meta.get(higher_slug, {}).get("name") or series.get("higher_seed_name"),
                "standing": standings_by_slug.get(higher_slug),
            },
            "lower_seed": {
                "seed": _safe_int(series.get("lower_seed")),
                "team_slug": lower_slug,
                "team_name": team_meta.get(lower_slug, {}).get("name") or series.get("lower_seed_name"),
                "standing": standings_by_slug.get(lower_slug),
            },
            "wins": {higher_slug: wins.get(higher_slug, 0), lower_slug: wins.get(lower_slug, 0)},
            "status": "complete" if max(wins.values() or [0]) >= wins_needed else ("active" if completed_games else "upcoming"),
            "state_label": _series_state_label(series, wins, team_meta),
            "completed_games": completed_games,
            "upcoming_games": upcoming_games,
            "next_game": next_game,
            "known_game_dates": series.get("known_game_dates", []),
            "notes": series.get("notes"),
            "elimination_pressure": [
                {
                    "team_slug": slug,
                    "team_name": team_meta.get(slug, {}).get("name") or slug,
                    "wins": wins.get(slug, 0),
                    "losses": len(completed_games) - wins.get(slug, 0),
                    "wins_needed": max(wins_needed - wins.get(slug, 0), 0),
                    "facing_elimination": len(completed_games) - wins.get(slug, 0) == wins_needed - 1,
                }
                for slug in (higher_slug, lower_slug)
            ],
            "regular_season_head_to_head": h2h_by_matchup.get(matchup),
        }
        all_series.append(series_payload)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season_id": playoffs.get("season_id"),
        "timezone": playoffs.get("timezone"),
        "rounds": [
            {
                "round_id": round_entry.get("round_id"),
                "label": round_entry.get("label"),
                "best_of": round_entry.get("best_of"),
                "series": [series for series in all_series if series.get("round_id") == round_entry.get("round_id")],
            }
            for round_entry in playoffs.get("rounds", [])
            if isinstance(round_entry, dict)
        ],
    }


def _team_head_to_head(team_slug: str, head_to_head: Iterable[Mapping[str, object]], team_meta: Mapping[str, Dict[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for matchup in head_to_head:
        teams = matchup.get("teams", {})
        if not isinstance(teams, dict) or team_slug not in teams:
            continue
        opponents = [slug for slug in matchup.get("matchup", []) if slug != team_slug]
        opponent_slug = opponents[0] if opponents else None
        rows.append(
            {
                "opponent_slug": opponent_slug,
                "opponent_name": team_meta.get(opponent_slug or "", {}).get("name") if opponent_slug else None,
                "games_played": matchup.get("games_played"),
                "record": teams.get(team_slug),
            }
        )
    rows.sort(key=lambda row: str(row.get("opponent_slug") or ""))
    return rows


def _recent_team_results(team_slug: str, games: Iterable[Mapping[str, object]], limit: int = 5) -> List[Dict[str, object]]:
    relevant = [
        game for game in games
        if str(game.get("status") or "") == "final"
        and (str(game.get("home_slug") or "") == team_slug or str(game.get("away_slug") or "") == team_slug)
    ]
    relevant.sort(key=lambda game: game.get("start_local") or "", reverse=True)
    return _team_game_rows(team_slug, relevant[:limit])


def _upcoming_team_games(team_slug: str, games: Iterable[Mapping[str, object]], limit: int = 3) -> List[Dict[str, object]]:
    relevant = [
        game for game in games
        if str(game.get("status") or "") != "final"
        and (str(game.get("home_slug") or "") == team_slug or str(game.get("away_slug") or "") == team_slug)
    ]
    relevant.sort(key=lambda game: game.get("start_local") or "")
    return _team_game_rows(team_slug, relevant[:limit])


def _team_game_rows(team_slug: str, games: Iterable[Mapping[str, object]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for game in games:
        home_slug = str(game.get("home_slug") or "")
        away_slug = str(game.get("away_slug") or "")
        team_is_home = home_slug == team_slug
        team_score = game.get("home_score" if team_is_home else "away_score")
        opp_score = game.get("away_score" if team_is_home else "home_score")
        outcome = "scheduled"
        if str(game.get("status") or "") == "final":
            if (team_score or 0) > (opp_score or 0):
                outcome = "win"
            elif (team_score or 0) < (opp_score or 0):
                outcome = "loss"
            else:
                outcome = "tie"
        rows.append(
            {
                "canonical_game_id": game.get("canonical_game_id"),
                "local_date": game.get("local_date"),
                "local_time": game.get("local_time"),
                "opponent_slug": away_slug if team_is_home else home_slug,
                "opponent_name": game.get("away_team") if team_is_home else game.get("home_team"),
                "team_score": team_score,
                "opponent_score": opp_score,
                "outcome": outcome,
                "season_phase": game.get("season_phase"),
                "playoff_series_id": game.get("playoff_series_id"),
            }
        )
    return rows


def _team_leaders(players: Iterable[Mapping[str, object]], team_slug: str, metric: str, limit: int = 5) -> List[Dict[str, object]]:
    filtered = [player for player in players if str(player.get("team_slug") or "") == team_slug]
    filtered.sort(
        key=lambda player: (
            _safe_int(player.get(metric)),
            _player_points(player),
            _safe_int(player.get("goals")),
            str(player.get("name") or ""),
        ),
        reverse=True,
    )
    rows: List[Dict[str, object]] = []
    for player in filtered[:limit]:
        rows.append(
            {
                "player_id": player.get("player_id"),
                "name": player.get("name"),
                "display_name": _display_name(str(player.get("name") or "Unknown")),
                "games_played": _safe_int(player.get("games_played")),
                "goals": _safe_int(player.get("goals")),
                "assists": _safe_int(player.get("assists")),
                "points": _player_points(player),
            }
        )
    return rows


def _team_dossiers(
    games: List[Dict[str, object]],
    players: List[Dict[str, object]],
    standings: List[Dict[str, object]],
    team_meta: Mapping[str, Dict[str, object]],
    series_data: Mapping[str, object],
    head_to_head: List[Dict[str, object]],
) -> Dict[str, Dict[str, object]]:
    standings_by_slug = {team["team_slug"]: team for team in standings}
    active_series_by_team: Dict[str, Dict[str, object]] = {}
    for round_entry in series_data.get("rounds", []):
        if not isinstance(round_entry, dict):
            continue
        for series in round_entry.get("series", []):
            if not isinstance(series, dict):
                continue
            for side in ("higher_seed", "lower_seed"):
                team_slug = str(series.get(side, {}).get("team_slug") or "")
                if team_slug:
                    active_series_by_team[team_slug] = series

    dossiers: Dict[str, Dict[str, object]] = {}
    for slug, meta in team_meta.items():
        standing = standings_by_slug.get(slug)
        series = active_series_by_team.get(slug)
        playoff_context = None
        if isinstance(series, dict):
            playoff_context = {
                "series_id": series.get("series_id"),
                "label": series.get("label"),
                "state_label": series.get("state_label"),
                "best_of": series.get("best_of"),
                "wins": series.get("wins"),
                "next_game": series.get("next_game"),
                "known_game_dates": series.get("known_game_dates"),
            }
        dossiers[slug] = {
            "team_slug": slug,
            "team_name": meta.get("name"),
            "logo_path": meta.get("logo_path"),
            "standing": standing,
            "leaders": {
                "points": _team_leaders(players, slug, "points"),
                "goals": _team_leaders(players, slug, "goals"),
                "assists": _team_leaders(players, slug, "assists"),
            },
            "recent_results": _recent_team_results(slug, games),
            "upcoming_games": _upcoming_team_games(slug, games),
            "head_to_head": _team_head_to_head(slug, head_to_head, team_meta),
            "playoff_context": playoff_context,
        }
    return dossiers


def _season_overview(
    games: List[Dict[str, object]],
    standings: List[Dict[str, object]],
    players: List[Dict[str, object]],
    series_data: Mapping[str, object],
    head_to_head: List[Dict[str, object]],
    team_meta: Mapping[str, Dict[str, object]],
) -> Dict[str, object]:
    regular_games = [game for game in games if game.get("season_phase") == "regular_season" and game.get("status") == "final"]
    playoff_games = [game for game in games if game.get("season_phase") == "playoffs"]
    completed_playoff_games = [game for game in playoff_games if game.get("status") == "final"]
    scheduled_playoff_games = [game for game in playoff_games if game.get("status") != "final"]
    standings_by_slug = {team["team_slug"]: team for team in standings}
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "season_id": "2025-2026",
        "local_today": halifax_now().strftime("%Y-%m-%d"),
        "counts": {
            "completed_regular_season_games": len(regular_games),
            "completed_playoff_games": len(completed_playoff_games),
            "scheduled_playoff_games": len(scheduled_playoff_games),
            "teams": len(team_meta),
        },
        "standings": standings,
        "leaders": _leaderboards(players),
        "head_to_head_matrix": head_to_head,
        "playoff_rounds": series_data.get("rounds", []),
        "playoff_teams": [
            {
                "team_slug": team_slug,
                "team_name": team_meta.get(team_slug, {}).get("name"),
                "rank": standings_by_slug.get(team_slug, {}).get("rank"),
            }
            for team_slug in sorted(
                {
                    str(series.get("higher_seed", {}).get("team_slug") or "")
                    for round_entry in series_data.get("rounds", [])
                    for series in round_entry.get("series", [])
                    if isinstance(round_entry, dict) and isinstance(series, dict)
                }
                | {
                    str(series.get("lower_seed", {}).get("team_slug") or "")
                    for round_entry in series_data.get("rounds", [])
                    for series in round_entry.get("series", [])
                    if isinstance(round_entry, dict) and isinstance(series, dict)
                }
            )
            if team_slug
        ],
    }


def _render_markdown(
    overview: Mapping[str, object],
    series_data: Mapping[str, object],
    dossiers: Mapping[str, Mapping[str, object]],
) -> str:
    lines: List[str] = []
    lines.append("# AAHL 2025-2026 Season Analysis")
    lines.append("")
    lines.append(f"Generated: {overview.get('generated_at')}")
    lines.append(f"Local date context: {overview.get('local_today')} (Halifax)")
    lines.append("")
    counts = overview.get("counts", {})
    lines.append("## League Snapshot")
    lines.append(f"- Completed regular-season games: {counts.get('completed_regular_season_games')}")
    lines.append(f"- Completed playoff games: {counts.get('completed_playoff_games')}")
    lines.append(f"- Scheduled playoff games: {counts.get('scheduled_playoff_games')}")
    lines.append(f"- Teams: {counts.get('teams')}")
    lines.append("")
    lines.append("## Standings")
    for team in overview.get("standings", []):
        if not isinstance(team, dict):
            continue
        lines.append(
            f"- {team.get('rank')}. {team.get('team_name')} | {team.get('record')} | {team.get('points')} pts | GF {team.get('goals_for')} / GA {team.get('goals_against')} | {team.get('streak')}"
        )
    lines.append("")
    lines.append("## Semifinals")
    for round_entry in series_data.get("rounds", []):
        if not isinstance(round_entry, dict):
            continue
        for series in round_entry.get("series", []):
            if not isinstance(series, dict):
                continue
            lines.append(f"### {series.get('label')}")
            lines.append(f"- State: {series.get('state_label')}")
            lines.append(f"- Best of: {series.get('best_of')}")
            next_game = series.get("next_game") or {}
            if next_game:
                lines.append(
                    f"- Next game: {next_game.get('local_date')} {next_game.get('local_time')} | {next_game.get('away_team')} at {next_game.get('home_team')}"
                )
            known_dates = series.get("known_game_dates") or []
            if known_dates:
                lines.append(f"- Known local dates: {', '.join(known_dates)}")
            h2h = series.get("regular_season_head_to_head") or {}
            teams = h2h.get("teams", {}) if isinstance(h2h, dict) else {}
            if teams:
                higher = series.get("higher_seed", {}).get("team_slug")
                lower = series.get("lower_seed", {}).get("team_slug")
                higher_record = teams.get(higher, {})
                lower_record = teams.get(lower, {})
                lines.append(
                    f"- Regular season head-to-head: {series.get('higher_seed', {}).get('team_name')} {higher_record.get('wins', 0)}-{higher_record.get('losses', 0)}-{higher_record.get('ties', 0)} vs {series.get('lower_seed', {}).get('team_name')}"
                )
            lines.append("")
    lines.append("## Team Capsules")
    for slug in sorted(dossiers):
        dossier = dossiers[slug]
        standing = dossier.get("standing") or {}
        lines.append(f"### {dossier.get('team_name')}")
        if standing:
            lines.append(
                f"- Standing: {standing.get('rank')} | {standing.get('record')} | {standing.get('points')} pts | last 10 {standing.get('last_10')} | {standing.get('streak')}"
            )
        points_leader = (dossier.get("leaders") or {}).get("points", [])
        if points_leader:
            leader = points_leader[0]
            lines.append(
                f"- Points leader: {leader.get('display_name')} ({leader.get('points')} pts in {leader.get('games_played')} GP)"
            )
        playoff_context = dossier.get("playoff_context")
        if isinstance(playoff_context, dict):
            lines.append(f"- Playoff context: {playoff_context.get('state_label')}")
        recent_results = dossier.get("recent_results") or []
        if recent_results:
            latest = recent_results[0]
            lines.append(
                f"- Most recent result: {latest.get('local_date')} vs {latest.get('opponent_name')} ({latest.get('outcome')})"
            )
        upcoming_games = dossier.get("upcoming_games") or []
        if upcoming_games:
            next_up = upcoming_games[0]
            lines.append(
                f"- Next scheduled: {next_up.get('local_date')} {next_up.get('local_time')} vs {next_up.get('opponent_name')}"
            )
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main() -> None:
    players = _load_players()
    standings = _load_standings()
    team_meta = _load_team_meta()
    playoffs = _load_playoff_config()
    games = _load_canonical_games()
    head_to_head = _head_to_head_matrix(games)
    series_data = _build_series_data(games, playoffs, standings, team_meta, head_to_head)
    overview = _season_overview(games, standings, players, series_data, head_to_head, team_meta)
    dossiers = _team_dossiers(games, players, standings, team_meta, series_data, head_to_head)
    markdown = _render_markdown(overview, series_data, dossiers)

    _write_json(OUTPUT_DIR / "games.json", games)
    _write_json(OUTPUT_DIR / "series.json", series_data)
    _write_json(OUTPUT_DIR / "season_overview.json", overview)
    for slug, dossier in dossiers.items():
        _write_json(OUTPUT_DIR / "teams" / f"{slug}.json", dossier)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / "season_analysis.md").write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
