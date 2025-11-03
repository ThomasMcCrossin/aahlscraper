"""
HTTP-based scraper implementation for the Amherst Adult Hockey League site.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .common import build_url, find_best_table, normalize_header
from .utils import parse_game_date

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

    def _fetch_soup(self, page_type: str, **params: str) -> Optional[BeautifulSoup]:
        url = build_url(self.team_id, page_type, **params)
        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            print(f"Error requesting {page_type}: {exc}")
            return None
        return BeautifulSoup(response.text, "html.parser")

    def scrape_schedule(self, format_type: str = "List", date_filter: str = "ALL") -> List[Dict[str, str]]:
        soup = self._fetch_soup("schedule", format=format_type, d=date_filter)
        if soup is None:
            return []

        table = find_best_table(soup, TABLE_CLASS_CANDIDATES)
        if table is None:
            print("No schedule table found")
            return []

        rows = _extract_rows(table)
        if not rows:
            return []

        # Parse headers like the stats scraper does
        headers: List[str] = [normalize_header(cell) for cell in rows[0]]
        data_rows = rows[1:] if len(rows) > 1 else rows

        games: List[Dict[str, str]] = []
        current_date = ""  # Track the current date from header rows

        for cells in data_rows:
            if len(cells) < 2:
                continue

            # Check if this is a date header row (single cell with a date like "Tuesday, October 28, 2025")
            if len(cells) == 1 and any(month in cells[0] for month in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']):
                current_date = cells[0]
                continue  # Skip to next row

            # Check if this is a week header (like "Mon, 10/27/25 to Sun, 11/2/25  Week 3")
            if len(cells) == 1 and 'Week' in cells[0]:
                continue  # Skip week headers

            # Use headers if available, otherwise use generic column names
            if headers and len(headers) == len(cells):
                game = {headers[i]: cells[i] for i in range(len(cells))}
            else:
                # Fallback to assumed structure
                padded = cells + [""] * max(0, 6 - len(cells))
                game = {
                    "time": padded[0],
                    "away": padded[1] if len(padded) > 1 else "",
                    "away_score": padded[2] if len(padded) > 2 else "",
                    "vs": padded[3] if len(padded) > 3 else "",
                    "home": padded[4] if len(padded) > 4 else "",
                    "home_score": padded[5] if len(padded) > 5 else "",
                    "location": padded[6] if len(padded) > 6 else "",
                }

            # Add the current date to the game
            game['date'] = current_date
            games.append(game)

        return games

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

    def get_recent_games(self, weeks: int = 1) -> List[Dict[str, str]]:
        games = self.scrape_schedule()
        if not games:
            return []

        cutoff = datetime.now() - timedelta(weeks=weeks)

        recent: List[Dict[str, str]] = []
        for game in games:
            parsed = parse_game_date(game.get("date", ""))
            if parsed is None:
                recent.append(game)
                continue

            if parsed >= cutoff:
                recent.append(game)

        return recent
