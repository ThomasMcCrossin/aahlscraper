"""
Common helpers shared across AAHL scraper modules.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional, Sequence
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from bs4.element import Tag


BASE_URL = "https://www.amherstadulthockey.com/teams"


def build_url(team_id: str, page_type: str, **params: str) -> str:
    """
    Build a fully qualified Amherst Adult Hockey League URL for a page type.
    """
    base_params = {"u": team_id, "s": "hockey", "p": page_type}
    base_params.update(params)
    return f"{BASE_URL}/default.asp?{urlencode(base_params)}"


def find_best_table(
    soup: BeautifulSoup, class_candidates: Optional[Sequence[str]] = None
) -> Optional[Tag]:
    """
    Find the most likely table containing the page data.
    Preference order:
    1. First match using explicit class candidates.
    2. Fallback to the table with the most rows.
    """
    if class_candidates:
        for candidate in class_candidates:
            table = soup.find("table", class_=candidate)
            if table:
                return table

    tables = soup.find_all("table")
    if not tables:
        return None

    return max(tables, key=lambda table: len(table.find_all("tr")))


def normalize_header(text: str) -> str:
    """
    Convert a header label into a normalized, snake_case key.
    """
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")
