"""
HTTP-based scraper implementation for the Amherst Adult Hockey League site.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .common import build_url, find_best_table, normalize_header
from .models import GameRecord, TeamRoster
from .parsers import (
    CALENDAR_URL,
    merge_games_with_scores,
    parse_ics_games,
    parse_rosters,
    parse_scoreboard,
    parse_box_score,
)
from .utils import derive_player_id, player_name_variants, slugify

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

TABLE_CLASS_CANDIDATES = ("table", "schedule-table", "data-table", "stats-table", "standings-table")


def _extract_rows(table: Tag) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        rows.append([cell.get_text(strip=True) for cell in cells])
    return rows



def _parse_record_numbers(record: Optional[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    if not record or "-" not in record:
        return None, None, None

    tokens = [segment.strip() for segment in record.split("-")]
    wins = losses = ties = None

    def _to_int(value: str) -> Optional[int]:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    if tokens:
        wins = _to_int(tokens[0])
    if len(tokens) >= 2:
        losses = _to_int(tokens[1])
    if len(tokens) >= 3:
        ties = _to_int(tokens[2])

    return wins, losses, ties


class AmherstHockeyScraper:
    """
    Requests + BeautifulSoup scraper for AAHL team pages.
    """

    def __init__(
        self,
        team_id: str = "DSMALL",
        session: Optional[requests.Session] = None,
        timeout: int = 10,
    ) -> None:
        self.team_id = team_id
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update(DEFAULT_HEADERS)
        self._game_cache: Optional[List[GameRecord]] = None
        self._roster_cache: Optional[Dict[str, TeamRoster]] = None
        self._player_lookup: Optional[Dict[Tuple[str, str], Dict[str, object]]] = None

    def _fetch_soup(self, page_type: str, **params: str) -> Optional[BeautifulSoup]:
        url = build_url(self.team_id, page_type, **params)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Error requesting {page_type}: {exc}")
            return None
        return BeautifulSoup(response.text, "html.parser")

    def _fetch_text(self, url: str, *, params: Optional[Dict[str, str]] = None) -> Optional[str]:
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Error requesting {url}: {exc}")
            return None
        return response.text

    def _fetch_calendar(self) -> Optional[str]:
        url = CALENDAR_URL.format(team_id=self.team_id)
        return self._fetch_text(url)

    def _fetch_scores_page(self) -> Optional[str]:
        return self._fetch_text(build_url(self.team_id, "scores"))

    def _fetch_roster_page(self) -> Optional[str]:
        return self._fetch_text(build_url(self.team_id, "roster"), params={"expandAll": "1"})

    def _load_rosters(self) -> Dict[str, TeamRoster]:
        if self._roster_cache is not None:
            return self._roster_cache

        html = self._fetch_roster_page()
        if not html:
            self._roster_cache = {}
            return {}

        self._roster_cache = parse_rosters(html)
        return self._roster_cache

    def _build_player_lookup(self) -> Dict[Tuple[str, str], Dict[str, object]]:
        if self._player_lookup is not None:
            return self._player_lookup

        rosters = self._load_rosters()
        lookup: Dict[Tuple[str, str], Dict[str, Optional[str]]] = {}

        for team_slug, roster in rosters.items():
            for player in roster.players:
                payload = {
                    "player_id": player.player_id,
                    "number": player.number,
                    "team_id": roster.team_id,
                    "team_name": roster.team_name,
                    "positions": player.positions,
                }
                for key in player_name_variants(player.name):
                    lookup.setdefault((team_slug, key), payload)

        self._player_lookup = lookup
        return lookup

    def _load_games(self) -> List[GameRecord]:
        if self._game_cache is not None:
            return list(self._game_cache)

        calendar_text = self._fetch_calendar()
        if not calendar_text:
            self._game_cache = []
            return []

        games = parse_ics_games(calendar_text, location_filter="Amherst")

        scores_html = self._fetch_scores_page()
        if scores_html:
            scoreboard_entries = [
                entry for entry in parse_scoreboard(scores_html) if "amherst" in (entry.location or "").lower()
            ]
            games = merge_games_with_scores(games, scoreboard_entries)

        games.sort(
            key=lambda g: (
                g.start_local
                or g.start_utc
                or datetime.max.replace(tzinfo=timezone.utc)  # type: ignore[arg-type]
            )
        )
        self._game_cache = games
        return list(self._game_cache)

    def scrape_schedule(self) -> List[Dict[str, object]]:
        """
        Return upcoming Amherst games as dictionaries.
        """

        games = self._load_games()
        if not games:
            return []

        now = datetime.now(timezone.utc)
        upcoming: List[Dict[str, object]] = []
        for game in games:
            if game.status == "final":
                continue
            starts = game.start_utc or game.start_local
            if starts and starts < now:
                continue
            upcoming.append(game.to_dict())
        return upcoming

    def scrape_stats(self, sort_by: str = "points") -> List[Dict[str, str]]:
        soup = self._fetch_soup("stats", psort=sort_by)
        if soup is None:
            return []

        table = find_best_table(soup, TABLE_CLASS_CANDIDATES)
        if table is None:
            print("No stats table found")
            return []

        rows = _extract_rows(table)
        if not rows:
            return []

        headers: List[str] = [normalize_header(cell) for cell in rows[0]]
        data_rows = rows[1:] if len(rows) > 1 else rows

        lookup = self._build_player_lookup()

        players: List[Dict[str, str]] = []
        for cells in data_rows:
            if len(cells) < 2:
                continue

            if headers and len(headers) == len(cells):
                player = {headers[i]: cells[i] for i in range(len(cells))}
            else:
                player = {f"col_{i}": cell for i, cell in enumerate(cells)}

            name_field = (
                player.get("name")
                or player.get("player")
                or player.get("player_name")
                or player.get("playername")
                or ""
            )
            team_field = player.get("team") or player.get("Team") or ""

            team_slug = slugify(team_field) if team_field else ""
            player_id: Optional[str] = None
            if team_slug and lookup:
                for key in player_name_variants(name_field):
                    match = lookup.get((team_slug, key))
                    if match:
                        player_id = match["player_id"]
                        if match.get("number") and not player.get("no"):
                            player.setdefault("no", match.get("number"))
                        player.setdefault("team_id", match.get("team_id"))
                        player.setdefault("team_name", match.get("team_name") or team_field)
                        break

            if player_id:
                player["player_id"] = player_id
            else:
                player["player_id"] = None
            player["team_slug"] = team_slug or None

            players.append(player)

        return players

    def scrape_standings(self) -> List[Dict[str, str]]:
        soup = self._fetch_soup("standings")
        if soup is None:
            return []

        table = find_best_table(soup, TABLE_CLASS_CANDIDATES)
        if table is None:
            print("No standings table found")
            return []

        rows = _extract_rows(table)
        if not rows:
            return []

        headers: List[str] = [normalize_header(cell) for cell in rows[0]]
        data_rows = rows[1:] if len(rows) > 1 else rows

        standings: List[Dict[str, str]] = []
        for cells in data_rows:
            if len(cells) < 2:
                continue

            if headers and len(headers) == len(cells):
                team = {headers[i]: cells[i] for i in range(len(cells))}
            else:
                team = {f"col_{i}": cell for i, cell in enumerate(cells)}

            record_text = str(team.get("record") or "")
            wins_record, losses_record, ties_record = _parse_record_numbers(record_text)

            def _coerce_numeric(field: str, fallback: Optional[int]) -> Optional[int]:
                value = team.get(field)
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    text = value.strip()
                    if text.isdigit():
                        return int(text)
                return fallback

            wins_val = _coerce_numeric("wins", wins_record)
            losses_val = _coerce_numeric("losses", losses_record)
            ties_val = _coerce_numeric("ties", ties_record if ties_record is not None else 0)

            if wins_val is not None:
                team["wins"] = wins_val
            if losses_val is not None:
                team["losses"] = losses_val
            if ties_val is not None:
                team["ties"] = ties_val

            standings.append(team)

        return standings

    def scrape_results(self) -> List[Dict[str, object]]:
        """
        Return completed Amherst games (with box score details when available).
        """

        games = self._load_games()
        lookup = self._build_player_lookup()
        results: List[Dict[str, object]] = []
        for game in games:
            if game.status != "final":
                continue

            record = game.to_dict()

            if game.box_score_url:
                box_html = self._fetch_text(game.box_score_url)
                if box_html:
                    box_score = parse_box_score(box_html)
                    player_stats = self._build_player_stats(game, box_score, lookup)
                    if player_stats:
                        record["player_stats"] = player_stats
                    if box_score.get("scoring_summary"):
                        record["scoring_summary"] = box_score["scoring_summary"]
                    if box_score.get("penalties"):
                        record["penalties"] = box_score["penalties"]
                    if box_score.get("scoreboard"):
                        record["scoreboard"] = box_score["scoreboard"]

            results.append(record)
        return results

    def _build_player_stats(
        self,
        game: GameRecord,
        box_score: Dict[str, object],
        lookup: Dict[Tuple[str, str], Dict[str, object]],
    ) -> Dict[str, List[Dict[str, object]]]:
        stats: Dict[str, List[Dict[str, object]]] = {}
        teams = box_score.get("teams") or []
        slug_map = {
            "home": game.home.slug,
            "away": game.away.slug,
        }
        used_sides: set[str] = set()

        for team_entry in teams:
            team_name = (team_entry.get("team_name") or "").strip()
            candidate_slug = slugify(team_name) if team_name else None
            side: Optional[str] = None

            for key, slug in slug_map.items():
                if key in used_sides:
                    continue
                if candidate_slug and candidate_slug == slug:
                    side = key
                    break

            if side is None:
                for key in ("home", "away"):
                    if key not in used_sides:
                        side = key
                        candidate_slug = slug_map[key]
                        break

            if side is None:
                continue

            used_sides.add(side)
            team_slug = slug_map.get(side)
            players_payload: List[Dict[str, object]] = []

            for raw_player in team_entry.get("players", []):
                name = (raw_player.get("name") or "").strip()
                if not name:
                    continue
                number = raw_player.get("number")
                match_payload: Optional[Dict[str, Optional[str]]] = None
                player_id: Optional[str] = None

                if team_slug:
                    for key in player_name_variants(name):
                        match_payload = lookup.get((team_slug, key))
                        if match_payload:
                            player_id = match_payload.get("player_id")
                            if not number and match_payload.get("number"):
                                number = match_payload.get("number")
                            break

                if not player_id and team_slug:
                    player_id = derive_player_id(team_slug, name, number)

                positions_raw = raw_player.get("positions") or ""
                if not positions_raw and match_payload and match_payload.get("positions"):
                    positions_raw = "/".join(match_payload["positions"])
                positions = [
                    token.strip()
                    for token in re.split(r"[\\/,-]+", positions_raw)
                    if token.strip()
                ]

                players_payload.append(
                    {
                        "player_id": player_id,
                        "name": name,
                        "number": number,
                        "positions": positions,
                        "goals": raw_player.get("goals", 0),
                        "assists": raw_player.get("assists", 0),
                        "points": raw_player.get("points", 0),
                        "penalty_minutes": raw_player.get("pim", 0),
                        "gtg": raw_player.get("gtg", 0),
                    }
                )

            stats[side] = players_payload

        return stats

    def scrape_rosters(self) -> Dict[str, Dict[str, object]]:
        """
        Parse and return team rosters keyed by team slug.
        """

        rosters = self._load_rosters()
        return {slug: roster.to_dict() for slug, roster in rosters.items()}

    def get_recent_games(self, weeks: int = 1) -> List[Dict[str, object]]:
        games = self._load_games()
        if not games:
            return []

        cutoff = datetime.now() - timedelta(weeks=weeks)

        recent: List[Dict[str, str]] = []
        for record in games:
            game = record.to_dict()
            start_iso = game.get("start_local") or game.get("start_utc")
            parsed = None
            if start_iso:
                try:
                    parsed = datetime.fromisoformat(str(start_iso))
                except Exception:
                    parsed = None

            if parsed is None:
                recent.append(game)  # Unable to parse means include by default
                continue

            if parsed >= cutoff:
                recent.append(game)

        return recent
