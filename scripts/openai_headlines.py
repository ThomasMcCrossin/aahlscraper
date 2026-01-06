#!/usr/bin/env python3
"""
OpenAI integration for generating polished game headlines and summaries.
"""

from __future__ import annotations

import json
import os
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_PATH = DATA_DIR / "ai_headlines_cache.json"


def _safe_int(value: Any) -> Optional[int]:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return None


def _team_name(game: Dict[str, Any], side: str) -> str:
    line = game.get(f"{side}_line")
    if isinstance(line, dict) and line.get("name"):
        return str(line["name"])
    value = game.get(side)
    if isinstance(value, str):
        return value
    return "Unknown"


def _format_player_stats(game: Dict[str, Any], side: str) -> str:
    """Format player statistics for a team in a game."""
    stats = game.get("player_stats", {})
    players = stats.get(side, [])
    if not players:
        return "No player stats available"

    lines = []
    for player in sorted(players, key=lambda p: (_safe_int(p.get("goals")) or 0) + (_safe_int(p.get("assists")) or 0), reverse=True)[:5]:
        name = player.get("name", "Unknown")
        goals = _safe_int(player.get("goals")) or 0
        assists = _safe_int(player.get("assists")) or 0
        if goals or assists:
            lines.append(f"  - {name}: {goals}G, {assists}A")

    return "\n".join(lines) if lines else "No scoring"


def _game_hash(game: Dict[str, Any]) -> str:
    """Create a unique hash for a game based on key attributes."""
    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score")) or 0
    away_score = _safe_int(game.get("away_score")) or 0
    game_id = game.get("game_id", "")

    key = f"{game_id}:{home}:{away}:{home_score}:{away_score}"
    return hashlib.md5(key.encode()).hexdigest()


def _load_cache() -> Dict[str, Dict[str, Any]]:
    """Load the AI headlines cache."""
    if not CACHE_PATH.exists():
        return {}
    try:
        with CACHE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_cache(cache: Dict[str, Dict[str, Any]]) -> None:
    """Save the AI headlines cache."""
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


def generate_ai_headline(game: Dict[str, Any], use_cache: bool = True) -> Optional[str]:
    """
    Generate an AI-polished headline for a game using OpenAI.

    Args:
        game: Game data dictionary with scores and player stats
        use_cache: Whether to use cached headlines

    Returns:
        AI-generated headline or None if generation fails
    """
    if not OPENAI_AVAILABLE:
        print("OpenAI library not available. Install with: pip install openai")
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    # Check cache
    game_key = _game_hash(game)
    if use_cache:
        cache = _load_cache()
        if game_key in cache:
            return cache[game_key].get("headline")

    # Extract game data
    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score")) or 0
    away_score = _safe_int(game.get("away_score")) or 0

    # Determine winner
    if home_score > away_score:
        winner, loser = home, away
        winner_score, loser_score = home_score, away_score
        winner_side = "home"
    elif away_score > home_score:
        winner, loser = away, home
        winner_score, loser_score = away_score, home_score
        winner_side = "away"
    else:
        winner = loser = None
        winner_score = loser_score = home_score
        winner_side = None

    # Build context
    home_stats = _format_player_stats(game, "home")
    away_stats = _format_player_stats(game, "away")

    # Construct prompt
    if winner:
        prompt = f"""Generate a concise, engaging sports headline for this hockey game result.

Game Result: {winner} defeats {loser}, {winner_score}-{loser_score}

{winner} Top Performers:
{_format_player_stats(game, winner_side)}

{loser} Top Performers:
{_format_player_stats(game, "away" if winner_side == "home" else "home")}

Requirements:
- Maximum 120 characters
- Highlight the winning team and score
- Mention the top performer(s) if they had notable stats (hat trick = 3+ goals, multi-point game)
- Use active, dynamic language (e.g., "dominates", "edges", "powers past")
- No quotes, just the headline text
- Sports news style, professional tone

Headline:"""
    else:
        prompt = f"""Generate a concise, engaging sports headline for this hockey game that ended in a tie.

Game Result: {home} ties {away}, {home_score}-{away_score}

{home} Top Performers:
{home_stats}

{away} Top Performers:
{away_stats}

Requirements:
- Maximum 120 characters
- Mention both teams and the tie score
- Highlight any standout performers
- Use engaging language appropriate for a tie
- No quotes, just the headline text
- Sports news style, professional tone

Headline:"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional sports journalist writing concise, engaging hockey game headlines. Keep headlines under 120 characters, use active voice, and highlight key performers."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=100,
            temperature=0.7
        )

        headline = response.choices[0].message.content.strip()

        # Clean up the headline
        headline = headline.strip('"\'')
        if len(headline) > 150:
            headline = headline[:147] + "..."

        # Cache the result
        cache = _load_cache()
        cache[game_key] = {
            "headline": headline,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "game_id": game.get("game_id")
        }
        _save_cache(cache)

        return headline

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def generate_game_summary(game: Dict[str, Any]) -> Optional[str]:
    """
    Generate a brief game summary paragraph using OpenAI.

    Args:
        game: Game data dictionary

    Returns:
        AI-generated summary or None if generation fails
    """
    if not OPENAI_AVAILABLE:
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score")) or 0
    away_score = _safe_int(game.get("away_score")) or 0

    home_stats = _format_player_stats(game, "home")
    away_stats = _format_player_stats(game, "away")

    prompt = f"""Write a brief 2-3 sentence game summary for this hockey game.

