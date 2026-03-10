#!/usr/bin/env python3
"""Generate prompt-ready story input files for manual LLM use."""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
V2_DIR = DATA_DIR / "v2"
OUTPUT_DIR = V2_DIR / "story_inputs"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aahlscraper.utils import slugify


MONTH_NAMES = {
    "2025-10": "October 2025",
    "2025-11": "November 2025",
    "2025-12": "December 2025",
    "2026-01": "January 2026",
    "2026-02": "February 2026",
    "2026-03": "March 2026",
}

PROMPT_TEMPLATES = {
    "league-season-review.md": """# League Season Review Template

Use this prompt with `league/season.md`.

## Prompt
Write a newspaper-style AAHL season review using only the attached league story pack as factual source material.

Requirements:
- Treat the pack's verified facts as hard constraints.
- Use the derived angles only as framing options, not mandatory claims.
- Explain how the table settled month by month.
- Distinguish the two semifinal series clearly: favorite-vs-underdog and rivalry/coin-flip if the facts support that framing.
- Mention the scoring race and at least three players by name.
- Do not invent quotes, injuries, transactions, or off-ice details.
- Keep dates in local season context exactly as written in the pack.

Output:
1. Headline
2. Deck
3. Main story in 700-1000 words
4. Five-bullet notebook of the season's biggest turning points

Pack to use:
[PASTE LEAGUE STORY PACK HERE]
""",
    "team-season-recap.md": """# Team Season Recap Template

Use this prompt with one file from `teams/`.

## Prompt
Write a newspaper-style season recap for the attached team using only the supplied team story pack.

Requirements:
- Treat verified facts as hard constraints.
- Build the story around the month-by-month team context notes and the first-half vs second-half split.
- Explain when the team was rising, stable, or fading.
- Use key games and opponent splits to support the story.
- Mention the leading players without inventing details about lines, systems, or injuries.
- If the pack includes playoff context, end by pivoting naturally into that semifinal setup.
- Do not invent quotes or details outside the pack.

Output:
1. Headline
2. Deck
3. Main story in 600-900 words
4. Short sidebar titled `By The Numbers`
5. One paragraph titled `Why This Team Was What It Was`

Pack to use:
[PASTE TEAM STORY PACK HERE]
""",
    "player-season-profile.md": """# Player Season Profile Template

Use this prompt with one file from `players/`.

## Prompt
Write a newspaper-style player feature using only the attached player story pack.

Requirements:
- Treat verified facts as hard constraints.
- Use the `Per-Game Log Coverage` section honestly. If coverage is partial, do not describe the game-by-game log as full-season chronology.
- Build the story around the player's role, season arc, production style, and biggest moments.
- Use month-end progression for the full-season accumulation story and use the logged game sample only for examples and texture.
- Mention team context where the pack supports it.
- Do not invent goalie metrics, injuries, quotes, or biographical detail not present in the pack.

Output:
1. Headline
2. Deck
3. Main profile in 700-1000 words
4. `Season Snapshot` bullet list
5. `Best Stretch` paragraph

Pack to use:
[PASTE PLAYER STORY PACK HERE]
""",
    "series-preview.md": """# Series Preview Template

Use this prompt with one file from `series/`.

## Prompt
Write a newspaper-style playoff preview for the attached semifinal series using only the supplied series story pack.

Requirements:
- Treat verified facts as hard constraints.
- Use the regular-season meetings as the backbone of the rivalry/setup section.
- Use recent results and key scorers to explain present form and pressure points.
- Respect the best-of-3 structure and current state exactly as written.
- Do not invent playoff results, quotes, lineup changes, or injuries.
- Keep the tone sharp and local, like a preview that runs on game day.

Output:
1. Headline
2. Deck
3. Main preview in 600-850 words
4. `What Decides The Series` section with three bullets
5. `Players To Watch` section with one short paragraph per side

Pack to use:
[PASTE SERIES STORY PACK HERE]
""",
    "team-season-capsule.md": """# Team Season Capsule Template

Use this prompt with one file from `teams/`.

## Prompt
Write a tight newspaper-style season capsule for the attached team using only the supplied team story pack.

Requirements:
- 180-260 words.
- One strong opening sentence, one middle paragraph on the season arc, and one closing paragraph on playoff context or what the season meant.
- Use the month-by-month team context notes to explain the rise, plateau, or fade.
- Do not invent quotes, injuries, or off-ice details.

Pack to use:
[PASTE TEAM STORY PACK HERE]
""",
    "player-blurb.md": """# Player Blurb Template

Use this prompt with one file from `players/`.

## Prompt
Write a sharp local-paper player blurb using only the attached player story pack.

Requirements:
- 120-180 words.
- Focus on role, season shape, and why the player mattered.
- If per-game log coverage is partial, avoid pretending the logged games are a full season chronology.
- End with one sentence connecting the player to his team heading into the playoffs or offseason.

Pack to use:
[PASTE PLAYER STORY PACK HERE]
""",
    "game-night-preview.md": """# Game-Night Preview Template

Use this prompt with one `series/` file and optionally one or two `teams/` files.

## Prompt
Write a concise game-night preview for tonight's playoff matchup using only the attached packs.

Requirements:
- 250-350 words.
- Lead with the stakes of the best-of-3 series.
- Use regular-season meetings and recent form to frame the matchup.
- Mention two or three players to watch.
- End with one sentence on what would swing the night.
- Do not invent line combinations, injuries, or quotes.

Packs to use:
[PASTE SERIES STORY PACK HERE]
[OPTIONAL: PASTE TEAM STORY PACK(S) HERE]
""",
    "player-briefs-package.md": """# Player Briefs Package Template

Use this prompt with multiple files from `players/`.

## Prompt
Write a package of short player briefs using only the attached player story packs.

Requirements:
- One 90-140 word brief per player.
- Keep each brief distinct in tone and emphasis.
- Use the team-context crossover material to explain each player's place in his club's season.
- Respect any per-game log coverage warning.
- Do not invent quotes, injuries, or history that is not present in the packs.

Packs to use:
[PASTE PLAYER STORY PACKS HERE]
""",
}


def load_json(path: Path) -> object | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def safe_int(value: object, default: int = 0) -> int:
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


def display_name(name: str) -> str:
    if "," in name:
        last, first = [segment.strip() for segment in name.split(",", 1)]
        return f"{first} {last}".strip()
    return name.strip()


def month_key(date_text: Optional[str]) -> Optional[str]:
    if not date_text:
        return None
    return str(date_text)[:7]


def month_label(month: str) -> str:
    return MONTH_NAMES.get(month, month)


def result_code(team_score: Optional[int], opp_score: Optional[int]) -> str:
    if team_score is None or opp_score is None:
        return "-"
    if team_score > opp_score:
        return "W"
    if team_score < opp_score:
        return "L"
    return "T"


def markdown_table(headers: List[str], rows: List[List[object]]) -> str:
    if not rows:
        return "_No data available._"
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(lines)


def render_frontmatter(meta: Mapping[str, object]) -> str:
    lines = ["---"]
    for key, value in meta.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(json.dumps(item) for item in value)}]")
        else:
            lines.append(f"{key}: {json.dumps(value)}")
    lines.append("---")
    return "\n".join(lines)


def pct_text(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "0.000"
    return f"{numerator / denominator:.3f}"


def build_team_meta() -> Dict[str, Dict[str, object]]:
    payload = load_json(DATA_DIR / "teams.json")
    teams = payload.get("teams", []) if isinstance(payload, dict) else []
    lookup: Dict[str, Dict[str, object]] = {}
    for team in teams:
        if isinstance(team, dict) and team.get("slug"):
            lookup[str(team["slug"])] = team
    return lookup


def build_standings() -> List[Dict[str, object]]:
    payload = load_json(V2_DIR / "season_overview.json")
    standings = payload.get("standings", []) if isinstance(payload, dict) else []
    return [row for row in standings if isinstance(row, dict)]


def build_games() -> List[Dict[str, object]]:
    payload = load_json(V2_DIR / "games.json")
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def build_series() -> List[Dict[str, object]]:
    payload = load_json(V2_DIR / "series.json")
    rounds = payload.get("rounds", []) if isinstance(payload, dict) else []
    series_list: List[Dict[str, object]] = []
    for round_entry in rounds:
        if not isinstance(round_entry, dict):
            continue
        for entry in round_entry.get("series", []):
            if isinstance(entry, dict):
                series_list.append(entry)
    return series_list


def build_player_registry() -> List[Dict[str, object]]:
    payload = load_json(DATA_DIR / "player_registry.json")
    players = payload.get("players", []) if isinstance(payload, dict) else payload
    return [row for row in players if isinstance(row, dict)] if isinstance(players, list) else []


def build_results() -> List[Dict[str, object]]:
    payload = load_json(DATA_DIR / "results.json")
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def latest_snapshot_paths_by_month(directory: Path) -> Dict[str, Path]:
    latest: Dict[str, Path] = {}
    for path in sorted(directory.glob("*.json")):
        stamp = path.stem.rsplit("-", 1)[-1]
        month = f"{stamp[0:4]}-{stamp[4:6]}"
        latest[month] = path
    return latest


def build_standing_checkpoints() -> Dict[str, List[Dict[str, object]]]:
    checkpoints: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for month, path in sorted(latest_snapshot_paths_by_month(DATA_DIR / "history" / "standings").items()):
        payload = load_json(path)
        if not isinstance(payload, list):
            continue
        for rank, row in enumerate(payload, start=1):
            if not isinstance(row, dict):
                continue
            team_name = str(row.get("team") or row.get("Team") or "Unknown")
            slug = slugify(team_name)
            checkpoints[slug].append(
                {
                    "month": month,
                    "month_label": month_label(month),
                    "rank": rank,
                    "points": safe_int(row.get("pts") or row.get("points")),
                    "record": str(row.get("record") or ""),
                    "streak": str(row.get("streak") or ""),
                }
            )
    return checkpoints


def build_player_checkpoints() -> Dict[str, List[Dict[str, object]]]:
    checkpoints: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for month, path in sorted(latest_snapshot_paths_by_month(DATA_DIR / "history" / "player_registry").items()):
        payload = load_json(path)
        players = payload.get("players", []) if isinstance(payload, dict) else []
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, dict):
                continue
            player_id = str(player.get("player_id") or "").strip()
            if not player_id:
                continue
            checkpoints[player_id].append(
                {
                    "month": month,
                    "month_label": month_label(month),
                    "games_played": safe_int(player.get("games_played")),
                    "goals": safe_int(player.get("goals")),
                    "assists": safe_int(player.get("assists")),
                    "points": safe_int(player.get("points")),
                }
            )
    return checkpoints


