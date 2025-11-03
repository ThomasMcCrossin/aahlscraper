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
from typing import Dict, List, Any

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
        """Filter schedule for Amherst games, split into past and future."""
        today = datetime.now().date()
        past_10_days = []
        next_10_days = []

        for game in schedule:
            try:
                # Try to parse date - handle various formats
                game_date_str = game.get('date', game.get('Date', ''))
                if not game_date_str:
                    continue

                # Try parsing as YYYY-MM-DD
                try:
                    game_date = datetime.strptime(game_date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        game_date = datetime.strptime(game_date_str, '%m/%d/%Y').date()
                    except ValueError:
                        continue

                # Check if game involves Amherst
                home = game.get('home_team', game.get('Home Team', '')).lower()
                away = game.get('away_team', game.get('Away Team', '')).lower()
                location = game.get('location', game.get('Location', '')).lower()

                is_amherst = 'amherst' in home or 'amherst' in away or 'amherst' in location

                if is_amherst:
                    # Add corrected names
                    game_copy = game.copy()
                    if 'home_team' in game_copy:
                        game_copy['home_team'] = self.correct_names(game_copy['home_team'])
                    if 'Home Team' in game_copy:
                        game_copy['Home Team'] = self.correct_names(game_copy['Home Team'])
                    if 'away_team' in game_copy:
                        game_copy['away_team'] = self.correct_names(game_copy['away_team'])
                    if 'Away Team' in game_copy:
                        game_copy['Away Team'] = self.correct_names(game_copy['Away Team'])

                    if today - timedelta(days=10) <= game_date <= today:
                        past_10_days.append(game_copy)
                    elif today < game_date <= today + timedelta(days=10):
                        next_10_days.append(game_copy)
            except Exception as e:
                print(f"Error processing game: {e}")
                continue

        return {
            'recent_results': sorted(past_10_days, key=lambda x: x.get('date', x.get('Date', '')), reverse=True)[:10],
            'upcoming_games': sorted(next_10_days, key=lambda x: x.get('date', x.get('Date', '')))[:10]
        }

    def get_top_scorers(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get top scorers with corrections applied."""
        stats = self.load_stats()

        # Try to sort by points/goals+assists
        try:
            for stat in stats:
                if 'points' not in stat:
                    goals = int(stat.get('goals', stat.get('Goals', 0)))
                    assists = int(stat.get('assists', stat.get('Assists', 0)))
                    stat['points'] = goals + assists
                else:
                    stat['points'] = int(stat['points'])
        except (ValueError, TypeError):
            pass

        # Sort and limit
        sorted_stats = sorted(stats, key=lambda x: x.get('points', 0), reverse=True)[:limit]

        # Add rank and apply name corrections
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
            formatted_standings.append({
                'team': self.correct_names(team.get('team', team.get('Team', ''))),
                'wins': int(team.get('wins', team.get('Wins', 0))),
                'losses': int(team.get('losses', team.get('Losses', 0))),
                'points': int(team.get('points', team.get('Points', 0))),
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

    # Generate and save Yodeck data
    data = processor.save_yodeck_data()
    print("Generated Yodeck display data:")
    print(json.dumps(data, indent=2)[:500] + "...")