Final Score: {away} {away_score}, {home} {home_score}

{home} Performers:
{home_stats}

{away} Performers:
{away_stats}

Requirements:
- 2-3 sentences maximum
- Professional sports recap style
- Mention the final score and key performers
- Note any hat tricks (3+ goals) or multi-point games
- Active, engaging voice

Summary:"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are a professional sports journalist writing brief game recaps for a local hockey league."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=200,
            temperature=0.7
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        print(f"OpenAI API error: {e}")
        return None


def generate_rich_narrative(
    game: Dict[str, Any],
    standings: Optional[List[Dict[str, Any]]] = None,
    use_cache: bool = True
) -> Optional[str]:
    """
    Generate a rich, extended narrative for a game result.

    Includes context like team streaks, playoff implications, and detailed
    game flow narrative suitable for filling display space.

    Args:
        game: Game data dictionary with scores and player stats
        standings: Optional standings data for streak/playoff context
        use_cache: Whether to use cached narratives

    Returns:
        AI-generated narrative (2-3 paragraphs) or None if generation fails
    """
    if not OPENAI_AVAILABLE:
        return None

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None

    # Check cache with different key for narratives
    game_key = _game_hash(game) + "_narrative"
    if use_cache:
        cache = _load_cache()
        if game_key in cache:
            return cache[game_key].get("narrative")

    # Extract game data
    home = _team_name(game, "home")
    away = _team_name(game, "away")
    home_score = _safe_int(game.get("home_score")) or 0
    away_score = _safe_int(game.get("away_score")) or 0

    # Determine winner
    if home_score > away_score:
        winner, loser = home, away
        winner_score, loser_score = home_score, away_score
        winner_side, loser_side = "home", "away"
    elif away_score > home_score:
        winner, loser = away, home
        winner_score, loser_score = away_score, home_score
        winner_side, loser_side = "away", "home"
    else:
        winner = loser = None
        winner_score = loser_score = home_score
        winner_side = loser_side = None

    # Build standings context
    standings_context = ""
    if standings:
        standings_map = {s.get("team", "").lower(): s for s in standings if isinstance(s, dict)}

        home_standing = standings_map.get(home.lower(), {})
        away_standing = standings_map.get(away.lower(), {})

        home_streak = home_standing.get("streak", "")
        away_streak = away_standing.get("streak", "")
        home_rank = None
        away_rank = None

        # Find ranks
        sorted_standings = sorted(standings, key=lambda x: _safe_int(x.get("points")) or 0, reverse=True)
        for i, team in enumerate(sorted_standings, 1):
            if team.get("team", "").lower() == home.lower():
                home_rank = i
            if team.get("team", "").lower() == away.lower():
                away_rank = i

        standings_lines = []
        if home_streak:
            standings_lines.append(f"- {home} entering game: {home_streak}" + (f", ranked #{home_rank}" if home_rank else ""))
        if away_streak:
            standings_lines.append(f"- {away} entering game: {away_streak}" + (f", ranked #{away_rank}" if away_rank else ""))

        # Playoff context (top 4 make playoffs)
        if home_rank and away_rank:
            if home_rank <= 4 and away_rank <= 4:
                standings_lines.append("- Playoff positioning matchup between two playoff teams")
            elif home_rank == 4 or away_rank == 4 or home_rank == 5 or away_rank == 5:
                standings_lines.append("- Playoff bubble implications")

        if standings_lines:
            standings_context = "Team Context:\n" + "\n".join(standings_lines)

    # Period scores if available
    period_context = ""
    period_scores = game.get("period_scores", {})
    if period_scores:
        lines = []
        for period, scores in period_scores.items():
            if isinstance(scores, dict):
                h = scores.get("home", 0)
                a = scores.get("away", 0)
                lines.append(f"  {period}: {away} {a}, {home} {h}")
        if lines:
            period_context = "Period Breakdown:\n" + "\n".join(lines)

    # Player stats
    winner_stats = _format_player_stats(game, winner_side) if winner_side else _format_player_stats(game, "home")
    loser_stats = _format_player_stats(game, loser_side) if loser_side else _format_player_stats(game, "away")

    # Construct rich prompt - stick to facts we actually have
    if winner:
        prompt = f"""Write a game recap for this adult hockey league game. This displays on a TV in the arena.

FINAL: {winner} {winner_score}, {loser} {loser_score}

{standings_context}

{winner} Scoring:
{winner_stats}

{loser} Scoring:
{loser_stats}

WRITE A 2-3 SENTENCE RECAP:
- State the final score and winning team
- Name the top scorer(s) with their actual stats (e.g., "Isaac Bridge led the way with 4 goals and an assist")
- If someone scored 3+ goals, call it a hat trick
- If someone had 4+ points, mention their "X-point night"
- Optionally mention standings context if provided above
- Keep it factual - only reference stats shown above
- Professional but casual tone suitable for a local league

RECAP:"""
    else:
        prompt = f"""Write a game recap for this adult hockey league game that ended in a tie. This displays on a TV in the arena.

FINAL: {home} {home_score}, {away} {away_score} (TIE)

{standings_context}

{home} Scoring:
{_format_player_stats(game, "home")}

{away} Scoring:
{_format_player_stats(game, "away")}

WRITE A 2-3 SENTENCE RECAP:
- State the tie score
- Name top scorers from each team with their actual stats
- Keep it factual - only reference stats shown above
- Professional but casual tone suitable for a local league

RECAP:"""

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You write factual game recaps for the Amherst Adult Hockey League. Only mention stats explicitly provided - never invent or assume details. Keep recaps to 2-3 sentences."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            max_tokens=150,
            temperature=0.5
        )

        narrative = response.choices[0].message.content.strip()

        # Cache the result
        cache = _load_cache()
        cache[game_key] = {
            "narrative": narrative,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "game_id": game.get("game_id")
        }
        _save_cache(cache)

        return narrative

    except Exception as e:
        print(f"OpenAI API error generating narrative: {e}")
        return None


