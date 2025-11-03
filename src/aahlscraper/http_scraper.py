"""
HTTP-based scraper implementation for the Amherst Adult Hockey League site.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .common import build_url, find_best_table, normalize_header
from .models import GameRecord
from .parsers import (
    CALENDAR_URL,
    merge_games_with_scores,
    parse_ics_games,
    parse_rosters,
    parse_scoreboard,
)

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

        players: List[Dict[str, str]] = []
        for cells in data_rows:
            if len(cells) < 2:
                continue

            if headers and len(headers) == len(cells):
                player = {headers[i]: cells[i] for i in range(len(cells))}
            else:
                player = {f"col_{i}": cell for i, cell in enumerate(cells)}
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
            standings.append(team)

        return standings

    def scrape_results(self) -> List[Dict[str, object]]:
        """
        Return completed Amherst games (with box score details when available).
        """

        games = self._load_games()
        results: List[Dict[str, object]] = []
        for game in games:
            if game.status == "final":
                results.append(game.to_dict())
        return results

    def scrape_rosters(self) -> Dict[str, Dict[str, object]]:
        """
        Parse and return team rosters keyed by team slug.
        """

        html = self._fetch_roster_page()
        if not html:
            return {}

        rosters = parse_rosters(html)
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
