"""
Data model definitions used by the AAHL scraper.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return dt.isoformat()


@dataclass(slots=True)
class GameTeamLine:
    """
    Representation of a single team's line within a game result.
    """

    name: str
    slug: str
    final: Optional[int] = None
    periods: List[Optional[int]] = field(default_factory=list)
    is_winner: Optional[bool] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "slug": self.slug,
            "final": self.final,
            "periods": self.periods,
            "is_winner": self.is_winner,
        }


@dataclass(slots=True)
class GameRecord:
    """
    Canonical representation of a single scheduled or completed game.
    """

    game_id: str
    start_utc: Optional[datetime]
    start_local: Optional[datetime]
    location: str
    status: str  # scheduled | final | postponed | unknown
    home: GameTeamLine
    away: GameTeamLine
    division: Optional[str] = None
    box_score_url: Optional[str] = None
    summary_url: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "game_id": self.game_id,
            "status": self.status,
            "location": self.location,
            "division": self.division,
            "start_utc": _iso(self.start_utc),
            "start_local": _iso(self.start_local),
            "home": self.home.to_dict(),
            "away": self.away.to_dict(),
            "box_score_url": self.box_score_url,
            "summary_url": self.summary_url,
        }


@dataclass(slots=True)
class ScoreBoardEntry:
    """
    Representation of a parsed scoreboard entry used for merging against games.
    """

    game_id: str
    location: str
    division: Optional[str]
    start_local: Optional[datetime]
    teams: List[GameTeamLine]
    box_score_url: Optional[str]
    summary_url: Optional[str]


@dataclass(slots=True)
class RosterPlayer:
    """
    Representation of a player on a roster.
    """

    number: Optional[str]
    name: str
    positions: List[str]
    height: Optional[str] = None
    weight: Optional[str] = None
    shoots: Optional[str] = None
    catches: Optional[str] = None
    hometown: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "number": self.number,
            "name": self.name,
            "positions": self.positions,
            "height": self.height,
            "weight": self.weight,
            "shoots": self.shoots,
            "catches": self.catches,
            "hometown": self.hometown,
        }


@dataclass(slots=True)
class TeamRoster:
    """
    Representation of a team's roster.
    """

    team_id: str
    team_name: str
    team_slug: str
    players: List[RosterPlayer]

    def to_dict(self) -> Dict[str, object]:
        return {
            "team_id": self.team_id,
            "team_name": self.team_name,
            "team_slug": self.team_slug,
            "players": [player.to_dict() for player in self.players],
        }