def enrich_games_with_ai(games: List[Dict[str, Any]], max_games: int = 10) -> List[Dict[str, Any]]:
    """
    Enrich a list of games with AI-generated headlines.

    Args:
        games: List of game dictionaries
        max_games: Maximum number of games to process

    Returns:
        Enriched list of games with AI headlines
    """
    enriched = []
    processed = 0

    for game in games:
        game_copy = dict(game)

        # Only generate AI headlines for games with scores
        home_score = _safe_int(game.get("home_score"))
        away_score = _safe_int(game.get("away_score"))

        if home_score is not None and away_score is not None and processed < max_games:
            ai_headline = generate_ai_headline(game)
            if ai_headline:
                game_copy["ai_headline"] = ai_headline
                # Use AI headline as primary if no headline exists
                if not game_copy.get("headline"):
                    game_copy["headline"] = ai_headline
            processed += 1

        enriched.append(game_copy)

    return enriched


def main():
    """Generate AI headlines for recent games."""
    results_path = DATA_DIR / "results.json"
    if not results_path.exists():
        print("No results.json found")
        return

    with results_path.open("r", encoding="utf-8") as f:
        results = json.load(f)

    if not results:
        print("No games found in results.json")
        return

    # Process recent games
    recent = sorted(
        results,
        key=lambda g: g.get("datetime", ""),
        reverse=True
    )[:10]

    print(f"Processing {len(recent)} recent games...")

    for game in recent:
        game_id = game.get("game_id", "?")
        home = _team_name(game, "home")
        away = _team_name(game, "away")
        home_score = _safe_int(game.get("home_score")) or 0
        away_score = _safe_int(game.get("away_score")) or 0

        headline = generate_ai_headline(game)
        if headline:
            print(f"\nGame {game_id}: {away} {away_score} @ {home} {home_score}")
            print(f"  AI Headline: {headline}")
        else:
            print(f"\nGame {game_id}: Failed to generate headline")


if __name__ == "__main__":
    main()
