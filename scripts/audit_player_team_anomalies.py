#!/usr/bin/env python3
"""
Audit player/team consistency across results.json.

This flags cases where a (name, number) appears for multiple teams. Those are
often caused by parsing issues (swapped/missing boxscore player-stat tables),
but can also be real AAHL data-entry artifacts.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
OUT_DIR = DATA_DIR / "v2" / "audits"
OUT_JSON = OUT_DIR / "player_team_anomalies.json"
OUT_MD = OUT_DIR / "player_team_anomalies.md"

SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aahlscraper.game_normalization import dedupe_game_mappings  # noqa: E402
from aahlscraper.utils import normalize_player_key, slugify  # noqa: E402


def _load_json(path: Path) -> object:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _safe_str(value: object) -> str:
    return str(value or "").strip()


def _team_slug_from_game(game: Mapping[str, object], side: str) -> str:
    line = game.get(f"{side}_line")
    if isinstance(line, Mapping) and line.get("slug"):
        return slugify(str(line.get("slug")))
    return slugify(_safe_str(game.get(side)))


def _canonical_game_id(game: Mapping[str, object]) -> str:
    return _safe_str(game.get("canonical_game_id") or game.get("game_id") or "")


def _local_date(game: Mapping[str, object]) -> str:
    # Prefer already-rendered local date, but fall back to legacy mm/dd/yyyy.
    return _safe_str(game.get("local_date") or game.get("date") or "")


@dataclass(frozen=True)
class PlayerKey:
    name_key: str
    number: str

    def label(self) -> str:
        num = self.number if self.number else "?"
        return f"{self.name_key} (#{num})"


def _roster_memberships(rosters: List[Mapping[str, object]]) -> Dict[PlayerKey, Set[str]]:
    memberships: Dict[PlayerKey, Set[str]] = defaultdict(set)
    for roster in rosters:
        team_slug = slugify(_safe_str(roster.get("team_slug") or roster.get("team_name")))
        players = roster.get("players")
        if not isinstance(players, list):
            continue
        for player in players:
            if not isinstance(player, Mapping):
                continue
            name = _safe_str(player.get("name"))
            if not name:
                continue
            number = _safe_str(player.get("number"))
            key = PlayerKey(normalize_player_key(name), number)
            memberships[key].add(team_slug)
    return memberships


def _fuzzy_matchup(game: Mapping[str, object]) -> str:
    away = _safe_str(game.get("away"))
    home = _safe_str(game.get("home"))
    if away and home:
        return f"{away} @ {home}"
    return away or home or ""


def main() -> int:
    results = _load_json(DATA_DIR / "results.json")
    rosters = _load_json(DATA_DIR / "rosters.json")

    if not isinstance(results, list):
        print("results.json must be a list")
        return 2
    if not isinstance(rosters, list):
        rosters = []

    roster_membership = _roster_memberships([r for r in rosters if isinstance(r, Mapping)])
    results_deduped = dedupe_game_mappings([g for g in results if isinstance(g, Mapping)], include_source_metadata=True)

    # key -> team_slug -> set(canonical_game_id)
    appearances: Dict[PlayerKey, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
    samples: Dict[Tuple[PlayerKey, str], List[Dict[str, str]]] = defaultdict(list)

    for game in results_deduped:
        for side in ("home", "away"):
            team_slug = _team_slug_from_game(game, side)
            stats = game.get("player_stats")
            if not isinstance(stats, Mapping):
                continue
            players = stats.get(side)
            if not isinstance(players, list):
                continue
            for row in players:
                if not isinstance(row, Mapping):
                    continue
                name = _safe_str(row.get("name"))
                if not name:
                    continue
                number = _safe_str(row.get("number"))
                key = PlayerKey(normalize_player_key(name), number)
                gid = _canonical_game_id(game)
                if not gid:
                    continue
                appearances[key][team_slug].add(gid)
                sample_key = (key, team_slug)
                if len(samples[sample_key]) < 6:
                    samples[sample_key].append(
                        {
                            "game": gid,
                            "date": _local_date(game),
                            "matchup": _fuzzy_matchup(game),
                            "result": _safe_str(game.get("result") or ""),
                        }
                    )

    anomalies: List[Dict[str, object]] = []
    one_game_suspects: List[Dict[str, object]] = []

    for key, by_team in appearances.items():
        teams = sorted(by_team.keys())
        if len(teams) <= 1:
            continue

        total_gp = sum(len(gids) for gids in by_team.values())
        row = {
            "player_key": {"name_key": key.name_key, "number": key.number},
            "total_games": total_gp,
            "teams": [
                {
                    "team_slug": team,
                    "games": len(by_team[team]),
                    "sample": samples.get((key, team), []),
                    "on_roster": team in roster_membership.get(key, set()),
                }
                for team in teams
            ],
            "roster_teams": sorted(roster_membership.get(key, set())),
        }
        anomalies.append(row)

        # Common pain: a player is rostered for one team but shows up as a 1 GP "member" elsewhere.
        for team in teams:
            if len(by_team[team]) == 1 and team not in roster_membership.get(key, set()):
                one_game_suspects.append(row)
                break

    anomalies.sort(key=lambda r: (-int(r.get("total_games") or 0), json.dumps(r.get("player_key") or {})))
    one_game_suspects.sort(key=lambda r: (-int(r.get("total_games") or 0), json.dumps(r.get("player_key") or {})))

    payload = {
        "games_considered": len(results_deduped),
        "multi_team_player_keys": len(anomalies),
        "multi_team_player_keys_one_game_suspects": len(one_game_suspects),
        "anomalies": anomalies,
        "one_game_suspects": one_game_suspects[:50],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    md: List[str] = []
    md.append("# Player Team Anomalies (results.json)")
    md.append("")
    md.append(f"- Games considered: {len(results_deduped)}")
    md.append(f"- Multi-team (name,number) keys: {len(anomalies)}")
    md.append(f"- 1-game suspects (not on roster for that team): {len(one_game_suspects)}")
    md.append("")
    md.append("## Top Suspects (up to 50)")
    md.append("")
    for entry in one_game_suspects[:50]:
        pk = entry.get("player_key") or {}
        label = f"{pk.get('name_key','')} (#{pk.get('number','?')})"
        md.append(f"- {label}: total {entry.get('total_games')} games")
        for team in entry.get("teams", []):
            if not isinstance(team, dict):
                continue
            roster_flag = "roster" if team.get("on_roster") else "non-roster"
            md.append(f"  - {team.get('team_slug')}: {team.get('games')} ({roster_flag})")
    md.append("")
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(f"Wrote: {OUT_JSON}")
    print(f"Wrote: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

