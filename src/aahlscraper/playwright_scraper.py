"""
Playwright-based scraper for handling JavaScript-rendered AAHL pages.
"""

from __future__ import annotations

from typing import Dict, List

from playwright.sync_api import sync_playwright

from .common import build_url, normalize_header

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
