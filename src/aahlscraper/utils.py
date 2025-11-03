"""
Utility helpers for the AAHL scraper package.
"""

from __future__ import annotations

import re
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


_SLUG_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(raw: str) -> str:
    """
    Convert freeform text into a filesystem and URL friendly slug.
    """

    value = raw.strip().lower().replace("&", " and ").replace(".", "")
    value = _SLUG_NON_ALNUM.sub("-", value)
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("-")
    return value or "unnamed"
