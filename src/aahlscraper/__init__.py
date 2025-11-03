"""
AAHL scraper package.
"""

from .diagnostics import analyze_page, run_diagnostics, summarize_recommendation
from .http_scraper import AmherstHockeyScraper

# Playwright is optional - only import if available
try:
    from .playwright_scraper import AmherstHockeyPlaywrightScraper
    _HAS_PLAYWRIGHT = True
except ImportError:
    AmherstHockeyPlaywrightScraper = None
    _HAS_PLAYWRIGHT = False

__all__ = [
    "AmherstHockeyScraper",
    "AmherstHockeyPlaywrightScraper",
    "analyze_page",
    "run_diagnostics",
    "summarize_recommendation",
]
