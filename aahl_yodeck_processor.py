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

    def load_results(self) -> List[Dict[str, Any]]:
        """Load final results from JSON if available."""
        results_json = self.data_dir / "results.json"
        if results_json.exists():
            with open(results_json, "r", encoding="utf-8") as handle:
                return json.load(handle)
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

    def load_headlines(self) -> Dict[str, Any]:
        """Load curated headlines keyed by game."""
        path = self.data_dir / "headlines.json"
        if not path.exists():
            return {"headlines": []}
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict):
            data.setdefault("headlines", [])
            return data
        # Legacy list format
        return {"headlines": []}

    def load_player_registry(self) -> Dict[str, Any]:
        """Load aggregated player registry with IDs and metrics."""
        path = self.data_dir / "player_registry.json"
        if not path.exists():
            return {"players": []}
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, dict) and "players" in data:
            return data
        if isinstance(data, list):
            return {"players": data}
        return {"players": []}

    def _game_identifier(self, game: Dict[str, Any]) -> str:
        """Create a stable identifier for a game combining id, participants, and date."""
        game_id = str(game.get("game_id") or game.get("id") or "").strip()
        if game_id:
            return f"id:{game_id}"

        def _clean(value: Any) -> str:
            if value is None:
                return ""
            return self.correct_names(str(value).strip())

        home = _clean(game.get("home") or game.get("home_team"))
        away = _clean(game.get("away") or game.get("away_team"))
        home_score = str(game.get("home_score") or "").strip()
        away_score = str(game.get("away_score") or "").strip()
        date_parts = [
            game.get("datetime"),
            game.get("start_local"),
            game.get("start_utc"),
            game.get("date"),
        ]
        when = ""
        for part in date_parts:
            if part:
                when = str(part).strip()
                if when:
                    break
        return f"fallback:{home}|{away}|{when}|{home_score}|{away_score}"

    @staticmethod
    def _merge_game_records(base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """Shallow merge game dictionaries keeping meaningful data from both."""
        merged = dict(base)
        for key, value in update.items():
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, (list, dict)) and not value:
                continue
            merged[key] = value
        return merged

    @staticmethod
    def _points_from_stat(stat: Dict[str, Any]) -> int:
        try:
            if "points" in stat and stat["points"] not in ("", None):
                return int(stat["points"])
            goals = int(stat.get("goals") or stat.get("g") or 0)
            assists = int(stat.get("assists") or stat.get("a") or 0)
            return goals + assists
        except (TypeError, ValueError):
            return 0

    def refine_headline_text(self, text: Optional[str]) -> Optional[str]:
        """Tweak templated headline language to read more naturally."""
        if not text or not isinstance(text, str):
            return text

        replacements = [
            (r"\bbrace\s*\(2G\)", "two goals"),
            (r"\bsupplying\b", "adding"),
            (r"\bchipping in\b", "adding"),
            (r"\bpummels\b", "dominates"),
            (r"\bcrushes\b", "rolls past"),
        ]

        refined = text
        for pattern, replacement in replacements:
            refined = re.sub(pattern, replacement, refined, flags=re.IGNORECASE)

        refined = re.sub(r"\s{2,}", " ", refined).strip()
        return refined

    def _clean_player_stats(self, game: Dict[str, Any]) -> Dict[str, Any]:
        """Apply name corrections and ensure numeric totals for per-game player stats."""
        stats = game.get("player_stats")
        if not isinstance(stats, dict):
            return game

        cleaned: Dict[str, Any] = {}
        for side in ("home", "away"):
            entries = stats.get(side)
            if not isinstance(entries, list):
                continue

            cleaned_entries = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_copy = dict(entry)
                name = entry_copy.get("name") or entry_copy.get("player_name")
                if name:
                    entry_copy["name"] = self.correct_names(name)
                goals = entry_copy.get("goals", entry_copy.get("g", 0))
                assists = entry_copy.get("assists", entry_copy.get("a", 0))
                try:
                    entry_copy["goals"] = int(goals or 0)
                except (TypeError, ValueError):
                    entry_copy["goals"] = 0
                try:
                    entry_copy["assists"] = int(assists or 0)
                except (TypeError, ValueError):
                    entry_copy["assists"] = 0
                entry_copy["points"] = self._points_from_stat(entry_copy)
                cleaned_entries.append(entry_copy)
            cleaned[side] = cleaned_entries

        if cleaned:
            game["player_stats"] = cleaned
        return game

    def filter_amherst_games(self, schedule: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Filter schedule for Amherst games, split into completed and upcoming.

        Uses per-game ISO "datetime" when available; otherwise falls back to date header
        parsing and/or presence of a numeric score.
        """
        now = datetime.now()

        def has_score(g: Dict[str, Any]) -> bool:
            def _to_int(val: Any) -> Optional[int]:
                if isinstance(val, (int, float)):
                    return int(val)
                if isinstance(val, str) and val.strip().isdigit():
                    return int(val.strip())
                return None

            home_score = _to_int(g.get("home_score"))
            away_score = _to_int(g.get("away_score"))
            if home_score is not None and away_score is not None:
                return True

            result_text = g.get("result") or g.get("score")
            if isinstance(result_text, str):
                parts = [segment.strip() for segment in result_text.split("-")]
                if len(parts) == 2 and all(part.isdigit() for part in parts):
                    return True

            for side_key in ("home_line", "away_line"):
                side = g.get(side_key)
                if isinstance(side, dict) and side.get("final") is not None:
                    return True

            return False

        def to_dt(g: Dict[str, Any]) -> Optional[datetime]:
            # Prefer explicit ISO datetime
            for key in ("start_local", "start_utc", "datetime"):
                value = g.get(key)
                if not value:
                    continue
                try:
                    dt_val = datetime.fromisoformat(str(value))
                    if dt_val.tzinfo is not None:
                        return dt_val.astimezone().replace(tzinfo=None)
                    return dt_val
                except Exception:
                    continue

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
                for fmt in ("%A, %B %d, %Y", "%b %d, %Y"):
                    try:
                        return datetime.strptime(date_txt, fmt)
                    except Exception:
                        continue
            return None

        amherst_recent: List[Dict[str, Any]] = []
        amherst_upcoming: List[Dict[str, Any]] = []

        for game in schedule:
            try:
                location = (game.get("location", game.get("Location", "")) or "").lower()
                if "amherst" not in location:
                    continue

                # Normalize home/away dictionaries for both legacy and new scraper output
                game_copy: Dict[str, Any] = dict(game)
                for side in ("home", "away"):
                    side_value = game.get(side)
                    if isinstance(side_value, dict):
                        game_copy[side] = side_value.get("name")
                        if side_value.get("final") is not None:
                            game_copy[f"{side}_score"] = side_value["final"]
                        if side_value.get("periods") is not None:
                            game_copy[f"{side}_periods"] = side_value["periods"]
                    elif isinstance(side_value, str):
                        game_copy[side] = side_value

                # Name corrections
                for side in ("home", "away"):
                    if side in game_copy and isinstance(game_copy[side], str):
                        game_copy[side] = self.correct_names(game_copy[side])

                game_copy = self._clean_player_stats(game_copy)

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

        recent_sorted = sorted(amherst_recent, key=sort_key, reverse=True)
        upcoming_sorted = sorted(amherst_upcoming, key=sort_key)

        def dedupe(games_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            unique: List[Dict[str, Any]] = []
            seen_keys = set()
            seen_composite = set()
            for entry in games_list:
                key = self._game_identifier(entry)
                home = self.correct_names(str(entry.get("home") or entry.get("home_team") or ""))
                away = self.correct_names(str(entry.get("away") or entry.get("away_team") or ""))
                home_score = str(entry.get("home_score") or "").strip()
                away_score = str(entry.get("away_score") or "").strip()
                when = ""
                for part in (entry.get("datetime"), entry.get("start_local"), entry.get("start_utc"), entry.get("date")):
                    if part:
                        when = str(part).strip()
                        if when:
                            break
                composite = (home.lower(), away.lower(), when, home_score, away_score)

                if key and key in seen_keys:
                    continue
                if composite in seen_composite:
                    continue

                if key:
                    seen_keys.add(key)
                seen_composite.add(composite)
                unique.append(entry)
            return unique

        recent_sorted = dedupe(recent_sorted)[:10]
        recent_keys = {self._game_identifier(game) for game in recent_sorted}

        def remove_seen(games_list: List[Dict[str, Any]], seen: set) -> List[Dict[str, Any]]:
            filtered: List[Dict[str, Any]] = []
            for entry in games_list:
                key = self._game_identifier(entry)
                home = self.correct_names(str(entry.get("home") or entry.get("home_team") or ""))
                away = self.correct_names(str(entry.get("away") or entry.get("away_team") or ""))
                when = ""
                for part in (entry.get("datetime"), entry.get("start_local"), entry.get("start_utc"), entry.get("date")):
                    if part:
                        when = str(part).strip()
                        if when:
                            break
                score_combo = (home.lower(), away.lower(), when)

                if (key and key in seen) or score_combo in seen:
                    continue
                filtered.append(entry)
            return filtered

        upcoming_seen = set(recent_keys)
        upcoming_seen.update(
            (self.correct_names(str(game.get("home") or game.get("home_team") or "")).lower(),
             self.correct_names(str(game.get("away") or game.get("away_team") or "")).lower(),
             str(game.get("datetime") or game.get("start_local") or game.get("start_utc") or game.get("date") or "").strip())
            for game in recent_sorted
        )

        upcoming_sorted = remove_seen(dedupe(upcoming_sorted), upcoming_seen)[:10]

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
        results = self.load_results()
        headlines_blob = self.load_headlines()
        player_registry = self.load_player_registry()

        combined_by_id: Dict[str, Dict[str, Any]] = {}

        for source in (schedule, results):
            for game in source:
                key = self._game_identifier(game)
                if not key:
                    continue
                if key in combined_by_id:
                    combined_by_id[key] = self._merge_game_records(combined_by_id[key], game)
                else:
                    combined_by_id[key] = dict(game)

        games = self.filter_amherst_games(list(combined_by_id.values()))
        headline_lookup = {
            str(entry.get("game_id")): entry
            for entry in headlines_blob.get("headlines", [])
            if isinstance(entry, dict) and entry.get("game_id")
        }

        enriched_recent: List[Dict[str, Any]] = []
        for game in games['recent_results']:
            enriched = dict(game)
            game_id = str(game.get("game_id", ""))
            headline_entry = headline_lookup.get(game_id)
            if headline_entry:
                enriched_headline = headline_entry.get("headline")
                enriched["headline"] = self.refine_headline_text(enriched_headline)
                enriched["headline_updated_at"] = headline_entry.get("updated_at")
            elif enriched.get("headline"):
                enriched["headline"] = self.refine_headline_text(enriched.get("headline"))
            self._clean_player_stats(enriched)
            enriched_recent.append(enriched)

        enriched_upcoming = []
        for game in games['upcoming_games']:
            clone = dict(game)
            self._clean_player_stats(clone)
            enriched_upcoming.append(clone)

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
            'recent_results': enriched_recent,
            'upcoming_games': enriched_upcoming,
            'headlines': headlines_blob.get('headlines', []),
            'player_registry': player_registry,
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
