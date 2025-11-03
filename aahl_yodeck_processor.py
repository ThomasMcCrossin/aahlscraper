#!/usr/bin/env python3
"""
AAHL Data Processor for Yodeck Display
Enhances the AAHL scraper output with name corrections and formats data for Yodeck.
"""

import json
import csv
import re
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

class AAHLDataProcessor:
    """Process AAHL scraper data with corrections and formatting for Yodeck display."""

    # Name corrections mapping
    NAME_CORRECTIONS = {
        r'Meathead': 'Marshall',
        r'Mccrossin': 'McCrossin',
    }

    def __init__(self, data_dir: str = "data"):
        """Initialize processor with data directory."""
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

    def correct_names(self, text: str) -> str:
        """Apply name corrections to text."""
        corrected = text
        for pattern, replacement in self.NAME_CORRECTIONS.items():
            corrected = re.sub(pattern, replacement, corrected, flags=re.IGNORECASE)
        return corrected

    def correct_player_names_in_list(self, players: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Apply name corrections to player data."""
        corrected = []
        for player in players:
            corrected_player = player.copy()
            if 'player_name' in corrected_player:
                corrected_player['player_name'] = self.correct_names(corrected_player['player_name'])
            if 'name' in corrected_player:
                corrected_player['name'] = self.correct_names(corrected_player['name'])
            corrected.append(corrected_player)
        return corrected

    def load_schedule(self) -> List[Dict[str, Any]]:
        """Load schedule from CSV or JSON."""
        schedule_csv = self.data_dir / "schedule.csv"
        schedule_json = self.data_dir / "schedule.json"

        if schedule_json.exists():
            with open(schedule_json, 'r') as f:
                return json.load(f)
        elif schedule_csv.exists():
            schedule = []
            with open(schedule_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    schedule.append(row)
            return schedule
        return []

    def load_stats(self) -> List[Dict[str, Any]]:
        """Load player stats from CSV or JSON."""
        stats_csv = self.data_dir / "player_stats.csv"
        stats_json = self.data_dir / "player_stats.json"

        if stats_json.exists():
            with open(stats_json, 'r') as f:
                return json.load(f)
        elif stats_csv.exists():
            stats = []
            with open(stats_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    stats.append(row)
            return stats
        return []

    def load_standings(self) -> List[Dict[str, Any]]:
        """Load standings from CSV or JSON."""
        standings_csv = self.data_dir / "standings.csv"
        standings_json = self.data_dir / "standings.json"

        if standings_json.exists():
            with open(standings_json, 'r') as f:
                return json.load(f)
        elif standings_csv.exists():
            standings = []
            with open(standings_csv, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    standings.append(row)
            return standings
        return []

    def filter_amherst_games(self, schedule: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Filter schedule for Amherst games, split into completed and upcoming.

        Uses per-game ISO "datetime" when available; otherwise falls back to date header
        parsing and/or presence of a numeric score.
        """
        now = datetime.now()

        def has_score(g: Dict[str, Any]) -> bool:
            # Consider any numeric score as a played game
            for k in ("result", "score", "home_score", "away_score"):
                v = (g.get(k) or "").strip()
                if v.isdigit():
                    return True
            # Also catch strings like "3 - 2"
            for v in g.values():
                s = (str(v) or "").strip()
                if s and ("-" in s) and any(ch.isdigit() for ch in s):
                    return True
            return False

        def to_dt(g: Dict[str, Any]) -> Optional[datetime]:
            # Prefer explicit ISO datetime
            if g.get("datetime"):
                try:
                    return datetime.fromisoformat(g["datetime"])
                except Exception:
                    pass
            # Try combining date header + time
            date_txt = (g.get("date") or "").strip()
            time_txt = (g.get("time") or "").strip()
            if date_txt and time_txt:
                for fmt in ("%A, %B %d, %Y %I:%M %p", "%A, %B %d, %Y %I %p", "%A, %B %d, %Y %H:%M"):
                    try:
                        return datetime.strptime(f"{date_txt} {time_txt}", fmt)
                    except ValueError:
                        continue
            if date_txt:
                try:
                    return datetime.strptime(date_txt, "%A, %B %d, %Y")
                except Exception:
                    return None
            return None

        amherst_recent: List[Dict[str, Any]] = []
        amherst_upcoming: List[Dict[str, Any]] = []

        for game in schedule:
            try:
                location = (game.get('location', game.get('Location', '')) or '').lower()
                if 'amherst' not in location:
                    continue

                game_copy = game.copy()
                # Name corrections
                for side in ("home", "away"):
                    if side in game_copy and isinstance(game_copy[side], str):
                        game_copy[side] = self.correct_names(game_copy[side])

                dt = to_dt(game_copy)
                played = has_score(game_copy)

                if played or (dt and dt < now):
                    amherst_recent.append(game_copy)
                else:
                    amherst_upcoming.append(game_copy)

            except Exception as e:
                print(f"Error processing game: {e}")
                continue

        # Sort: recent newest first, upcoming earliest first
        def sort_key(g: Dict[str, Any]):
            d = to_dt(g)
            return d or datetime.max

        recent_sorted = sorted(amherst_recent, key=sort_key, reverse=True)[:10]
        upcoming_sorted = sorted(amherst_upcoming, key=sort_key)[:10]

        return {
            'recent_results': recent_sorted,
            'upcoming_games': upcoming_sorted,
        }

    def get_top_scorers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top scorers with corrections applied."""
        stats = self.load_stats()

        # Parse points from various field names
        for stat in stats:
            try:
                if 'pts' in stat and stat['pts']:
                    stat['points'] = int(stat['pts'])
                elif 'points' in stat and stat['points']:
                    stat['points'] = int(stat['points'])
                elif 'g' in stat and 'a' in stat:
                    goals = int(stat.get('g', 0) or 0)
                    assists = int(stat.get('a', 0) or 0)
                    stat['points'] = goals + assists
                else:
                    goals = int(stat.get('goals', stat.get('Goals', 0)) or 0)
                    assists = int(stat.get('assists', stat.get('Assists', 0)) or 0)
                    stat['points'] = goals + assists
            except (ValueError, TypeError):
                stat['points'] = 0

        sorted_stats = sorted(stats, key=lambda x: x.get('points', 0), reverse=True)[:limit]

        ranked = []
        for idx, stat in enumerate(sorted_stats, 1):
            stat_copy = stat.copy()
            stat_copy['rank'] = idx
            if 'player_name' in stat_copy:
                stat_copy['player_name'] = self.correct_names(stat_copy['player_name'])
            if 'name' in stat_copy:
                stat_copy['name'] = self.correct_names(stat_copy['name'])
            ranked.append(stat_copy)

        return ranked

    def generate_yodeck_data(self) -> Dict[str, Any]:
        """Generate complete data package for Yodeck display."""
        standings = self.load_standings()
        top_scorers = self.get_top_scorers(20)
        schedule = self.load_schedule()
        games = self.filter_amherst_games(schedule)

        # Format standings
        formatted_standings = []
        for team in standings:
            wins = 0
            losses = 0
            record = team.get('record', team.get('Record', ''))
            if record and '-' in record:
                try:
                    parts = record.split('-')
                    wins = int(parts[0])
                    losses = int(parts[1])
                except (ValueError, IndexError):
                    pass

            points = 0
            try:
                if 'pts' in team and team['pts'] and team['pts'] != '-':
                    points = int(team['pts'])
                elif 'points' in team:
                    points = int(team.get('points', 0))
                elif 'Points' in team:
                    points = int(team.get('Points', 0))
            except (ValueError, TypeError):
                pass

            formatted_standings.append({
                'team': self.correct_names(team.get('team', team.get('Team', ''))),
                'wins': wins,
                'losses': losses,
                'points': points,
            })

        return {
            'timestamp': datetime.now().isoformat(),
            'standings': formatted_standings,
            'top_scorers': top_scorers,
            'recent_results': games['recent_results'],
            'upcoming_games': games['upcoming_games'],
        }

    def save_yodeck_data(self, filename: str = "yodeck_display.json"):
        """Save formatted data for Yodeck."""
        data = self.generate_yodeck_data()
        output_path = self.data_dir / filename
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Yodeck data saved to {output_path}")
        return data

# Example usage
if __name__ == "__main__":
    processor = AAHLDataProcessor()
    data = processor.save_yodeck_data()
    print("Generated Yodeck display data:")
    print(json.dumps(data, indent=2)[:500] + "...")

