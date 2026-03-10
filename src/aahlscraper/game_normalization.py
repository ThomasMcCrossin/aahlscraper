"""
Canonical game identity and dedupe helpers.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, MutableMapping
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from .game_time import HALIFAX_TZ, mapping_game_local_start, to_halifax
from .models import GameRecord, GameTeamLine
from .utils import slugify

CanonicalGameKey = Tuple[str, str, str, str]


def _location_key(value: object) -> str:
    return slugify(str(value or "unknown-location"))


def _start_key(dt: datetime | None) -> str:
    if dt is None:
        return "unknown-start"
    return dt.replace(second=0, microsecond=0).isoformat()


def _canonical_key(home_slug: str, away_slug: str, start_local: datetime | None, location: object) -> CanonicalGameKey:
    team_a, team_b = sorted(
        (
            slugify(home_slug or "unknown-home"),
            slugify(away_slug or "unknown-away"),
        )
    )
    return (team_a, team_b, _start_key(start_local), _location_key(location))


def canonical_game_key_for_record(game: GameRecord) -> CanonicalGameKey:
    start_local = game.start_local or to_halifax(game.start_utc)
    return _canonical_key(game.home.slug, game.away.slug, start_local, game.location)


def canonical_game_key_for_mapping(game: Mapping[str, object]) -> CanonicalGameKey:
    return _canonical_key(
        game_team_slug(game, "home"),
        game_team_slug(game, "away"),
        mapping_game_local_start(game),
        game.get("location"),
    )


def matchup_key_for_mapping(game: Mapping[str, object]) -> Tuple[str, str]:
    home_slug = game_team_slug(game, "home")
    away_slug = game_team_slug(game, "away")
    return tuple(sorted((home_slug, away_slug)))


def game_team_slug(game: Mapping[str, object], side: str) -> str:
    line = game.get(f"{side}_line")
    if isinstance(line, Mapping):
        slug = line.get("slug") or line.get("name")
        if slug:
            return slugify(str(slug))

    for key in (side, f"{side}_team"):
        value = game.get(key)
        if value:
            return slugify(str(value))

    return slugify(f"unknown-{side}")


def source_game_ids_for_mapping(game: Mapping[str, object]) -> List[str]:
    values = game.get("source_game_ids")
    if isinstance(values, list):
        cleaned = []
        for value in values:
            text = str(value or "").strip()
            if text and text not in cleaned:
                cleaned.append(text)
        if cleaned:
            return cleaned

    game_id = str(game.get("game_id") or "").strip()
    return [game_id] if game_id else []


def _count_period_values(line: GameTeamLine) -> int:
    return sum(1 for value in line.periods if value is not None)


def _record_quality(game: GameRecord) -> Tuple[int, int, int, int, int]:
    return (
        1 if game.start_utc is not None else 0,
        1 if game.box_score_url else 0,
        1 if game.summary_url else 0,
        1 if game.division else 0,
        _count_period_values(game.home) + _count_period_values(game.away),
    )


def _merge_team_line(target: GameTeamLine, candidate: GameTeamLine) -> None:
    if target.final is None and candidate.final is not None:
        target.final = candidate.final
    if not target.periods and candidate.periods:
        target.periods = list(candidate.periods)
    if target.is_winner is None and candidate.is_winner is not None:
        target.is_winner = candidate.is_winner


def _merge_game_record(target: GameRecord, candidate: GameRecord) -> None:
    if not target.start_local and candidate.start_local:
        target.start_local = candidate.start_local
    if not target.start_utc and candidate.start_utc:
        target.start_utc = candidate.start_utc
    if not target.location and candidate.location:
        target.location = candidate.location
    if not target.division and candidate.division:
        target.division = candidate.division

    if not target.box_score_url and candidate.box_score_url:
        target.box_score_url = candidate.box_score_url
    if not target.summary_url and candidate.summary_url:
        target.summary_url = candidate.summary_url

    candidate_ids = [value for value in candidate.source_game_ids if value]
    for value in candidate_ids:
        if value not in target.source_game_ids:
            target.source_game_ids.append(value)

    team_map = {
        target.home.slug: target.home,
        target.away.slug: target.away,
    }
    for line in (candidate.home, candidate.away):
        target_line = team_map.get(line.slug)
        if target_line is not None:
            _merge_team_line(target_line, line)

    if target.home.final is not None and target.away.final is not None:
        target.status = "final"


def dedupe_game_records(games: Sequence[GameRecord]) -> List[GameRecord]:
    grouped: Dict[CanonicalGameKey, List[GameRecord]] = defaultdict(list)
    for game in games:
        grouped[canonical_game_key_for_record(game)].append(game)

    deduped: List[GameRecord] = []
    for group in grouped.values():
        preferred = max(group, key=_record_quality)
        for candidate in group:
            if candidate is preferred:
                continue
            _merge_game_record(preferred, candidate)
        if not preferred.source_game_ids and preferred.game_id:
            preferred.source_game_ids = [preferred.game_id]
        deduped.append(preferred)

    deduped.sort(
        key=lambda game: game.start_local or to_halifax(game.start_utc) or datetime.max.replace(tzinfo=HALIFAX_TZ)
    )
    return deduped


def _mapping_stat_count(game: Mapping[str, object]) -> int:
    stats = game.get("player_stats")
    if not isinstance(stats, Mapping):
        return 0
    total = 0
    for value in stats.values():
        if isinstance(value, list):
            total += len(value)
    return total


def _list_len(value: object) -> int:
    return len(value) if isinstance(value, list) else 0


def _mapping_quality(game: Mapping[str, object]) -> Tuple[int, int, int, int, int, int]:
    return (
        1 if game.get("start_utc") else 0,
        1 if game.get("box_score_url") else 0,
        _mapping_stat_count(game),
        _list_len(game.get("scoring_summary")),
        _list_len(game.get("penalties")),
        _list_len(game.get("scoreboard")),
    )


def _copy_if_missing(target: MutableMapping[str, Any], candidate: Mapping[str, object], key: str) -> None:
    if not target.get(key) and candidate.get(key):
        target[key] = candidate.get(key)


def _merge_game_mapping(target: MutableMapping[str, Any], candidate: Mapping[str, object], *, include_source_metadata: bool) -> None:
    for key in ("start_local", "start_utc", "datetime", "location", "division", "summary_url"):
        _copy_if_missing(target, candidate, key)

    if not target.get("box_score_url") and candidate.get("box_score_url"):
        target["box_score_url"] = candidate.get("box_score_url")

    for key in ("player_stats", "scoring_summary", "penalties", "scoreboard"):
        contender = candidate.get(key)
        current = target.get(key)
        if key == "player_stats":
            if _mapping_stat_count(candidate) > _mapping_stat_count(target) and isinstance(contender, Mapping):
                target[key] = deepcopy(contender)
        else:
            if not isinstance(current, list) or (isinstance(contender, list) and len(contender) > len(current)):
                target[key] = deepcopy(contender)

    for side_key in ("home_line", "away_line"):
        side = target.get(side_key)
        contender = candidate.get(side_key)
        if not isinstance(contender, Mapping):
            continue
        if not isinstance(side, MutableMapping):
            side = dict(side) if isinstance(side, Mapping) else {}
            target[side_key] = side
        if not side.get("final") and contender.get("final") is not None:
            side["final"] = contender.get("final")
        if not side.get("periods") and contender.get("periods"):
            side["periods"] = deepcopy(contender.get("periods"))
        if side.get("is_winner") is None and contender.get("is_winner") is not None:
            side["is_winner"] = contender.get("is_winner")

    if include_source_metadata:
        source_ids = source_game_ids_for_mapping(target)
        for value in source_game_ids_for_mapping(candidate):
            if value not in source_ids:
                source_ids.append(value)
        target["source_game_ids"] = source_ids
        target["source_game_count"] = len(source_ids)


def dedupe_game_mappings(
    games: Iterable[Mapping[str, object]],
    *,
    include_source_metadata: bool = False,
) -> List[Dict[str, Any]]:
    grouped: Dict[CanonicalGameKey, List[Mapping[str, object]]] = defaultdict(list)
    for game in games:
        grouped[canonical_game_key_for_mapping(game)].append(game)

    deduped: List[Dict[str, Any]] = []
    for group in grouped.values():
        preferred_source = max(group, key=_mapping_quality)
        preferred = deepcopy(dict(preferred_source))
        if include_source_metadata:
            preferred["source_game_ids"] = source_game_ids_for_mapping(preferred_source)
            preferred["source_game_count"] = len(preferred["source_game_ids"])
        for candidate in group:
            if candidate is preferred_source:
                continue
            _merge_game_mapping(preferred, candidate, include_source_metadata=include_source_metadata)
        deduped.append(preferred)

    deduped.sort(
        key=lambda game: mapping_game_local_start(game) or datetime.max.replace(tzinfo=HALIFAX_TZ)
    )
    return deduped
