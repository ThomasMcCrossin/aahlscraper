"""
Utility helpers for the AAHL scraper package.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Iterable, List, Optional, Tuple

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
_PLAYER_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(raw: str) -> str:
    """
    Convert freeform text into a filesystem and URL friendly slug.
    """

    value = raw.strip().lower().replace("&", " and ").replace(".", "")
    value = _SLUG_NON_ALNUM.sub("-", value)
    value = re.sub(r"-{2,}", "-", value)
    value = value.strip("-")
    return value or "unnamed"


def normalize_player_key(name: str) -> str:
    """
    Produce a slug-like key for matching player names across data sources.
    """

    value = name.replace(",", " ").replace(".", " ").lower()
    value = re.sub(r"\s+", " ", value).strip()
    return _PLAYER_NON_ALNUM.sub("-", value)


def player_name_variants(name: str) -> List[str]:
    """
    Return normalized name variants (e.g. 'Last, First' and 'First Last').
    """

    cleaned = (name or "").strip()
    variants = {normalize_player_key(cleaned)}
    if "," in cleaned:
        last, first = [segment.strip() for segment in cleaned.split(",", 1)]
        variants.add(normalize_player_key(f"{first} {last}"))
    else:
        parts = cleaned.split()
        if len(parts) >= 2:
            first = " ".join(parts[:-1])
            last = parts[-1]
            variants.add(normalize_player_key(f"{last}, {first}"))
    return [variant for variant in variants if variant]


def derive_player_id(team_slug: str, name: str, number: Optional[str] = None) -> str:
    """
    Generate a stable player identifier scoped to a team.
    """

    base = slugify(name.replace(",", " "))
    number_fragment = ""
    if number:
        digits = re.sub(r"\D", "", number)
        if digits:
            number_fragment = f"-{digits}"
    return f"{team_slug}-{base or 'player'}{number_fragment}"
