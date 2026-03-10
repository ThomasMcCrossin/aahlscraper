"""
Halifax-local time helpers for AAHL game data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping, Optional
from zoneinfo import ZoneInfo


HALIFAX_TZ = ZoneInfo("America/Halifax")


def ensure_datetime(value: object, *, naive_tz: ZoneInfo = HALIFAX_TZ) -> Optional[datetime]:
    """
    Parse an ISO-like value into a timezone-aware datetime.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value))
        except ValueError:
            return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=naive_tz)
    return dt


def to_halifax(value: object) -> Optional[datetime]:
    """
    Convert a datetime-like value to Halifax local time.
    """

    dt = ensure_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(HALIFAX_TZ)


def to_utc(value: object) -> Optional[datetime]:
    """
    Convert a datetime-like value to UTC.
    """

    dt = ensure_datetime(value)
    if dt is None:
        return None
    return dt.astimezone(timezone.utc)


def halifax_now() -> datetime:
    """
    Return the current Halifax-local time.
    """

    return datetime.now(timezone.utc).astimezone(HALIFAX_TZ)


def local_date_key(value: object) -> Optional[str]:
    """
    Return the Halifax-local calendar date key for a datetime-like value.
    """

    dt = to_halifax(value)
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d")


def mapping_game_local_start(game: Mapping[str, object]) -> Optional[datetime]:
    """
    Return the best local start time available on a serialized game mapping.
    """

    for key in ("start_local", "datetime", "start_utc"):
        dt = to_halifax(game.get(key))
        if dt is not None:
            return dt
    return None


def mapping_game_utc_start(game: Mapping[str, object]) -> Optional[datetime]:
    """
    Return the best UTC start time available on a serialized game mapping.
    """

    for key in ("start_utc", "start_local", "datetime"):
        dt = to_utc(game.get(key))
        if dt is not None:
            return dt
    return None
