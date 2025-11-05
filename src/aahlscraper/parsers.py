"""
HTML and ICS parsing helpers for the AAHL scraper.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from urllib.parse import parse_qs, urljoin, urlparse
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from bs4.element import Tag

from .common import normalize_header
from .models import GameRecord, GameTeamLine, RosterPlayer, ScoreBoardEntry, TeamRoster
from .utils import derive_player_id, normalize_roster_name, slugify

CALENDAR_URL = "https://media.hometeamsonline.com/photos/hockey/{team_id}/data/schedule.ics"
BASE_TEAM_URL = "https://www.amherstadulthockey.com/teams/default.asp"

BULLET_PATTERN = re.compile(r"[•\u2022]+")
WHITESPACE_PATTERN = re.compile(r"\s+")
SUMMARY_PATTERN = re.compile(
    r"^(?P<home>.+?)\s+vs\.?\s+(?P<away>.+?)(?:\s*\((?P<home_score>\d+)\s*-\s*(?P<away_score>\d+)\))?$",
    re.IGNORECASE,
)
URL_PATTERN = re.compile(r"https?://[^\s]+")
ROLE_PATTERN = re.compile(r"\((home|away)\)", re.IGNORECASE)


def _unfold_ics_lines(text: str) -> Iterator[str]:
    """
    Merge folded ICS lines into full logical lines.
    """

    current = ""
    for raw_line in text.splitlines():
        if not raw_line:
            if current:
                yield current
                current = ""
            continue

        if raw_line.startswith((" ", "\t")):
            current += raw_line[1:]
        else:
            if current:
                yield current
            current = raw_line

    if current:
        yield current


def _iter_ics_events(text: str) -> Iterator[Dict[str, str]]:
    """
    Yield raw ICS event dictionaries from a calendar blob.
    """

    event: Dict[str, str] = {}
    for line in _unfold_ics_lines(text):
        if line == "BEGIN:VEVENT":
            event = {}
            continue
        if line == "END:VEVENT":
            if event:
                yield event
            event = {}
            continue

        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        # Drop parameter payloads (e.g., DTSTART;TZID=America/Halifax)
        key = key.split(";", 1)[0].strip().upper()
        event[key] = value.strip()


def _parse_datetimeish(raw: Optional[str], *, local_tz: ZoneInfo) -> Tuple[Optional[datetime], Optional[datetime]]:
    if not raw:
        return None, None

    fmt_variants = ("%Y%m%dT%H%M%SZ", "%Y%m%dT%H%M%S", "%Y%m%dT%H%M")
    value = raw.strip()
    tz_aware = None
    for fmt in fmt_variants:
        try:
            parsed = datetime.strptime(value.rstrip("Z"), fmt.rstrip("Z"))
        except ValueError:
            continue

        if value.endswith("Z"):
            tz_aware = parsed.replace(tzinfo=timezone.utc)
        else:
            tz_aware = parsed.replace(tzinfo=local_tz)
        break

    if tz_aware is None:
        return None, None

    if tz_aware.tzinfo is timezone.utc:
        local_dt = tz_aware.astimezone(local_tz)
    else:
        local_dt = tz_aware
        tz_aware = local_dt.astimezone(timezone.utc)
    return tz_aware, local_dt


def _parse_summary(summary: str) -> Tuple[str, str, Optional[int], Optional[int]]:
    cleaned = summary.strip()
    match = SUMMARY_PATTERN.match(cleaned)
    if not match:
        # Fallback: split on " vs "
        parts = re.split(r"\s+vs\.?\s+", cleaned, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip(), None, None
        return cleaned, "", None, None

    home = match.group("home").strip()
    away = match.group("away").strip()
    home_score = match.group("home_score")
    away_score = match.group("away_score")
    return home, away, int(home_score) if home_score else None, int(away_score) if away_score else None


def _extract_game_id(event: Dict[str, str]) -> str:
    for key in ("DESCRIPTION", "UID"):
        candidate = event.get(key, "")
        match = re.search(r"gameID=(\d+)", candidate, re.IGNORECASE)
        if match:
            return match.group(1)
    # Fallback to UID or a generated value
    return event.get("UID", "").strip() or "unknown"


def _extract_box_score_url(event: Dict[str, str]) -> Optional[str]:
    description = event.get("DESCRIPTION", "")
    match = URL_PATTERN.search(description)
    return match.group(0) if match else None


def _strip_role_tag(name: str) -> Tuple[str, Optional[str]]:
    match = ROLE_PATTERN.search(name)
    role: Optional[str] = None
    if match:
        role = match.group(1).lower()
        name = ROLE_PATTERN.sub("", name)
    return WHITESPACE_PATTERN.sub(" ", name).strip(), role


def parse_ics_games(
    text: str,
    *,
    location_filter: Optional[str] = "Amherst",
    tz_name: str = "America/Halifax",
) -> List[GameRecord]:
    """
    Parse the AAHL ICS calendar into game records.
    """

    local_tz = ZoneInfo(tz_name)
    games: List[GameRecord] = []

    for event in _iter_ics_events(text):
        location = event.get("LOCATION", "").strip()
        if location_filter and location_filter.lower() not in location.lower():
            continue

        summary = event.get("SUMMARY", "").strip()
        if not summary:
            continue

        home_name, away_name, home_score, away_score = _parse_summary(summary)
        game_id = _extract_game_id(event)
        start_utc, start_local = _parse_datetimeish(event.get("DTSTART"), local_tz=local_tz)
        box_score_url = _extract_box_score_url(event)
        summary_url = None
        if box_score_url and "p=boxscore" in box_score_url:
            summary_url = box_score_url.replace("p=boxscore", "p=summary")

        status = "final" if home_score is not None and away_score is not None else "scheduled"

        home_name, home_role = _strip_role_tag(home_name)
        away_name, away_role = _strip_role_tag(away_name)

        candidate_home = GameTeamLine(name=home_name, slug=slugify(home_name), final=home_score)
        candidate_away = GameTeamLine(name=away_name, slug=slugify(away_name), final=away_score)

        if home_role == "away" or away_role == "home":
            home_line, away_line = candidate_away, candidate_home
        else:
            home_line, away_line = candidate_home, candidate_away

        games.append(
            GameRecord(
                game_id=game_id,
                start_utc=start_utc,
                start_local=start_local,
                location=location,
                status=status,
                home=home_line,
                away=away_line,
                division=None,
                box_score_url=box_score_url,
                summary_url=summary_url,
            )
        )

    return games


def _clean_bullet_text(raw: str) -> str:
    without_bullet = BULLET_PATTERN.sub(" ", raw)
    return WHITESPACE_PATTERN.sub(" ", without_bullet).strip()


def _parse_score_team_row(row: Tag) -> GameTeamLine:
    name_tag = row.find("td", class_="team")
    name = name_tag.get_text(strip=True) if name_tag else ""

    final_tag = row.find("td", class_="final")
    final_value = final_tag.get_text(strip=True) if final_tag else ""
    final_score = int(final_value) if final_value.isdigit() else None

    period_values: List[Optional[int]] = []
    for period_td in row.find_all("td", class_="period"):
        text = period_td.get_text(strip=True)
        period_values.append(int(text) if text.isdigit() else None)

    is_winner = "win" in (row.get("class") or [])

    return GameTeamLine(
        name=name,
        slug=slugify(name),
        final=final_score,
        periods=period_values,
        is_winner=is_winner,
    )


def parse_scoreboard(html: str, *, tz_name: str = "America/Halifax") -> List[ScoreBoardEntry]:
    """
    Parse the AAHL scores page into scoreboard entries.
    """

    soup = BeautifulSoup(html, "html.parser")
    local_tz = ZoneInfo(tz_name)
    entries: List[ScoreBoardEntry] = []

    for board_wrapper in soup.select("div.scoreBoard.periodScore"):
        parent = board_wrapper.parent
        if not isinstance(parent, Tag):
            continue

        header = parent.find("div", class_="gameDate")
        location = ""
        date_text = ""
        time_text = ""
        if header:
            spans = header.find_all("span")
            if len(spans) >= 1:
                location = _clean_bullet_text(spans[0].get_text(" ", strip=True))
            if len(spans) >= 2:
                date_text = _clean_bullet_text(spans[1].get_text(" ", strip=True))
            if len(spans) >= 3:
                time_text = _clean_bullet_text(spans[2].get_text(" ", strip=True))

        division = None
        heading_cell = board_wrapper.find("td", class_="location")
        if heading_cell:
            division = heading_cell.get_text(strip=True) or None

        start_local = None
        if date_text:
            dt_candidate = date_text
            if time_text:
                dt_candidate = f"{date_text} {time_text}"
            for fmt in ("%b %d, %Y %I:%M %p", "%b %d, %Y %I %p", "%b %d, %Y"):
                try:
                    parsed = datetime.strptime(dt_candidate, fmt)
                    start_local = parsed.replace(tzinfo=local_tz)
                    break
                except ValueError:
                    continue

        team_rows = [row for row in board_wrapper.select("tbody tr") if isinstance(row, Tag)]
        teams = [_parse_score_team_row(row) for row in team_rows if row.find("td", class_="team")]
        if len(teams) != 2:
            continue

        link_wrapper = parent.find("div", class_="scoreSummary")
        box_score_url = None
        summary_url = None
        if link_wrapper:
            anchor = link_wrapper.find("a")
            if anchor and anchor.get("href"):
                absolute = urljoin(BASE_TEAM_URL, anchor["href"])
                box_score_url = absolute
                parsed = urlparse(absolute)
                query = parse_qs(parsed.query)
                game_id = query.get("gameID", [None])[0]
                if "p=boxscore" in absolute:
                    summary_url = absolute.replace("p=boxscore", "p=summary")
            else:
                game_id = None
        else:
            game_id = None

        if not teams:
            continue

        # Fallback to parse game id from box score url if not already extracted
        if not box_score_url:
            game_id = None
        else:
            parsed = urlparse(box_score_url)
            query = parse_qs(parsed.query)
            game_id = query.get("gameID", [None])[0]

        if not game_id:
            continue

        entries.append(
            ScoreBoardEntry(
                game_id=str(game_id),
                location=location,
                division=division,
                start_local=start_local,
                teams=teams,
                box_score_url=box_score_url,
                summary_url=summary_url,
            )
        )

    return entries


def merge_games_with_scores(games: List[GameRecord], scores: List[ScoreBoardEntry]) -> List[GameRecord]:
    """
    Merge scoreboard details into ICS-derived games.
    """

    games_by_id = {game.game_id: game for game in games}

    for score in scores:
        game = games_by_id.get(score.game_id)
        if not game:
            # If the scoreboard has an entry not present in ICS, create a new stub.
            if len(score.teams) == 2:
                home, away = score.teams
                games_by_id[score.game_id] = GameRecord(
                    game_id=score.game_id,
                    start_utc=None,
                    start_local=score.start_local,
                    location=score.location,
                    status="final" if home.final is not None and away.final is not None else "unknown",
                    home=home,
                    away=away,
                    division=score.division,
                    box_score_url=score.box_score_url,
                    summary_url=score.summary_url,
                )
            continue

        game.division = game.division or score.division
        game.box_score_url = score.box_score_url or game.box_score_url
        game.summary_url = score.summary_url or game.summary_url
        if score.start_local and not game.start_local:
            game.start_local = score.start_local
            game.start_utc = score.start_local.astimezone(timezone.utc)
        if score.location:
            game.location = score.location

        # Align teams by slug to avoid ordering issues
        score_teams = {team.slug: team for team in score.teams}
        for side in ("home", "away"):
            line = getattr(game, side)
            score_line = score_teams.get(line.slug)
            if score_line:
                line.final = score_line.final
                line.periods = score_line.periods
                line.is_winner = score_line.is_winner

        if game.home.final is not None and game.away.final is not None:
            game.status = "final"

    return list(games_by_id.values())


def _extract_text(td: Optional[Tag]) -> Optional[str]:
    if td is None:
        return None
    text = td.get_text(strip=True)
    return text or None


def _split_positions(raw: Optional[str]) -> List[str]:
    if not raw:
        return []
    parts = re.split(r"[\/·,]+", raw)
    return [part.strip() for part in parts if part.strip()]


def parse_rosters(html: str) -> Dict[str, TeamRoster]:
    """
    Parse the roster page into structured rosters keyed by slug.
    """

    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="group_byTeam")
    if not table:
        return {}

    rosters: Dict[str, TeamRoster] = {}
    bodies = table.find_all("tbody", recursive=False)

    i = 0
    while i < len(bodies):
        header = bodies[i]
        if not header or not header.get("id", "").startswith("parent_"):
            i += 1
            continue

        team_id = header.get("id").replace("parent_", "").strip()
        name_span = header.find("span", class_="teamLabel")
        team_name = name_span.get_text(strip=True) if name_span else team_id
        team_slug = slugify(team_name)

        i += 1
        if i >= len(bodies):
            break

        roster_body = bodies[i]
        players: List[RosterPlayer] = []

        for row in roster_body.find_all("tr", class_="modGroupItem"):
            classes = row.get("class") or []
            if "thead" in classes:
                continue

            cells = {cell.get("class", [""])[0]: cell for cell in row.find_all("td")}

            number = _extract_text(cells.get("playernumberLabel"))
            raw_name = _extract_text(cells.get("nameLabel")) or ""
            name, captaincy = normalize_roster_name(raw_name)
            positions = _split_positions(_extract_text(cells.get("positionsAllLabel")))
            height = _extract_text(cells.get("heightLabel"))
            weight = _extract_text(cells.get("weightLabel"))
            shoots = _extract_text(cells.get("shootsLabel"))
            catches = _extract_text(cells.get("catchesLabel"))
            hometown = _extract_text(cells.get("hometownLabel"))

            player_id = derive_player_id(team_slug, name, number)

            players.append(
                RosterPlayer(
                    number=number,
                    name=name,
                    positions=positions,
                    player_id=player_id,
                    height=height,
                    weight=weight,
                    shoots=shoots,
                    catches=catches,
                    hometown=hometown,
                    captaincy=captaincy,
                )
            )

        rosters[team_slug] = TeamRoster(
            team_id=team_id,
            team_name=team_name,
            team_slug=team_slug,
            players=players,
        )

        i += 1

    return rosters


def _safe_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        try:
            return int(float(value))
        except ValueError:
            return None


def _parse_table_rows(table: Tag) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["td", "th"])
        if not cells:
            continue
        rows.append([cell.get_text(" ", strip=True) for cell in cells])
    return rows


def parse_box_score(html: str) -> Dict[str, object]:
    """
    Parse an AAHL box score page extracting scoreboard, scoring summary, penalties, and player stats.
    """

    soup = BeautifulSoup(html, "html.parser")

    scoreboard_rows: List[List[str]] = []
    scoreboard = soup.select_one("div.scoreBoard table")
    team_order: List[str] = []
    if scoreboard:
        scoreboard_rows = _parse_table_rows(scoreboard)
        for row in scoreboard_rows[1:]:
            if row:
                team_order.append(row[0])

    scoring_summary: List[Dict[str, str]] = []
    penalties: List[Dict[str, str]] = []
    player_tables: List[Dict[str, object]] = []

    for table in soup.find_all("table"):
        raw_rows = _parse_table_rows(table)
        if not raw_rows:
            continue
        headers = [normalize_header(cell) for cell in raw_rows[0]]
        rows = raw_rows[1:]

        if {"perperiod", "time", "team"}.issubset(headers):
            for row in rows:
                record = {}
                for idx, header in enumerate(headers):
                    if idx < len(row):
                        record[header] = row[idx]
                if record:
                    scoring_summary.append(record)
            continue

        if "infraction" in headers or "length" in headers:
            for row in rows:
                record = {}
                for idx, header in enumerate(headers):
                    if idx < len(row):
                        record[header] = row[idx]
                if record:
                    penalties.append(record)
            continue

        if "name" in headers and ("g" in headers or "goals" in headers):
            players: List[Dict[str, object]] = []
            for row in rows:
                if not row:
                    continue
                lowered = [cell.lower() for cell in row if isinstance(cell, str)]
                if any("team stats" in cell for cell in lowered) or any("overall stats" in cell for cell in lowered):
                    continue

                record: Dict[str, object] = {}
                for idx, header in enumerate(headers):
                    record[header] = row[idx] if idx < len(row) else ""

                name = (record.get("name") or record.get("player") or "").strip()
                if not name:
                    continue

                number = (record.get("no") or record.get("number") or "").strip() or None
                positions = (record.get("pos") or record.get("position") or "").strip()
                goals = _safe_int(str(record.get("g") or record.get("goals") or "")) or 0
                assists = _safe_int(str(record.get("a") or record.get("assists") or "")) or 0
                points = _safe_int(str(record.get("pts") or record.get("points") or "")) or (goals + assists)
                pim = _safe_int(str(record.get("pim") or record.get("pen") or "")) or 0
                gtg = _safe_int(str(record.get("gtg") or record.get("game_tying_goals") or "")) or 0

                players.append(
                    {
                        "number": number,
                        "name": name,
                        "positions": positions,
                        "goals": goals,
                        "assists": assists,
                        "points": points,
                        "pim": pim,
                        "gtg": gtg,
                        "raw": record,
                    }
                )

            player_tables.append({"headers": headers, "players": players})

    teams: List[Dict[str, object]] = []
    for idx, table in enumerate(player_tables):
        team_name = team_order[idx] if idx < len(team_order) else None
        teams.append({"team_name": team_name, "players": table["players"]})

    return {
        "scoreboard": scoreboard_rows,
        "scoring_summary": scoring_summary,
        "penalties": penalties,
        "teams": teams,
    }