def build_player_logs(results: Iterable[Mapping[str, object]], playoff_teams: set[str]) -> Dict[str, List[Dict[str, object]]]:
    logs: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for game in results:
        game_date = str(game.get("date") or "")
        local_date = None
        if game.get("start_local"):
            local_date = str(game.get("start_local"))[:10]
        elif game_date:
            parts = game_date.split("/")
            if len(parts) == 3:
                local_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
        month = month_key(local_date)
        home = str(game.get("home") or "")
        away = str(game.get("away") or "")
        home_slug = str((game.get("home_line") or {}).get("slug") or slugify(home))
        away_slug = str((game.get("away_line") or {}).get("slug") or slugify(away))
        home_score = safe_int(game.get("home_score"))
        away_score = safe_int(game.get("away_score"))
        player_stats = game.get("player_stats") or {}
        if not isinstance(player_stats, dict):
            continue

        for side in ("home", "away"):
            roster = player_stats.get(side, [])
            if not isinstance(roster, list):
                continue
            team_name = home if side == "home" else away
            team_slug = home_slug if side == "home" else away_slug
            opponent_name = away if side == "home" else home
            opponent_slug = away_slug if side == "home" else home_slug
            team_score = home_score if side == "home" else away_score
            opponent_score = away_score if side == "home" else home_score
            for player in roster:
                if not isinstance(player, dict):
                    continue
                player_id = str(player.get("player_id") or "").strip()
                if not player_id:
                    continue
                goals = safe_int(player.get("goals"))
                assists = safe_int(player.get("assists"))
                points = safe_int(player.get("points"), goals + assists)
                logs[player_id].append(
                    {
                        "game_id": str(game.get("game_id") or ""),
                        "local_date": local_date,
                        "month": month,
                        "team_name": team_name,
                        "team_slug": team_slug,
                        "opponent_name": opponent_name,
                        "opponent_slug": opponent_slug,
                        "team_score": team_score,
                        "opponent_score": opponent_score,
                        "result": result_code(team_score, opponent_score),
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "penalty_minutes": safe_int(player.get("penalty_minutes")),
                        "is_playoff_opponent": opponent_slug in playoff_teams,
                    }
                )
    for entries in logs.values():
        entries.sort(key=lambda row: (row.get("local_date") or "", row.get("game_id") or ""))
    return logs


def summarize_team_results(entries: List[Mapping[str, object]]) -> Dict[str, object]:
    wins = sum(1 for row in entries if row.get("result") == "W")
    losses = sum(1 for row in entries if row.get("result") == "L")
    ties = sum(1 for row in entries if row.get("result") == "T")
    gf = sum(safe_int(row.get("team_score")) for row in entries)
    ga = sum(safe_int(row.get("opponent_score")) for row in entries)
    gp = len(entries)
    standings_points = wins * 2 + ties
    return {
        "gp": gp,
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "gf": gf,
        "ga": ga,
        "record": f"{wins}-{losses}-{ties}",
        "points_pct": pct_text(standings_points, gp * 2),
        "goal_diff": gf - ga,
    }


def summarize_player_results(entries: List[Mapping[str, object]]) -> Dict[str, object]:
    gp = len(entries)
    goals = sum(safe_int(row.get("goals")) for row in entries)
    assists = sum(safe_int(row.get("assists")) for row in entries)
    points = sum(safe_int(row.get("points")) for row in entries)
    pim = sum(safe_int(row.get("penalty_minutes")) for row in entries)
    return {
        "gp": gp,
        "goals": goals,
        "assists": assists,
        "points": points,
        "penalty_minutes": pim,
        "points_per_game": f"{(points / gp):.2f}" if gp else "0.00",
    }


def build_team_logs(games: Iterable[Mapping[str, object]], playoff_teams: set[str]) -> Dict[str, Dict[str, List[Dict[str, object]]]]:
    team_logs: Dict[str, Dict[str, List[Dict[str, object]]]] = defaultdict(lambda: {"final": [], "scheduled": []})
    for game in games:
        home_slug = str(game.get("home_slug") or "")
        away_slug = str(game.get("away_slug") or "")
        home_score = game.get("home_score") if isinstance(game.get("home_score"), int) else None
        away_score = game.get("away_score") if isinstance(game.get("away_score"), int) else None
        for side, team_slug, opponent_slug in (("home", home_slug, away_slug), ("away", away_slug, home_slug)):
            if not team_slug:
                continue
            team_name = str(game.get("home_team") if side == "home" else game.get("away_team") or "")
            opponent_name = str(game.get("away_team") if side == "home" else game.get("home_team") or "")
            team_score = home_score if side == "home" else away_score
            opp_score = away_score if side == "home" else home_score
            row = {
                "canonical_game_id": game.get("canonical_game_id"),
                "local_date": game.get("local_date"),
                "local_time": game.get("local_time"),
                "month": month_key(game.get("local_date")),
                "season_phase": game.get("season_phase"),
                "team_name": team_name,
                "team_slug": team_slug,
                "opponent_name": opponent_name,
                "opponent_slug": opponent_slug,
                "team_score": team_score,
                "opponent_score": opp_score,
                "result": result_code(team_score, opp_score),
                "is_playoff_opponent": opponent_slug in playoff_teams,
                "box_score_url": game.get("box_score_url"),
            }
            bucket = "final" if str(game.get("status") or "") == "final" else "scheduled"
            team_logs[team_slug][bucket].append(row)
    for team_slug in team_logs:
        team_logs[team_slug]["final"].sort(key=lambda row: (row.get("local_date") or "", row.get("canonical_game_id") or ""))
        team_logs[team_slug]["scheduled"].sort(key=lambda row: (row.get("local_date") or "", row.get("canonical_game_id") or ""))
    return team_logs


def rolling_team_windows(entries: List[Dict[str, object]], window: int = 5) -> Dict[str, Dict[str, object]]:
    if not entries:
        return {}
    window = min(window, len(entries))
    ranked: List[Tuple[Tuple[int, int, int], Dict[str, object]]] = []
    for index in range(len(entries) - window + 1):
        chunk = entries[index:index + window]
        summary = summarize_team_results(chunk)
        ranked.append(
            (
                (
                    summary["wins"] * 2 + summary["ties"],
                    summary["goal_diff"],
                    summary["gf"],
                ),
                {
                    "start_date": chunk[0].get("local_date"),
                    "end_date": chunk[-1].get("local_date"),
                    "window": window,
                    **summary,
                },
            )
        )
    best = max(ranked, key=lambda item: item[0])[1]
    worst = min(ranked, key=lambda item: item[0])[1]
    return {"best": best, "worst": worst}


def rolling_player_windows(entries: List[Dict[str, object]], window: int = 5) -> Dict[str, Dict[str, object]]:
    if not entries:
        return {}
    window = min(window, len(entries))
    ranked: List[Tuple[Tuple[int, int, int], Dict[str, object]]] = []
    for index in range(len(entries) - window + 1):
        chunk = entries[index:index + window]
        summary = summarize_player_results(chunk)
        ranked.append(
            (
                (
                    summary["points"],
                    summary["goals"],
                    -summary["penalty_minutes"],
                ),
                {
                    "start_date": chunk[0].get("local_date"),
                    "end_date": chunk[-1].get("local_date"),
                    "window": window,
                    **summary,
                },
            )
        )
    best = max(ranked, key=lambda item: item[0])[1]
    worst = min(ranked, key=lambda item: item[0])[1]
    return {"best": best, "worst": worst}


