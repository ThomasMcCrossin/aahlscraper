"""
Playwright-based scraper for handling JavaScript-rendered AAHL pages.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from playwright.sync_api import sync_playwright

from .common import build_url, normalize_header
from .http_scraper import AmherstHockeyScraper
from .utils import player_name_variants, slugify

EXTRACT_ROWS_SCRIPT = """
() => {
  const table = document.querySelector('table');
  if (!table) {
    return [];
  }

  const rows = Array.from(table.querySelectorAll('tr'));
  return rows.map(row => {
    const cells = Array.from(row.querySelectorAll('td, th'));
    return cells.map(cell => cell.textContent.trim());
  }).filter(row => row.length > 0);
}
"""


class AmherstHockeyPlaywrightScraper:
    """
    Playwright scraper. Use when the static HTTP scraper cannot see the data.
    """

    def __init__(
        self,
        team_id: str = "DSMALL",
        headless: bool = True,
        browser: str = "chromium",
        timeout_ms: int = 10_000,
    ) -> None:
        self.team_id = team_id
        self.headless = headless
        self.browser = browser
        self.timeout_ms = timeout_ms
        self._player_lookup: Optional[Dict[Tuple[str, str], Dict[str, Optional[str]]]] = None

    def _collect_rows(self, page_type: str, **params: str) -> List[List[str]]:
        url = build_url(self.team_id, page_type, **params)

        with sync_playwright() as playwright:
            browser_factory = getattr(playwright, self.browser, None)
            if browser_factory is None:
                raise ValueError(f"Unsupported browser type: {self.browser}")

            browser = browser_factory.launch(headless=self.headless)
            page = browser.new_page()

            try:
                page.goto(url, wait_until="networkidle")
                page.wait_for_selector("table", timeout=self.timeout_ms)
                return page.evaluate(EXTRACT_ROWS_SCRIPT)
            except Exception as exc:
                print(f"Error scraping {page_type} with Playwright: {exc}")
                return []
            finally:
                browser.close()

    def _ensure_player_lookup(self) -> Dict[Tuple[str, str], Dict[str, Optional[str]]]:
        if self._player_lookup is not None:
            return self._player_lookup

        helper = AmherstHockeyScraper(team_id=self.team_id)
        rosters = helper.scrape_rosters()
        lookup: Dict[Tuple[str, str], Dict[str, Optional[str]]] = {}

        for roster in rosters.values():
            team_slug = roster.get("team_slug")
            if not team_slug:
                continue
            team_payload = {
                "team_id": roster.get("team_id"),
                "team_name": roster.get("team_name"),
            }
            for player in roster.get("players", []):
                payload = {
                    "player_id": player.get("player_id"),
                    "number": player.get("number"),
                    **team_payload,
                }
                for key in player_name_variants(player.get("name", "")):
                    if not key:
                        continue
                    lookup.setdefault((team_slug, key), payload)

        self._player_lookup = lookup
        return lookup

    def scrape_schedule(self, format_type: str = "List", date_filter: str = "ALL") -> List[Dict[str, str]]:
        rows = self._collect_rows("schedule", format=format_type, d=date_filter)
        if not rows:
            return []

        data_rows = rows[1:] if len(rows) > 1 else rows
        games: List[Dict[str, str]] = []
        for cells in data_rows:
            if len(cells) < 1:
                continue

            padded = cells + [""] * max(0, 6 - len(cells))
            game = {
                "date": padded[0],
                "time": padded[1] if len(padded) > 1 else "",
                "opponent": padded[2] if len(padded) > 2 else "",
                "location": padded[3] if len(padded) > 3 else "",
                "result": padded[4] if len(padded) > 4 else "",
                "score": padded[5] if len(padded) > 5 else "",
            }
            games.append(game)

        return games

    def scrape_stats(self, sort_by: str = "points") -> List[Dict[str, str]]:
        rows = self._collect_rows("stats", psort=sort_by)
        if not rows:
            return []

        headers = [normalize_header(cell) for cell in rows[0]]
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

        lookup = self._ensure_player_lookup()
        for player in players:
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
            player["player_id"] = player_id
            player["team_slug"] = team_slug or None

        return players

    def scrape_standings(self) -> List[Dict[str, str]]:
        rows = self._collect_rows("standings")
        if not rows:
            return []

        headers = [normalize_header(cell) for cell in rows[0]]
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
