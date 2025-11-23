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