def streak_lengths(entries: List[Mapping[str, object]], predicate) -> int:
    best = 0
    current = 0
    for row in entries:
        if predicate(row):
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def monthly_team_timeline(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    by_month: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in entries:
        month = str(row.get("month") or "")
        if month:
            by_month[month].append(row)
    rows: List[Dict[str, object]] = []
    for month in sorted(by_month):
        month_entries = by_month[month]
        summary = summarize_team_results(month_entries)
        notable = max(
            month_entries,
            key=lambda row: (
                abs(safe_int(row.get("team_score")) - safe_int(row.get("opponent_score"))),
                safe_int(row.get("team_score")) + safe_int(row.get("opponent_score")),
            ),
        )
        rows.append(
            {
                "month": month,
                "month_label": month_label(month),
                "record": summary["record"],
                "gf": summary["gf"],
                "ga": summary["ga"],
                "notable_game": f"{notable.get('local_date')} vs {notable.get('opponent_name')} ({notable.get('team_score')}-{notable.get('opponent_score')}, {notable.get('result')})",
            }
        )
    return rows


def monthly_team_context_notes(team_name: str, monthly: List[Dict[str, object]], monthly_checkpoints: List[Dict[str, object]], entries: List[Dict[str, object]], team_name_map: Mapping[str, str]) -> List[Dict[str, object]]:
    if not monthly:
        return []
    season_summary = summarize_team_results(entries)
    season_gf_per_game = season_summary["gf"] / max(season_summary["gp"], 1)
    season_ga_per_game = season_summary["ga"] / max(season_summary["gp"], 1)
    checkpoint_map = {str(row.get("month") or ""): row for row in monthly_checkpoints}
    notes_rows: List[Dict[str, object]] = []
    prev_points_pct: Optional[float] = None
    prev_checkpoint_rank: Optional[int] = None
    by_month_entries: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in entries:
        month = str(row.get("month") or "")
        if month:
            by_month_entries[month].append(row)

    for row in monthly:
        month = str(row.get("month") or "")
        gp = safe_int(row.get("gp"))
        wins = safe_int(row.get("wins"))
        losses = safe_int(row.get("losses"))
        ties = safe_int(row.get("ties"))
        gf = safe_int(row.get("gf"))
        ga = safe_int(row.get("ga"))
        points_pct = (wins * 2 + ties) / max(gp * 2, 1)
        month_entries = by_month_entries.get(month, [])
        playoff_games = sum(1 for game in month_entries if game.get("is_playoff_opponent"))
        opponents = sorted({team_name_map.get(str(game.get("opponent_slug") or ""), str(game.get("opponent_name") or "Unknown")) for game in month_entries})
        checkpoint = checkpoint_map.get(month)
        notes: List[str] = []

        goal_diff = gf - ga
        if wins == gp and gp > 0:
            notes.append(f"Went unbeaten and perfect at {wins}-{losses}-{ties} with a {goal_diff:+d} goal differential.")
        elif losses == 0 and gp > 0:
            notes.append(f"Went unbeaten at {wins}-{losses}-{ties} with a {goal_diff:+d} goal differential.")
        else:
            notes.append(f"Played to a {wins}-{losses}-{ties} month and outscored opponents {gf}-{ga}.")

        gf_per_game = gf / max(gp, 1)
        ga_per_game = ga / max(gp, 1)
        if gf_per_game - season_gf_per_game >= 0.75:
            notes.append("Scored well above its season pace, which makes this month an offensive spike.")
        elif season_gf_per_game - gf_per_game >= 0.75:
            notes.append("Scored below its usual rate, which helps explain any stall or fade in the standings.")

        if season_ga_per_game - ga_per_game >= 0.75:
            notes.append("Defended better than its season norm, which gave the month a steadier feel.")
        elif ga_per_game - season_ga_per_game >= 0.75:
            notes.append("Allowed goals at a higher rate than normal, which put strain on the month.")

        if prev_points_pct is not None:
            if points_pct - prev_points_pct >= 0.2:
                notes.append("This was a clear improvement from the previous month.")
            elif prev_points_pct - points_pct >= 0.2:
                notes.append("This was a clear drop from the previous month.")
        prev_points_pct = points_pct

        if playoff_games >= max(2, gp - 1):
            notes.append(f"The schedule was playoff-heavy, with {playoff_games} of {gp} games against the postseason field.")

        if checkpoint:
            rank = safe_int(checkpoint.get("rank"), 99)
            points = safe_int(checkpoint.get("points"))
            rank_note = f"Closed the month at No. {rank} with {points} points."
            if prev_checkpoint_rank is not None:
                if rank < prev_checkpoint_rank:
                    rank_note += " That was an upward move in the table."
                elif rank > prev_checkpoint_rank:
                    rank_note += " That was a drop in the table."
                else:
                    rank_note += " That held the same place in the table."
            notes.append(rank_note)
            prev_checkpoint_rank = rank

        if opponents:
            notes.append(f"Main opponents that month: {', '.join(opponents)}.")

        notes_rows.append(
            {
                "month": month,
                "month_label": row.get("month_label"),
                "notes": notes[:5],
            }
        )
    return notes_rows


def player_team_context_notes(team_name: str, team_monthly: List[Dict[str, object]], team_month_notes: List[Dict[str, object]], player_monthly: List[Dict[str, object]], team_checkpoints: List[Dict[str, object]]) -> List[Dict[str, object]]:
    if not team_monthly:
        return []
    player_month_map = {str(row.get("month") or ""): row for row in player_monthly}
    team_note_map = {str(row.get("month") or ""): row for row in team_month_notes}
    team_checkpoint_map = {str(row.get("month") or ""): row for row in team_checkpoints}
    rows: List[Dict[str, object]] = []
    for team_row in team_monthly:
        month = str(team_row.get("month") or "")
        player_row = player_month_map.get(month, {})
        note_row = team_note_map.get(month, {})
        checkpoint = team_checkpoint_map.get(month, {})
        notes = [
            f"{team_name} went {team_row.get('wins')}-{team_row.get('losses')}-{team_row.get('ties')} and scored {team_row.get('gf')} while allowing {team_row.get('ga')}.",
        ]
        if checkpoint:
            notes.append(f"Month-end standing snapshot: No. {checkpoint.get('rank')} with {checkpoint.get('points')} points.")
        if player_row:
            notes.append(f"Player logged-sample line that month: {player_row.get('gp')} GP, {player_row.get('goals')} G, {player_row.get('assists')} A, {player_row.get('points')} PTS.")
        top_context = (note_row.get("notes") or [])[:2]
        notes.extend(str(note) for note in top_context if note)
        rows.append(
            {
                "month": month,
                "month_label": team_row.get("month_label"),
                "notes": notes[:5],
            }
        )
    return rows


def player_team_role_profile(player: Mapping[str, object], team_standing: Mapping[str, object], team_players: List[Dict[str, object]]) -> Dict[str, object]:
    team_points = sorted(team_players, key=lambda row: (safe_int(row.get("points")), safe_int(row.get("goals")), safe_int(row.get("assists"))), reverse=True)
    team_goals_for = safe_int(team_standing.get("goals_for"))
    player_id = str(player.get("player_id") or "")
    player_goals = safe_int(player.get("goals"))
    player_points = safe_int(player.get("points"))
    team_points_rank = next((index for index, row in enumerate(team_points, start=1) if str(row.get("player_id") or "") == player_id), None)
    leader = team_points[0] if team_points else {}
    next_teammate = None
    if team_points_rank and 1 <= team_points_rank < len(team_points):
        next_teammate = team_points[team_points_rank]
    return {
        "team_rank": safe_int(team_standing.get("rank"), 99),
        "team_record": str(team_standing.get("record") or ""),
        "team_points_rank": team_points_rank,
        "team_points_leader": display_name(str(leader.get("name") or "Unknown")) if leader else "Unknown",
        "gap_to_team_leader": safe_int(leader.get("points")) - player_points if leader else 0,
        "lead_over_next_teammate": player_points - safe_int(next_teammate.get("points")) if next_teammate else 0,
        "goal_share_pct": f"{(player_goals / team_goals_for) * 100:.1f}%" if team_goals_for else "0.0%",
    }


def monthly_player_timeline(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    by_month: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in entries:
        month = str(row.get("month") or "")
        if month:
            by_month[month].append(row)
    rows: List[Dict[str, object]] = []
    for month in sorted(by_month):
        month_entries = by_month[month]
        summary = summarize_player_results(month_entries)
        top_game = max(
            month_entries,
            key=lambda row: (
                safe_int(row.get("points")),
                safe_int(row.get("goals")),
                safe_int(row.get("assists")),
            ),
        )
        rows.append(
            {
                "month": month,
                "month_label": month_label(month),
                **summary,
                "top_game": f"{top_game.get('local_date')} vs {top_game.get('opponent_name')} ({top_game.get('goals')}-{top_game.get('assists')}-{top_game.get('points')})",
            }
        )
    return rows


def opponent_team_splits(entries: List[Dict[str, object]], team_name_map: Mapping[str, str]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in entries:
        grouped[str(row.get("opponent_slug") or "")].append(row)
    output: List[Dict[str, object]] = []
    for opponent_slug, rows in grouped.items():
        summary = summarize_team_results(rows)
        output.append(
            {
                "opponent_slug": opponent_slug,
                "opponent_name": team_name_map.get(opponent_slug, opponent_slug),
                **summary,
            }
        )
    output.sort(key=lambda row: (safe_int(row.get("wins")), safe_int(row.get("goal_diff"))), reverse=True)
    return output


def opponent_player_splits(entries: List[Dict[str, object]], team_name_map: Mapping[str, str]) -> List[Dict[str, object]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in entries:
        grouped[str(row.get("opponent_slug") or "")].append(row)
    output: List[Dict[str, object]] = []
    for opponent_slug, rows in grouped.items():
        summary = summarize_player_results(rows)
        output.append(
            {
                "opponent_slug": opponent_slug,
                "opponent_name": team_name_map.get(opponent_slug, opponent_slug),
                **summary,
            }
        )
    output.sort(key=lambda row: (safe_int(row.get("points")), safe_int(row.get("goals"))), reverse=True)
    return output


def outcome_player_splits(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    output: List[Dict[str, object]] = []
    for result in ("W", "L", "T"):
        rows = [row for row in entries if row.get("result") == result]
        summary = summarize_player_results(rows)
        output.append({"result": result, **summary})
    return output


def split_halves(entries: List[Dict[str, object]], summary_builder) -> Dict[str, Dict[str, object]]:
    if not entries:
        return {}
    midpoint = len(entries) // 2
    if midpoint == 0:
        midpoint = 1
    first = entries[:midpoint]
    second = entries[midpoint:]
    return {
        "first_half": summary_builder(first),
        "second_half": summary_builder(second),
    }


def player_log_coverage(player: Mapping[str, object], logs: List[Dict[str, object]]) -> Dict[str, object]:
    logged = summarize_player_results(logs)
    season_gp = safe_int(player.get("games_played"))
    season_goals = safe_int(player.get("goals"))
    season_assists = safe_int(player.get("assists"))
    season_points = safe_int(player.get("points"))
    return {
        "logged_gp": logged["gp"],
        "season_gp": season_gp,
        "game_coverage_pct": pct_text(logged["gp"], season_gp) if season_gp else "0.000",
        "logged_goals": logged["goals"],
        "season_goals": season_goals,
        "goal_coverage_pct": pct_text(logged["goals"], season_goals) if season_goals else "0.000",
        "logged_assists": logged["assists"],
        "season_assists": season_assists,
        "assist_coverage_pct": pct_text(logged["assists"], season_assists) if season_assists else "0.000",
        "logged_points": logged["points"],
        "season_points": season_points,
        "point_coverage_pct": pct_text(logged["points"], season_points) if season_points else "0.000",
        "is_complete": logged["gp"] == season_gp and logged["goals"] == season_goals and logged["assists"] == season_assists and logged["points"] == season_points,
    }


def rank_maps(players: List[Dict[str, object]]) -> Dict[str, Dict[str, int]]:
    ranks: Dict[str, Dict[str, int]] = {"points": {}, "goals": {}, "assists": {}}
    for metric in ("points", "goals", "assists"):
        ordered = sorted(
            players,
            key=lambda row: (safe_int(row.get(metric)), safe_int(row.get("goals")), safe_int(row.get("assists")), str(row.get("name") or "")),
            reverse=True,
        )
        for index, player in enumerate(ordered, start=1):
            player_id = str(player.get("player_id") or "")
            if player_id and player_id not in ranks[metric]:
                ranks[metric][player_id] = index
    return ranks


def team_rank_maps(players: List[Dict[str, object]]) -> Dict[str, Dict[str, Dict[str, int]]]:
    grouped: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for player in players:
        grouped[str(player.get("team_slug") or "")].append(player)
    team_ranks: Dict[str, Dict[str, Dict[str, int]]] = {}
    for team_slug, entries in grouped.items():
        team_ranks[team_slug] = rank_maps(entries)
    return team_ranks


def monthly_team_splits(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    monthly: Dict[str, Dict[str, int]] = defaultdict(lambda: {"gp": 0, "wins": 0, "losses": 0, "ties": 0, "gf": 0, "ga": 0})
    for row in entries:
        month = row.get("month")
        if not month:
            continue
        bucket = monthly[str(month)]
        bucket["gp"] += 1
        if row.get("result") == "W":
            bucket["wins"] += 1
        elif row.get("result") == "L":
            bucket["losses"] += 1
        elif row.get("result") == "T":
            bucket["ties"] += 1
        bucket["gf"] += safe_int(row.get("team_score"))
        bucket["ga"] += safe_int(row.get("opponent_score"))
    rows: List[Dict[str, object]] = []
    for month in sorted(monthly):
        stats = monthly[month]
        rows.append({"month": month, "month_label": month_label(month), **stats})
    return rows


def monthly_player_splits(entries: List[Dict[str, object]]) -> List[Dict[str, object]]:
    monthly: Dict[str, Dict[str, int]] = defaultdict(lambda: {"gp": 0, "goals": 0, "assists": 0, "points": 0, "pim": 0, "multi_point_games": 0})
    for row in entries:
        month = row.get("month")
        if not month:
            continue
        bucket = monthly[str(month)]
        bucket["gp"] += 1
        bucket["goals"] += safe_int(row.get("goals"))
        bucket["assists"] += safe_int(row.get("assists"))
        bucket["points"] += safe_int(row.get("points"))
        bucket["pim"] += safe_int(row.get("penalty_minutes"))
        if safe_int(row.get("points")) >= 2:
            bucket["multi_point_games"] += 1
    rows: List[Dict[str, object]] = []
    for month in sorted(monthly):
        stats = monthly[month]
        rows.append({"month": month, "month_label": month_label(month), **stats})
    return rows


def team_story_angles(team: Mapping[str, object], monthly: List[Mapping[str, object]], leaders: Mapping[str, List[Mapping[str, object]]], series: Optional[Mapping[str, object]]) -> List[str]:
    angles: List[str] = []
    rank = safe_int(team.get("rank"), 99)
    if rank <= 4:
        angles.append(f"Finished the regular season in a playoff position at No. {rank}.")
    else:
        angles.append(f"Finished outside the playoff field at No. {rank}, which frames the season as a miss rather than a chase that got over the line.")

    goals_for = safe_int(team.get("goals_for"))
    goals_against = safe_int(team.get("goals_against"))
    if goals_for - goals_against >= 25:
        angles.append("Owned a strong positive goal differential, which supports a control-the-game narrative rather than a lucky record narrative.")
    elif goals_for - goals_against <= -25:
        angles.append("Carried a deep negative goal differential, which points toward structural defensive problems or thin depth.")

    if monthly:
        best = max(monthly, key=lambda row: (safe_int(row.get("wins")), -safe_int(row.get("losses")), safe_int(row.get("gf"))))
        worst = min(monthly, key=lambda row: (safe_int(row.get("wins")) - safe_int(row.get("losses")), safe_int(row.get("ga")) - safe_int(row.get("gf"))))
        if best.get("month") != worst.get("month"):
            angles.append(f"Best month was {best.get('month_label')} ({best.get('wins')}-{best.get('losses')}-{best.get('ties')}), while {worst.get('month_label')} was the low point.")
        if len(monthly) >= 2:
            first = monthly[0]
            last = monthly[-1]
            first_pct = (safe_int(first.get("wins")) + 0.5 * safe_int(first.get("ties"))) / max(safe_int(first.get("gp")), 1)
            last_pct = (safe_int(last.get("wins")) + 0.5 * safe_int(last.get("ties"))) / max(safe_int(last.get("gp")), 1)
            if last_pct - first_pct >= 0.25:
                angles.append(f"Closed the season much stronger than it opened, which gives the year an upward-trajectory frame going into March.")
            elif first_pct - last_pct >= 0.25:
                angles.append(f"Started stronger than it finished, which opens a fade-down-the-stretch angle.")

    points_leaders = leaders.get("points") or []
    if len(points_leaders) >= 2:
        top = points_leaders[0]
        second = points_leaders[1]
        if safe_int(top.get("points")) - safe_int(second.get("points")) >= 12:
            angles.append(f"The offense appears to run heavily through {display_name(str(top.get('name') or 'Unknown'))}, whose scoring gap over the next teammate is large enough to matter narratively.")

    if series:
        angles.append(f"The immediate playoff frame is {series.get('state_label')}, so the season recap can pivot directly into a semifinal preview.")
    return angles[:6]


def player_story_angles(player: Mapping[str, object], logs: List[Mapping[str, object]], monthly: List[Mapping[str, object]], checkpoints: List[Mapping[str, object]], league_ranks: Mapping[str, Dict[str, int]], team_ranks: Mapping[str, Dict[str, Dict[str, int]]]) -> List[str]:
    angles: List[str] = []
    player_id = str(player.get("player_id") or "")
    team_slug = str(player.get("team_slug") or "")
    gp = safe_int(player.get("games_played"))
    team_games = safe_int(player.get("team_games_played"))
    goals = safe_int(player.get("goals"))
    assists = safe_int(player.get("assists"))
    points = safe_int(player.get("points"))
    positions = [str(pos) for pos in player.get("positions") or []]

    if gp == 0:
        return ["No recorded game log or counting-stat contribution is available in the current dataset, so any profile should stay biographical and roster-focused."]

    if team_games and gp / team_games >= 0.85:
        angles.append("Was available for almost the full season, which supports an ironman or lineup fixture angle.")
    elif team_games and gp / team_games <= 0.45:
        angles.append("Played a limited share of the team schedule, which makes availability and sample size part of the profile.")

    team_metric_ranks = team_ranks.get(team_slug, {})
    team_points_rank = team_metric_ranks.get("points", {}).get(player_id)
    league_points_rank = league_ranks.get("points", {}).get(player_id)
    if team_points_rank == 1:
        angles.append("Finished as his team’s points leader, which makes him a natural centerpiece for any team-season story.")
    if league_points_rank and league_points_rank <= 10:
        angles.append(f"Finished inside the league top 10 in points at No. {league_points_rank}.")

    if goals >= max(assists * 3 // 2, 10) and goals >= 10:
        angles.append("Profiles more like a finisher than a pure setup player; the goal totals drive the story.")
    elif assists >= max(goals * 3 // 2, 10) and assists >= 10:
        angles.append("Profiles as a playmaker; the assist totals tell more of the story than the goal count.")
    elif points >= 20:
        angles.append("Has a balanced scoring line rather than an extreme scorer/playmaker split.")

    multi_point_games = sum(1 for row in logs if safe_int(row.get("points")) >= 2)
    hat_tricks = sum(1 for row in logs if safe_int(row.get("goals")) >= 3)
    if multi_point_games >= 5:
        angles.append(f"Logged {multi_point_games} multi-point games, which gives the season a repeat-impact frame rather than a few isolated spikes.")
    if hat_tricks:
        angles.append(f"Recorded {hat_tricks} hat trick{'s' if hat_tricks != 1 else ''}, which is a ready-made local-paper hook.")

    if monthly:
        best_month = max(monthly, key=lambda row: (safe_int(row.get("points")), safe_int(row.get("goals"))))
        worst_month = min(monthly, key=lambda row: (safe_int(row.get("points")), -safe_int(row.get("gp"))))
        if best_month.get("month") != worst_month.get("month"):
            angles.append(f"Peak month was {best_month.get('month_label')} ({best_month.get('points')} points), which helps structure the season arc.")
        if len(monthly) >= 2:
            first = monthly[0]
            last = monthly[-1]
            if safe_int(last.get("points")) - safe_int(first.get("points")) >= 5:
                angles.append("Production rose late in the season, which supports a late-heater or playoff-form angle.")

    if checkpoints and len(checkpoints) >= 2:
        early = checkpoints[0]
        late = checkpoints[-1]
        if safe_int(late.get("points")) - safe_int(early.get("points")) >= 20:
            angles.append("The month-end checkpoints show a steady accumulation profile rather than one single explosive stretch.")

    if "D" in positions and points >= 15:
        angles.append("Produces enough offense from the blue line to justify a puck-moving defenseman frame.")
    elif "G" in positions and points == 0:
        angles.append("Current dataset does not include goalie-specific performance metrics, so the profile should avoid inventing save or win narratives.")

    return angles[:7]


def series_story_angles(series: Mapping[str, object]) -> List[str]:
    angles: List[str] = []
    higher = series.get("higher_seed", {}) or {}
    lower = series.get("lower_seed", {}) or {}
    higher_name = higher.get("team_name")
    lower_name = lower.get("team_name")
    higher_points = safe_int((higher.get("standing") or {}).get("points"))
    lower_points = safe_int((lower.get("standing") or {}).get("points"))
    if higher_points - lower_points >= 10:
        angles.append(f"On standings points alone, {higher_name} enters as the clear favorite over {lower_name}.")
    elif abs(higher_points - lower_points) <= 3:
        angles.append("The seeding gap is narrow enough that this can be framed as a near coin-flip semifinal rather than a classic favorite-versus-underdog series.")

    h2h = series.get("regular_season_head_to_head") or {}
    teams = h2h.get("teams", {}) if isinstance(h2h, dict) else {}
    higher_slug = higher.get("team_slug")
    lower_slug = lower.get("team_slug")
    higher_record = teams.get(higher_slug, {}) if isinstance(teams, dict) else {}
    lower_record = teams.get(lower_slug, {}) if isinstance(teams, dict) else {}
    if higher_record and lower_record:
        hw = safe_int(higher_record.get("wins"))
        lw = safe_int(lower_record.get("wins"))
        ties = safe_int(higher_record.get("ties"))
        if abs(hw - lw) >= 2:
            angles.append("The regular-season head-to-head was not random noise; one side owned the matchup enough to matter in the preview.")
        elif ties >= 2:
            angles.append("The regular-season series produced multiple ties, which supports a tight-checking, coin-flip rivalry frame.")

    next_game = series.get("next_game") or {}
    if next_game:
        angles.append(f"The first posted playoff date is {next_game.get('local_date')}, so the preview can be written as an opening-night setup rather than a reactive recap.")
    return angles[:5]


def league_story_angles(standings: List[Mapping[str, object]], series_list: List[Mapping[str, object]]) -> List[str]:
    angles: List[str] = []
    if standings:
        top = standings[0]
        second = standings[1] if len(standings) > 1 else {}
        third = standings[2] if len(standings) > 2 else {}
        if safe_int(top.get("points")) - safe_int(second.get("points")) >= 6:
            angles.append(f"{top.get('team_name')} separated itself at the top of the table rather than merely surviving a crowded race.")
        if safe_int(second.get("points")) == safe_int(third.get("points")):
            angles.append(f"The middle of the playoff field was tight enough that {second.get('team_name')} and {third.get('team_name')} finished level on points.")
        bottom = standings[-1]
        if safe_int(bottom.get("points")) <= 10:
            angles.append(f"{bottom.get('team_name')} spent most of the year trying to climb out of a deep hole, which is a different narrative from a late miss.")
    if series_list:
        angles.append("The playoff bracket naturally splits into one favorite-versus-underdog semifinal and one rivalry semifinal with much tighter regular-season history.")
    return angles[:5]


def standing_movement_rows(standings: List[Dict[str, object]], team_month_checkpoints: Dict[str, List[Dict[str, object]]]) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for team in standings:
        team_slug = str(team.get("team_slug") or "")
        checkpoints = sorted(team_month_checkpoints.get(team_slug, []), key=lambda row: str(row.get("month") or ""))
        if not checkpoints:
            continue
        start = checkpoints[0]
        end = checkpoints[-1]
        rows.append(
            {
                "team_name": team.get("team_name"),
                "start_month": start.get("month_label"),
                "start_rank": start.get("rank"),
                "end_month": end.get("month_label"),
                "end_rank": end.get("rank"),
                "rank_change": safe_int(start.get("rank")) - safe_int(end.get("rank")),
            }
        )
    rows.sort(key=lambda row: (safe_int(row.get("end_rank"), 99), -safe_int(row.get("rank_change"))))
    return rows


def team_key_games(entries: List[Mapping[str, object]]) -> List[Dict[str, object]]:
    if not entries:
        return []
    rows: List[Tuple[str, Mapping[str, object]]] = []
    biggest_win = max(entries, key=lambda row: (safe_int(row.get("team_score")) - safe_int(row.get("opponent_score")), safe_int(row.get("team_score"))))
    rows.append(("Biggest win", biggest_win))
    toughest_loss = min(entries, key=lambda row: (safe_int(row.get("team_score")) - safe_int(row.get("opponent_score")), -safe_int(row.get("opponent_score"))))
    rows.append(("Toughest loss", toughest_loss))
    highest_event = max(entries, key=lambda row: safe_int(row.get("team_score")) + safe_int(row.get("opponent_score")))
    rows.append(("Highest-event game", highest_event))
    latest_playoff_team = None
    for row in reversed(entries):
        if row.get("is_playoff_opponent"):
            latest_playoff_team = row
            break
    if latest_playoff_team is not None:
        rows.append(("Latest vs playoff team", latest_playoff_team))
    output: List[Dict[str, object]] = []
    seen = set()
    for label, row in rows:
        gid = row.get("canonical_game_id")
        if gid in seen:
            continue
        seen.add(gid)
        output.append(
            {
                "label": label,
                "local_date": row.get("local_date"),
                "opponent_name": row.get("opponent_name"),
                "score": f"{row.get('team_score')}-{row.get('opponent_score')}",
                "result": row.get("result"),
                "canonical_game_id": gid,
            }
        )
    return output


def player_key_games(entries: List[Mapping[str, object]]) -> List[Dict[str, object]]:
    if not entries:
        return []
    rows = sorted(entries, key=lambda row: (safe_int(row.get("points")), safe_int(row.get("goals")), safe_int(row.get("assists"))), reverse=True)
    output: List[Dict[str, object]] = []
    for row in rows[:5]:
        output.append(
            {
                "local_date": row.get("local_date"),
                "opponent_name": row.get("opponent_name"),
                "score": f"{row.get('team_score')}-{row.get('opponent_score')}",
                "result": row.get("result"),
                "goals": row.get("goals"),
                "assists": row.get("assists"),
                "points": row.get("points"),
                "game_id": row.get("game_id"),
            }
        )
    return output


def build_league_pack(standings: List[Dict[str, object]], series_list: List[Dict[str, object]], players: List[Dict[str, object]], team_month_checkpoints: Dict[str, List[Dict[str, object]]]) -> Tuple[Dict[str, object], str]:
    points_leaders = sorted(players, key=lambda row: safe_int(row.get("points")), reverse=True)[:15]
    goals_leaders = sorted(players, key=lambda row: safe_int(row.get("goals")), reverse=True)[:15]
    assists_leaders = sorted(players, key=lambda row: safe_int(row.get("assists")), reverse=True)[:15]
    movement_rows = standing_movement_rows(standings, team_month_checkpoints)
    team_profile_rows = []
    for row in standings:
        gp = safe_int(row.get("wins")) + safe_int(row.get("losses")) + safe_int(row.get("ties"))
        gf = safe_int(row.get("goals_for"))
        ga = safe_int(row.get("goals_against"))
        team_profile_rows.append(
            {
                "team_name": row.get("team_name"),
                "gf_per_game": f"{(gf / gp):.2f}" if gp else "0.00",
                "ga_per_game": f"{(ga / gp):.2f}" if gp else "0.00",
                "goal_diff": gf - ga,
            }
        )

    month_end_table: List[Dict[str, object]] = []
    months = sorted({checkpoint["month"] for rows in team_month_checkpoints.values() for checkpoint in rows})
    for month in months:
        snapshot_rows = []
        for team in standings:
            slug = str(team.get("team_slug") or "")
            checkpoints = team_month_checkpoints.get(slug, [])
            match = next((row for row in checkpoints if row.get("month") == month), None)
            if match:
                snapshot_rows.append({"team_name": team.get("team_name"), "rank": match.get("rank"), "points": match.get("points")})
        snapshot_rows.sort(key=lambda row: safe_int(row.get("rank"), 99))
        month_end_table.append({"month": month, "month_label": month_label(month), "teams": snapshot_rows})

    pack = {
        "entity_type": "league",
        "entity_id": "aahl-2025-2026",
        "title": "AAHL 2025-2026 season league brief",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_facts": {
            "standings": standings,
            "month_end_checkpoints": month_end_table,
            "standing_movement": movement_rows,
            "team_profiles": team_profile_rows,
            "series": series_list,
            "leaders": {
                "points": points_leaders,
                "goals": goals_leaders,
                "assists": assists_leaders,
            },
        },
        "angles": league_story_angles(standings, series_list),
        "suggested_prompts": [
            "Write a front-page league season review that explains how the table settled and why the semifinal matchups feel different from each other.",
            "Write a newspaper-style playoff preview with one section on the top seed, one on the rivalry semifinal, and one on the scoring race that defined the year.",
            "Write a commissioner-style year-in-review focused on the biggest swings in standings position and the players who defined the season.",
        ],
    }

    points_rows = [[index + 1, display_name(str(player.get("name") or "Unknown")), player.get("team_name"), safe_int(player.get("points")), safe_int(player.get("goals")), safe_int(player.get("assists"))] for index, player in enumerate(points_leaders[:10])]
    goals_rows = [[index + 1, display_name(str(player.get("name") or "Unknown")), player.get("team_name"), safe_int(player.get("goals")), safe_int(player.get("points"))] for index, player in enumerate(goals_leaders[:10])]
    assists_rows = [[index + 1, display_name(str(player.get("name") or "Unknown")), player.get("team_name"), safe_int(player.get("assists")), safe_int(player.get("points"))] for index, player in enumerate(assists_leaders[:10])]

    lines = [
        render_frontmatter({"entity": "league", "season": "2025-2026", "type": "story_input"}),
        "# AAHL 2025-2026 League Story Pack",
        "",
        "## How To Use This File",
        "Paste this file into an LLM and ask it to write league-wide season recaps, playoff previews, or newspaper-style columns. Treat the facts below as hard constraints and the angles as optional framing.",
        "",
        "## Verified Facts",
        markdown_table(
            ["Rank", "Team", "Record", "Points", "GF", "GA", "Last 10", "Streak"],
            [[row.get("rank"), row.get("team_name"), row.get("record"), row.get("points"), row.get("goals_for"), row.get("goals_against"), row.get("last_10"), row.get("streak")] for row in standings],
        ),
        "",
        "## Month-End Standings Checkpoints",
    ]
    for month in month_end_table:
        lines.append(f"### {month.get('month_label')}")
        lines.append(markdown_table(["Rank", "Team", "Points"], [[row.get("rank"), row.get("team_name"), row.get("points")] for row in month.get("teams", [])]))
        lines.append("")
    lines.extend([
        "## Standings Movement",
        markdown_table(["Team", "Start Month", "Start Rank", "End Month", "End Rank", "Rank Change"], [[row.get("team_name"), row.get("start_month"), row.get("start_rank"), row.get("end_month"), row.get("end_rank"), row.get("rank_change")] for row in movement_rows]),
        "",
        "## Team Profile Snapshot",
        markdown_table(["Team", "GF/Game", "GA/Game", "Goal Diff"], [[row.get("team_name"), row.get("gf_per_game"), row.get("ga_per_game"), row.get("goal_diff")] for row in team_profile_rows]),
        "",
        "## Leaders",
        "### Points",
        markdown_table(["Rank", "Player", "Team", "PTS", "G", "A"], points_rows),
        "",
        "### Goals",
        markdown_table(["Rank", "Player", "Team", "G", "PTS"], goals_rows),
        "",
        "### Assists",
        markdown_table(["Rank", "Player", "Team", "A", "PTS"], assists_rows),
        "",
        "## Playoff Frame",
    ])
    for series in series_list:
        lines.append(f"- {series.get('label')}: {series.get('state_label')} | next game {((series.get('next_game') or {}).get('local_date') or 'TBD')} {((series.get('next_game') or {}).get('local_time') or '')}".rstrip())
    lines.extend(["", "## Derived Angles"])
    for angle in pack["angles"]:
        lines.append(f"- {angle}")
    lines.extend(["", "## Suggested Prompts"])
    for prompt in pack["suggested_prompts"]:
        lines.append(f"- {prompt}")
    return pack, "\n".join(lines).strip() + "\n"


def build_series_pack(series: Mapping[str, object], team_logs: Mapping[str, Dict[str, List[Dict[str, object]]]], players_by_team: Mapping[str, List[Dict[str, object]]]) -> Tuple[Dict[str, object], str]:
    higher = series.get("higher_seed", {}) or {}
    lower = series.get("lower_seed", {}) or {}
    higher_slug = str(higher.get("team_slug") or "")
    lower_slug = str(lower.get("team_slug") or "")
    higher_recent = list((team_logs.get(higher_slug, {}) or {}).get("final", []))[-5:]
    lower_recent = list((team_logs.get(lower_slug, {}) or {}).get("final", []))[-5:]
    regular_meetings = [
        row
        for row in (team_logs.get(higher_slug, {}) or {}).get("final", [])
        if row.get("opponent_slug") == lower_slug
    ]
    higher_leaders = sorted(players_by_team.get(higher_slug, []), key=lambda row: safe_int(row.get("points")), reverse=True)[:5]
    lower_leaders = sorted(players_by_team.get(lower_slug, []), key=lambda row: safe_int(row.get("points")), reverse=True)[:5]

    pack = {
        "entity_type": "series",
        "entity_id": series.get("series_id"),
        "title": series.get("label"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_facts": {
            "series": series,
            "regular_season_meetings": regular_meetings,
            "higher_seed_recent_results": higher_recent,
            "lower_seed_recent_results": lower_recent,
            "higher_seed_leaders": higher_leaders,
            "lower_seed_leaders": lower_leaders,
        },
        "angles": series_story_angles(series),
        "suggested_prompts": [
            f"Write a newspaper playoff preview for {series.get('label')} that explains why the matchup should be watched closely.",
            f"Write a feature on the stars and pressure points in the {series.get('label')} semifinal.",
        ],
    }

    def recent_rows(rows: List[Dict[str, object]]) -> List[List[object]]:
        ordered = list(reversed(rows))
        return [[row.get("local_date"), row.get("opponent_name"), row.get("result"), row.get("team_score"), row.get("opponent_score")] for row in ordered]

    def leader_rows(rows: List[Dict[str, object]]) -> List[List[object]]:
        return [[display_name(str(row.get("name") or "Unknown")), safe_int(row.get("points")), safe_int(row.get("goals")), safe_int(row.get("assists"))] for row in rows]

    lines = [
        render_frontmatter({"entity": "series", "series_id": series.get("series_id"), "type": "story_input"}),
        f"# {series.get('label')} Story Pack",
        "",
        "## How To Use This File",
        "Use this as source material for a playoff preview, game program writeup, or rivalry column. Treat the verified facts as hard constraints and the angles as framing choices.",
        "",
        "## Verified Facts",
        f"- Best-of format: {series.get('best_of')}",
        f"- Current state: {series.get('state_label')}",
        f"- Known dates: {', '.join(series.get('known_game_dates') or [])}",
    ]
    next_game = series.get("next_game") or {}
    if next_game:
        lines.append(f"- Next game: {next_game.get('local_date')} {next_game.get('local_time')} | {next_game.get('away_team')} at {next_game.get('home_team')}")
    h2h = series.get("regular_season_head_to_head") or {}
    if h2h:
        teams = h2h.get("teams", {})
        higher_record = teams.get(higher_slug, {}) if isinstance(teams, dict) else {}
        lower_record = teams.get(lower_slug, {}) if isinstance(teams, dict) else {}
        lines.append(f"- Regular-season head-to-head: {higher.get('team_name')} {higher_record.get('wins', 0)}-{higher_record.get('losses', 0)}-{higher_record.get('ties', 0)} vs {lower.get('team_name')} {lower_record.get('wins', 0)}-{lower_record.get('losses', 0)}-{lower_record.get('ties', 0)}")
    lines.extend([
        "",
        "## Regular-Season Meetings",
        markdown_table(["Date", "Site Team", "Opponent", "Result", "GF", "GA"], [[row.get("local_date"), higher.get("team_name"), row.get("opponent_name"), row.get("result"), row.get("team_score"), row.get("opponent_score")] for row in regular_meetings]),
        "",
        f"## {higher.get('team_name')} Last 5 Finals",
        markdown_table(["Date", "Opponent", "Result", "GF", "GA"], recent_rows(higher_recent)),
        "",
        f"## {lower.get('team_name')} Last 5 Finals",
        markdown_table(["Date", "Opponent", "Result", "GF", "GA"], recent_rows(lower_recent)),
        "",
        f"## {higher.get('team_name')} Key Scorers",
        markdown_table(["Player", "PTS", "G", "A"], leader_rows(higher_leaders)),
        "",
        f"## {lower.get('team_name')} Key Scorers",
        markdown_table(["Player", "PTS", "G", "A"], leader_rows(lower_leaders)),
        "",
        "## Derived Angles",
    ])
    for angle in pack["angles"]:
        lines.append(f"- {angle}")
    lines.extend(["", "## Suggested Prompts"])
    for prompt in pack["suggested_prompts"]:
        lines.append(f"- {prompt}")
    return pack, "\n".join(lines).strip() + "\n"


def build_team_pack(team: Mapping[str, object], team_meta: Mapping[str, object], monthly_checkpoints: List[Dict[str, object]], logs: Mapping[str, List[Dict[str, object]]], leaders: Mapping[str, List[Mapping[str, object]]], series: Optional[Mapping[str, object]], head_to_head: List[Mapping[str, object]], team_name_map: Mapping[str, str]) -> Tuple[Dict[str, object], str]:
    team_slug = str(team.get("team_slug") or "")
    final_logs = list((logs or {}).get("final", []))
    scheduled_logs = list((logs or {}).get("scheduled", []))
    monthly = monthly_team_splits(final_logs)
    month_timeline = monthly_team_timeline(final_logs)
    month_context_notes = monthly_team_context_notes(str(team.get("team_name") or "Unknown"), monthly, monthly_checkpoints, final_logs, team_name_map)
    key_games = team_key_games(final_logs)
    results_profile = summarize_team_results(final_logs)
    playoff_field_profile = summarize_team_results([row for row in final_logs if row.get("is_playoff_opponent")])
    rolling_windows = rolling_team_windows(final_logs, 5)
    half_splits = split_halves(final_logs, summarize_team_results)
    opponent_rows = opponent_team_splits(final_logs, team_name_map)
    streaks = {
        "longest_win_streak": streak_lengths(final_logs, lambda row: row.get("result") == "W"),
        "longest_winless_streak": streak_lengths(final_logs, lambda row: row.get("result") in {"L", "T"}),
    }
    h2h_rows = []
    for row in head_to_head:
        teams = row.get("teams", {}) if isinstance(row, dict) else {}
        if team_slug not in teams:
            continue
        opponent_slug = next((slug for slug in row.get("matchup", []) if slug != team_slug), None)
        record = teams.get(team_slug, {})
        h2h_rows.append({
            "opponent_slug": opponent_slug,
            "opponent_name": team_name_map.get(str(opponent_slug or ""), str(opponent_slug or "")),
            "wins": record.get("wins"),
            "losses": record.get("losses"),
            "ties": record.get("ties"),
            "gf": record.get("goals_for"),
            "ga": record.get("goals_against"),
        })
    pack = {
        "entity_type": "team",
        "entity_id": team_slug,
        "title": f"{team.get('team_name')} season story pack",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_facts": {
            "standing": team,
            "month_end_checkpoints": monthly_checkpoints,
            "monthly_game_splits": monthly,
            "monthly_timeline": month_timeline,
            "monthly_context_notes": month_context_notes,
            "results_profile": results_profile,
            "leaders": leaders,
            "key_games": key_games,
            "head_to_head": h2h_rows,
            "opponent_splits": opponent_rows,
            "vs_playoff_field": playoff_field_profile,
            "five_game_windows": rolling_windows,
            "half_splits": half_splits,
            "streaks": streaks,
            "recent_results": final_logs[-5:],
            "upcoming_games": scheduled_logs[:3],
            "playoff_context": series,
        },
        "angles": team_story_angles(team, monthly, leaders, series),
        "suggested_prompts": [
            f"Write a newspaper season recap for {team.get('team_name')} that explains how its season evolved month by month.",
            f"Write a playoff preview for {team.get('team_name')} that ties regular-season trends to the upcoming semifinal.",
            f"Write a long-form feature on the identity of {team.get('team_name')} based on its record, leaders, and turning points.",
        ],
    }
    lines = [
        render_frontmatter({"entity": "team", "team_slug": team_slug, "type": "story_input"}),
        f"# {team.get('team_name')} Story Pack",
        "",
        "## How To Use This File",
        "Use this as source material for a season recap, playoff preview, or identity piece. Treat the verified facts as hard constraints and the angles as optional framing.",
        "",
        "## Verified Facts",
        f"- Final standing: No. {team.get('rank')}",
        f"- Record: {team.get('record')}",
        f"- Points: {team.get('points')}",
        f"- Goals for / against: {team.get('goals_for')} / {team.get('goals_against')}",
        f"- Last 10: {team.get('last_10')}",
        f"- Streak entering playoffs: {team.get('streak')}",
        f"- Full-season points percentage: {results_profile.get('points_pct')}",
        f"- Longest win streak: {streaks.get('longest_win_streak')}",
        f"- Longest winless stretch: {streaks.get('longest_winless_streak')}",
        "",
        "## Month-End Standings Checkpoints",
        markdown_table(["Month", "Rank", "Points", "Record", "Streak"], [[row.get("month_label"), row.get("rank"), row.get("points"), row.get("record"), row.get("streak")] for row in monthly_checkpoints]),
        "",
        "## Monthly Game Splits",
        markdown_table(["Month", "GP", "W", "L", "T", "GF", "GA"], [[row.get("month_label"), row.get("gp"), row.get("wins"), row.get("losses"), row.get("ties"), row.get("gf"), row.get("ga")] for row in monthly]),
        "",
        "## Month-by-Month Narrative Timeline",
        markdown_table(["Month", "Record", "GF", "GA", "Notable Game"], [[row.get("month_label"), row.get("record"), row.get("gf"), row.get("ga"), row.get("notable_game")] for row in month_timeline]),
    ]
    lines.extend(["", "## Month-by-Month Team Context Notes"])
    for row in month_context_notes:
        lines.append(f"### {row.get('month_label')}")
        for note in row.get("notes", []):
            lines.append(f"- {note}")
        lines.append("")
    lines.extend([
        "## Team Leaders",
        "### Points",
        markdown_table(["Player", "PTS", "G", "A", "GP"], [[display_name(str(leader.get("name") or "Unknown")), leader.get("points"), leader.get("goals"), leader.get("assists"), leader.get("games_played")] for leader in (leaders.get("points") or [])[:5]]),
        "",
        "### Goals",
        markdown_table(["Player", "G", "PTS"], [[display_name(str(leader.get("name") or "Unknown")), leader.get("goals"), leader.get("points")] for leader in (leaders.get("goals") or [])[:5]]),
        "",
        "### Assists",
        markdown_table(["Player", "A", "PTS"], [[display_name(str(leader.get("name") or "Unknown")), leader.get("assists"), leader.get("points")] for leader in (leaders.get("assists") or [])[:5]]),
        "",
        "## Key Games",
        markdown_table(["Label", "Date", "Opponent", "Score", "Result"], [[row.get("label"), row.get("local_date"), row.get("opponent_name"), row.get("score"), row.get("result")] for row in key_games]),
        "",
        "## Recent Results",
        markdown_table(["Date", "Opponent", "Result", "GF", "GA"], [[row.get("local_date"), row.get("opponent_name"), row.get("result"), row.get("team_score"), row.get("opponent_score")] for row in list(reversed(final_logs[-5:]))]),
        "",
        "## Head-to-Head Snapshot",
        markdown_table(["Opponent", "W", "L", "T", "GF", "GA"], [[row.get("opponent_name"), row.get("wins"), row.get("losses"), row.get("ties"), row.get("gf"), row.get("ga")] for row in h2h_rows]),
        "",
        "## Opponent Splits",
        markdown_table(["Opponent", "GP", "Record", "GF", "GA", "Goal Diff"], [[row.get("opponent_name"), row.get("gp"), row.get("record"), row.get("gf"), row.get("ga"), row.get("goal_diff")] for row in opponent_rows]),
    ])
    if half_splits:
        lines.extend([
            "",
            "## First Half Vs Second Half",
            markdown_table(
                ["Split", "GP", "Record", "GF", "GA", "Points %"],
                [
                    ["First half", half_splits.get("first_half", {}).get("gp"), half_splits.get("first_half", {}).get("record"), half_splits.get("first_half", {}).get("gf"), half_splits.get("first_half", {}).get("ga"), half_splits.get("first_half", {}).get("points_pct")],
                    ["Second half", half_splits.get("second_half", {}).get("gp"), half_splits.get("second_half", {}).get("record"), half_splits.get("second_half", {}).get("gf"), half_splits.get("second_half", {}).get("ga"), half_splits.get("second_half", {}).get("points_pct")],
                ],
            ),
        ])
    lines.extend([
        "",
        "## Versus Playoff Field",
        f"- Record: {playoff_field_profile.get('record')}",
        f"- GF / GA: {playoff_field_profile.get('gf')} / {playoff_field_profile.get('ga')}",
        f"- Points percentage: {playoff_field_profile.get('points_pct')}",
    ])
    if rolling_windows:
        lines.extend([
            "",
            "## Best And Worst 5-Game Stretches",
            f"- Best 5-game run: {rolling_windows.get('best', {}).get('record')} from {rolling_windows.get('best', {}).get('start_date')} to {rolling_windows.get('best', {}).get('end_date')} with {rolling_windows.get('best', {}).get('gf')}-{rolling_windows.get('best', {}).get('ga')} goals.",
            f"- Worst 5-game run: {rolling_windows.get('worst', {}).get('record')} from {rolling_windows.get('worst', {}).get('start_date')} to {rolling_windows.get('worst', {}).get('end_date')} with {rolling_windows.get('worst', {}).get('gf')}-{rolling_windows.get('worst', {}).get('ga')} goals.",
        ])
    if series:
        next_game = series.get("next_game") or {}
        lines.extend([
            "",
            "## Playoff Context",
            f"- Series: {series.get('label')}",
            f"- State: {series.get('state_label')}",
            f"- Known dates: {', '.join(series.get('known_game_dates') or [])}",
        ])
        if next_game:
            lines.append(f"- Next game: {next_game.get('local_date')} {next_game.get('local_time')} vs {next_game.get('away_team') if next_game.get('home_team') == team.get('team_name') else next_game.get('home_team')}")
    lines.extend(["", "## Derived Angles"])
    for angle in pack["angles"]:
        lines.append(f"- {angle}")
    lines.extend(["", "## Suggested Prompts"])
    for prompt in pack["suggested_prompts"]:
        lines.append(f"- {prompt}")
    return pack, "\n".join(lines).strip() + "\n"


def build_player_pack(player: Mapping[str, object], logs: List[Dict[str, object]], checkpoints: List[Dict[str, object]], team_name: str, league_ranks: Mapping[str, Dict[str, int]], team_ranks: Mapping[str, Dict[str, Dict[str, int]]], team_name_map: Mapping[str, str], team_context: Mapping[str, object]) -> Tuple[Dict[str, object], str]:
    player_id = str(player.get("player_id") or "")
    team_slug = str(player.get("team_slug") or "")
    monthly = monthly_player_splits(logs)
    month_timeline = monthly_player_timeline(logs)
    key_games = player_key_games(logs)
    vs_playoff = [row for row in logs if row.get("is_playoff_opponent")]
    vs_playoff_totals = {
        "gp": len(vs_playoff),
        "goals": sum(safe_int(row.get("goals")) for row in vs_playoff),
        "assists": sum(safe_int(row.get("assists")) for row in vs_playoff),
        "points": sum(safe_int(row.get("points")) for row in vs_playoff),
    }
    result_splits = outcome_player_splits(logs)
    opponent_splits = opponent_player_splits(logs, team_name_map)
    rolling_windows = rolling_player_windows(logs, 5)
    half_splits = split_halves(logs, summarize_player_results)
    streaks = {
        "longest_point_streak": streak_lengths(logs, lambda row: safe_int(row.get("points")) >= 1),
        "longest_goal_streak": streak_lengths(logs, lambda row: safe_int(row.get("goals")) >= 1),
        "multi_point_games": sum(1 for row in logs if safe_int(row.get("points")) >= 2),
        "hat_tricks": sum(1 for row in logs if safe_int(row.get("goals")) >= 3),
    }
    season_profile = summarize_player_results(logs)
    coverage = player_log_coverage(player, logs)
    role_profile = player_team_role_profile(player, team_context.get("standing", {}), list(team_context.get("players", [])))
    team_context_rows = player_team_context_notes(
        team_name,
        list(team_context.get("monthly", [])),
        list(team_context.get("month_context_notes", [])),
        monthly,
        list(team_context.get("checkpoints", [])),
    )
    pack = {
        "entity_type": "player",
        "entity_id": player_id,
        "title": f"{display_name(str(player.get('name') or 'Unknown'))} season story pack",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verified_facts": {
            "player": player,
            "season_profile": season_profile,
            "month_end_checkpoints": checkpoints,
            "monthly_game_splits": monthly,
            "monthly_timeline": month_timeline,
            "key_games": key_games,
            "vs_playoff_teams": vs_playoff_totals,
            "result_splits": result_splits,
            "opponent_splits": opponent_splits,
            "five_game_windows": rolling_windows,
            "half_splits": half_splits,
            "streaks": streaks,
            "box_score_log_coverage": coverage,
            "team_role_profile": role_profile,
            "team_context_crossovers": team_context_rows,
        },
        "angles": player_story_angles(player, logs, monthly, checkpoints, league_ranks, team_ranks),
        "suggested_prompts": [
            f"Write a newspaper-style player profile on {display_name(str(player.get('name') or 'Unknown'))} and how his season developed month by month.",
            f"Write a playoff program feature on {display_name(str(player.get('name') or 'Unknown'))} that explains his role for {team_name}.",
            f"Write a local-sports column on what defined {display_name(str(player.get('name') or 'Unknown'))}'s 2025-2026 season.",
        ],
    }
    lines = [
        render_frontmatter({"entity": "player", "player_id": player_id, "team_slug": team_slug, "type": "story_input"}),
        f"# {display_name(str(player.get('name') or 'Unknown'))} Story Pack",
        "",
        "## How To Use This File",
        "Use this as source material for a player profile, season recap, or playoff feature. Treat the verified facts as hard constraints and use the angles only as framing ideas.",
        "",
        "## Verified Facts",
        f"- Team: {team_name}",
        f"- Number: {player.get('number')}",
        f"- Positions: {', '.join(player.get('positions') or []) if player.get('positions') else 'Unknown'}",
        f"- Season totals: {player.get('games_played')} GP, {player.get('goals')} G, {player.get('assists')} A, {player.get('points')} PTS, {player.get('penalty_minutes')} PIM",
        f"- Team games played: {player.get('team_games_played')}",
        f"- Team scoring rank: {(team_ranks.get(team_slug, {}).get('points', {}) or {}).get(player_id, 'n/a')}",
        f"- League scoring rank: {(league_ranks.get('points', {}) or {}).get(player_id, 'n/a')}",
        f"- Points per game: {player.get('points_per_game') or season_profile.get('points_per_game')}",
        f"- Logged-sample longest point streak: {streaks.get('longest_point_streak')}",
        f"- Logged-sample longest goal streak: {streaks.get('longest_goal_streak')}",
        "",
        "## Per-Game Log Coverage",
        f"- Logged box-score appearances: {coverage.get('logged_gp')} of {coverage.get('season_gp')} ({coverage.get('game_coverage_pct')})",
        f"- Logged goals / assists / points: {coverage.get('logged_goals')} / {coverage.get('logged_assists')} / {coverage.get('logged_points')}",
        f"- Season goals / assists / points: {coverage.get('season_goals')} / {coverage.get('season_assists')} / {coverage.get('season_points')}",
    ]
    if not coverage.get("is_complete"):
        lines.append("- Note: the game-by-game sections below use only the logged box-score sample, not the full season totals.")
    lines.extend([
        "",
        "## Month-End Progression",
        markdown_table(["Month", "GP", "G", "A", "PTS"], [[row.get("month_label"), row.get("games_played"), row.get("goals"), row.get("assists"), row.get("points")] for row in checkpoints]),
        "",
        "## Monthly Game Splits",
        markdown_table(["Month", "GP", "G", "A", "PTS", "Multi-point games"], [[row.get("month_label"), row.get("gp"), row.get("goals"), row.get("assists"), row.get("points"), row.get("multi_point_games")] for row in monthly]),
        "",
        "## Month-by-Month Narrative Timeline",
        markdown_table(["Month", "GP", "G", "A", "PTS", "Top Game"], [[row.get("month_label"), row.get("gp"), row.get("goals"), row.get("assists"), row.get("points"), row.get("top_game")] for row in month_timeline]),
        "",
        "## Best Games",
        markdown_table(["Date", "Opponent", "Result", "Score", "G", "A", "PTS"], [[row.get("local_date"), row.get("opponent_name"), row.get("result"), row.get("score"), row.get("goals"), row.get("assists"), row.get("points")] for row in key_games]),
        "",
        "## Recent Games",
        markdown_table(["Date", "Opponent", "Result", "G", "A", "PTS"], [[row.get("local_date"), row.get("opponent_name"), row.get("result"), row.get("goals"), row.get("assists"), row.get("points")] for row in list(reversed(logs[-5:]))]),
        "",
        "## Versus Playoff Teams",
        f"- GP: {vs_playoff_totals['gp']}",
        f"- G: {vs_playoff_totals['goals']}",
        f"- A: {vs_playoff_totals['assists']}",
        f"- PTS: {vs_playoff_totals['points']}",
        "",
        "## Results Splits",
        markdown_table(["Result", "GP", "G", "A", "PTS", "P/GP"], [[row.get("result"), row.get("gp"), row.get("goals"), row.get("assists"), row.get("points"), row.get("points_per_game")] for row in result_splits]),
        "",
        "## Opponent Splits",
        markdown_table(["Opponent", "GP", "G", "A", "PTS", "P/GP"], [[row.get("opponent_name"), row.get("gp"), row.get("goals"), row.get("assists"), row.get("points"), row.get("points_per_game")] for row in opponent_splits[:8]]),
    ])
    lines.extend([
        "",
        "## Team Context Crossovers",
        f"- Team finish: No. {role_profile.get('team_rank')} at {role_profile.get('team_record')}",
        f"- Team scoring rank: {role_profile.get('team_points_rank')}",
        f"- Share of team goals: {role_profile.get('goal_share_pct')}",
    ])
    if safe_int(role_profile.get("gap_to_team_leader")) > 0:
        lines.append(f"- Gap to team points leader {role_profile.get('team_points_leader')}: {role_profile.get('gap_to_team_leader')} points")
    elif safe_int(role_profile.get("lead_over_next_teammate")) > 0:
        lines.append(f"- Lead over next teammate in points: {role_profile.get('lead_over_next_teammate')}")
    for row in team_context_rows:
        lines.append("")
        lines.append(f"### {row.get('month_label')}")
        for note in row.get("notes", []):
            lines.append(f"- {note}")
    if half_splits:
        lines.extend([
            "",
            "## First Half Vs Second Half",
            markdown_table(
                ["Split", "GP", "G", "A", "PTS", "P/GP"],
                [
                    ["First half", half_splits.get("first_half", {}).get("gp"), half_splits.get("first_half", {}).get("goals"), half_splits.get("first_half", {}).get("assists"), half_splits.get("first_half", {}).get("points"), half_splits.get("first_half", {}).get("points_per_game")],
                    ["Second half", half_splits.get("second_half", {}).get("gp"), half_splits.get("second_half", {}).get("goals"), half_splits.get("second_half", {}).get("assists"), half_splits.get("second_half", {}).get("points"), half_splits.get("second_half", {}).get("points_per_game")],
                ],
            ),
        ])
    if rolling_windows:
        lines.extend([
            "",
            "## Best And Worst 5-Game Stretches",
            f"- Best 5-game run: {rolling_windows.get('best', {}).get('points')} points ({rolling_windows.get('best', {}).get('goals')}-{rolling_windows.get('best', {}).get('assists')}) from {rolling_windows.get('best', {}).get('start_date')} to {rolling_windows.get('best', {}).get('end_date')}.",
            f"- Quietest 5-game run: {rolling_windows.get('worst', {}).get('points')} points ({rolling_windows.get('worst', {}).get('goals')}-{rolling_windows.get('worst', {}).get('assists')}) from {rolling_windows.get('worst', {}).get('start_date')} to {rolling_windows.get('worst', {}).get('end_date')}.",
        ])
    lines.extend([
        "",
        "## Derived Angles",
    ])
    if not coverage.get("is_complete"):
        lines.append("- Coverage note: angles that depend on game-by-game logs are based on the logged box-score sample.")
    for angle in pack["angles"]:
        lines.append(f"- {angle}")
    lines.extend(["", "## Suggested Prompts"])
    for prompt in pack["suggested_prompts"]:
        lines.append(f"- {prompt}")
    return pack, "\n".join(lines).strip() + "\n"


def main() -> None:
    team_meta = build_team_meta()
    standings = build_standings()
    games = build_games()
    series_list = build_series()
    players = build_player_registry()
    results = build_results()
    team_month_checkpoints = build_standing_checkpoints()
    player_month_checkpoints = build_player_checkpoints()

    playoff_teams = {
        str(team.get("team_slug") or "")
        for series in series_list
        for team in (series.get("higher_seed", {}), series.get("lower_seed", {}))
        if isinstance(team, dict) and team.get("team_slug")
    }

    team_logs = build_team_logs(games, playoff_teams)
    player_logs = build_player_logs(results, playoff_teams)
    league_ranks = rank_maps(players)
    team_ranks = team_rank_maps(players)
    players_by_team: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for player in players:
        players_by_team[str(player.get("team_slug") or "")].append(player)
    team_name_map: Dict[str, str] = {}
    for team in standings:
        team_slug = str(team.get("team_slug") or "")
        team_name = str(team.get("team_name") or "")
        if team_slug and team_name:
            team_name_map[team_slug] = team_name
    for team_slug, meta in team_meta.items():
        name = str(meta.get("name") or "")
        if team_slug and name:
            team_name_map[team_slug] = name

    head_to_head = (load_json(V2_DIR / "season_overview.json") or {}).get("head_to_head_matrix", [])
    if not isinstance(head_to_head, list):
        head_to_head = []

    team_series_map: Dict[str, Dict[str, object]] = {}
    for series in series_list:
        for side in ("higher_seed", "lower_seed"):
            team = series.get(side, {})
            if isinstance(team, dict) and team.get("team_slug"):
                team_series_map[str(team["team_slug"])] = series

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_text(
        OUTPUT_DIR / "README.md",
        "# Story Inputs\n\nThese files are deterministic fact packs for manual use with frontier models. They are not generated stories. Each file separates verified facts, derived angles, and suggested prompts.\n\nPlayer packs include a `Per-Game Log Coverage` section. When that coverage is below full season totals, the game-by-game sections in that player file are only a logged box-score sample and should be treated as partial chronology rather than complete season accounting.\n\nThe `templates/` directory contains copy-paste prompt shells for league reviews, team recaps, player profiles, and series previews. Pair one template with one pack.\n",
    )
    for filename, content in PROMPT_TEMPLATES.items():
        write_text(OUTPUT_DIR / "templates" / filename, content)

    league_pack, league_md = build_league_pack(standings, series_list, players, team_month_checkpoints)
    write_json(OUTPUT_DIR / "league" / "season.json", league_pack)
    write_text(OUTPUT_DIR / "league" / "season.md", league_md)

    index: Dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "league": {
            "json": "league/season.json",
            "markdown": "league/season.md",
        },
        "series": [],
        "teams": [],
        "players": [],
        "templates": [],
    }

    for filename in sorted(PROMPT_TEMPLATES):
        index["templates"].append(
            {
                "name": filename,
                "markdown": f"templates/{filename}",
            }
        )

    for series in series_list:
        pack, md = build_series_pack(series, team_logs, players_by_team)
        series_id = str(series.get("series_id") or "unknown-series")
        write_json(OUTPUT_DIR / "series" / f"{series_id}.json", pack)
        write_text(OUTPUT_DIR / "series" / f"{series_id}.md", md)
        index["series"].append({
            "series_id": series_id,
            "label": series.get("label"),
            "json": f"series/{series_id}.json",
            "markdown": f"series/{series_id}.md",
        })

    standings_by_slug = {str(team.get("team_slug") or ""): team for team in standings}
    team_story_contexts: Dict[str, Dict[str, object]] = {}
    for team_slug, meta in sorted(team_meta.items()):
        standing = standings_by_slug.get(team_slug, {"team_slug": team_slug, "team_name": meta.get("name")})
        top_points = sorted(players_by_team.get(team_slug, []), key=lambda row: safe_int(row.get("points")), reverse=True)
        top_goals = sorted(players_by_team.get(team_slug, []), key=lambda row: safe_int(row.get("goals")), reverse=True)
        top_assists = sorted(players_by_team.get(team_slug, []), key=lambda row: safe_int(row.get("assists")), reverse=True)
        team_final_logs = team_logs.get(team_slug, {"final": [], "scheduled": []}).get("final", [])
        team_monthly = monthly_team_splits(list(team_final_logs))
        team_month_notes = monthly_team_context_notes(
            str(standing.get("team_name") or meta.get("name") or team_slug),
            team_monthly,
            team_month_checkpoints.get(team_slug, []),
            list(team_final_logs),
            team_name_map,
        )
        leaders = {
            "points": top_points,
            "goals": top_goals,
            "assists": top_assists,
        }
        pack, md = build_team_pack(
            standing,
            meta,
            team_month_checkpoints.get(team_slug, []),
            team_logs.get(team_slug, {"final": [], "scheduled": []}),
            leaders,
            team_series_map.get(team_slug),
            head_to_head,
            team_name_map,
        )
        write_json(OUTPUT_DIR / "teams" / f"{team_slug}.json", pack)
        write_text(OUTPUT_DIR / "teams" / f"{team_slug}.md", md)
        team_story_contexts[team_slug] = {
            "standing": standing,
            "players": players_by_team.get(team_slug, []),
            "monthly": team_monthly,
            "month_context_notes": team_month_notes,
            "checkpoints": team_month_checkpoints.get(team_slug, []),
        }
        index["teams"].append({
            "team_slug": team_slug,
            "team_name": meta.get("name"),
            "json": f"teams/{team_slug}.json",
            "markdown": f"teams/{team_slug}.md",
        })

    for player in players:
        player_id = str(player.get("player_id") or "")
        if not player_id:
            continue
        team_name = str(player.get("team_name") or "Unknown")
        pack, md = build_player_pack(
            player,
            player_logs.get(player_id, []),
            player_month_checkpoints.get(player_id, []),
            team_name,
            league_ranks,
            team_ranks,
            team_name_map,
            team_story_contexts.get(str(player.get("team_slug") or ""), {}),
        )
        write_json(OUTPUT_DIR / "players" / f"{player_id}.json", pack)
        write_text(OUTPUT_DIR / "players" / f"{player_id}.md", md)
        index["players"].append({
            "player_id": player_id,
            "team_slug": player.get("team_slug"),
            "name": player.get("name"),
            "json": f"players/{player_id}.json",
            "markdown": f"players/{player_id}.md",
        })

    write_json(OUTPUT_DIR / "index.json", index)


if __name__ == "__main__":
    main()
