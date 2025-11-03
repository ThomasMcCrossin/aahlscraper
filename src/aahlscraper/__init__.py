"""
AAHL scraper package.
"""

from .diagnostics import analyze_page, run_diagnostics, summarize_recommendation
from .http_scraper import AmherstHockeyScraper
from .playwright_scraper import AmherstHockeyPlaywrightScraper

__all__ = [
    "AmherstHockeyScraper",
    "AmherstHockeyPlaywrightScraper",
    "analyze_page",
    "run_diagnostics",
    "summarize_recommendation",
]
