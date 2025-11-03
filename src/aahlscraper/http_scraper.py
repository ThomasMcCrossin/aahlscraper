```python
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
        """Scrape schedule while propagating date headers down to each game row.

        The AAHL site groups games under a date header (e.g., "Sunday, November 2, 2025").
        We walk the DOM in order, track the last seen date-looking header, and stamp it
        into each subsequent game row. When possible, we also compute an ISO "datetime"
        from the header date + row time for easier downstream sorting.
        """
        soup = self._fetch_soup("schedule", format=format_type, d=date_filter)
        if soup is None:
            return []

        def looks_like_date(text: str) -> bool:
            text = (text or "").strip()
            try:
                # Example: "Sunday, November 2, 2025"
                datetime.strptime(text, "%A, %B %d, %Y")
                return True
            except Exception:
                return False

        def parse_time_to_iso(date_str: str, time_str: str) -> Optional[str]:
            if not date_str or not time_str:
                return None
            try:
                base = datetime.strptime(date_str.strip(), "%A, %B %d, %Y").date()
            except Exception:
                return None
            t_raw = time_str.strip().upper().replace(".", "")
            for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
                try:
                    t = datetime.strptime(t_raw, fmt).time()
                    return datetime.combine(base, t).isoformat()
                except ValueError:
                    continue
            return None

        games: List[Dict[str, str]] = []
        current_date_header = ""

        # Consider headings/strong/divs and rows, in document order
        for el in soup.find_all(["h1", "h2", "h3", "h4", "div", "strong", "tr"], recursive=True):
            text = el.get_text(" ", strip=True)

            # Update current header-date when encountered anywhere above the table rows
            if looks_like_date(text):
                current_date_header = text
                continue

            # Skip week-range headers like "Mon, 10/27/25 to Sun, 11/2/25  Week 3"
            if (el.name != "tr") and ("Week" in text):
                continue

            # Treat table rows as potential games
            if el.name == "tr":
                tds = el.find_all("td")
                if not tds:
                    continue
                cells = [td.get_text(strip=True) for td in tds]

                # Ignore divider/single-cell date/week rows inside tables
                if len(cells) == 1 and (looks_like_date(cells[0]) or "Week" in cells[0]):
                    continue

                # Heuristic mapping (robust to minor layout shifts)
                time_candidate = cells[0] if len(cells) >= 1 else ""
                location_candidate = cells[1] if len(cells) >= 2 else ""

                away = ""
                home = ""
                away_score = ""
                home_score = ""

                if len(cells) >= 5:
                    # Typical: [time, rink, away, away_score?, 'vs'?, home, home_score?]
                    away = cells[2]
                    if len(cells) >= 4 and cells[3].isdigit():
                        away_score = cells[3]
                    # If last cell looks numeric, treat it as home_score, with name preceding
                    if cells[-1].isdigit():
                        home_score = cells[-1]
                        home = cells[-2] if len(cells) >= 2 else ""
                    else:
                        home = cells[-1]

                # Box score link, if present in the row
                box = None
                a = el.find("a", string=lambda s: s and "Box" in s)
                if a and a.get("href"):
                    box = a["href"].strip()

                game: Dict[str, str] = {
                    "date": current_date_header,  # carry down header date text
                    "time": time_candidate,
                    "location": location_candidate,
                    "away": away,
                    "away_score": away_score,
                    "home": home,
                    "home_score": home_score,
                    "box_score_url": box or "",
                }

                iso_dt = parse_time_to_iso(current_date_header, time_candidate)
                if iso_dt:
                    game["datetime"] = iso_dt

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
            # Prefer explicit ISO datetime if present
            dt_txt = game.get("datetime")
            parsed = None
            if dt_txt:
                try:
                    parsed = datetime.fromisoformat(dt_txt)
                except Exception:
                    parsed = None
            if parsed is None:
                parsed = parse_game_date(game.get("date", ""))

            if parsed is None:
                recent.append(game)
                continue

            if parsed >= cutoff:
                recent.append(game)

        return recent
```
