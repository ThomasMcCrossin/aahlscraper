"""
Utility helpers for the AAHL scraper package.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

DATE_FORMATS: Iterable[str] = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d", "%m/%d/%y")


def parse_game_date(raw: str) -> Optional[datetime]:
    """
    Attempt to parse a date string using the known set of formats.
    Returns None when parsing fails.
    """
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
