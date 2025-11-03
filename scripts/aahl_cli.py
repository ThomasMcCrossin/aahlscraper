#!/usr/bin/env python3
"""
Command-line interface for the aahlscraper package.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Iterable, List
import json
from importlib import resources

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aahlscraper import (
    AmherstHockeyPlaywrightScraper,
    AmherstHockeyScraper,
    run_diagnostics,
    summarize_recommendation,
)
from aahlscraper.exporters import export_csv, export_json
from aahlscraper.utils import parse_game_date


def _build_scraper(backend: str, team_id: str):
    if backend == "http":
        return AmherstHockeyScraper(team_id=team_id)
    return AmherstHockeyPlaywrightScraper(team_id=team_id)


def _export_records(records: List[Dict[str, str]], outdir: Path, basename: str, *, emit_json: bool, emit_csv: bool) -> None:
    if emit_json:
        export_json(records, outdir / f"{basename}.json")
    if emit_csv:
        export_csv(records, outdir / f"{basename}.csv")


def _filter_recent_games(records: Iterable[Dict[str, str]], weeks: int) -> List[Dict[str, str]]:
    from datetime import datetime, timedelta

    cutoff = datetime.now() - timedelta(weeks=weeks)

    filtered: List[Dict[str, str]] = []
    for record in records:
        parsed = parse_game_date(record.get("date", ""))
        if parsed is None or parsed >= cutoff:
            filtered.append(record)
    return filtered


def handle_scrape(args: argparse.Namespace) -> None:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    scraper = _build_scraper(args.backend, args.team)

    if "schedule" in args.targets or args.recent_weeks is not None or args.current_week:
        schedule = scraper.scrape_schedule()
        _export_records(schedule, outdir, "schedule", emit_json=not args.no_json, emit_csv=not args.no_csv)

        if args.recent_weeks is not None:
            recent = _filter_recent_games(schedule, args.recent_weeks)
            if not args.no_json:
                export_json(recent, outdir / "recent_games.json")

        if args.current_week:
            current = _filter_recent_games(schedule, weeks=0)
            if not args.no_json:
                export_json(current, outdir / "current_week_games.json")

    if "stats" in args.targets:
        stats = scraper.scrape_stats(sort_by=args.sort_stats)
        _export_records(stats, outdir, "player_stats", emit_json=not args.no_json, emit_csv=not args.no_csv)

    if "results" in args.targets:
        results = scraper.scrape_results()
        if not args.no_json:
            export_json(results, outdir / "results.json")

    if "rosters" in args.targets:
        rosters = scraper.scrape_rosters()
        if not args.no_json and rosters:
            roster_dir = outdir / "rosters"
            roster_dir.mkdir(parents=True, exist_ok=True)
            export_json(list(rosters.values()), outdir / "rosters.json")
            for slug, roster in rosters.items():
                export_json(roster["players"], roster_dir / f"{slug}.json")

    if "teams" in args.targets:
        if not args.no_json:
            teams_path = resources.files("aahlscraper.data").joinpath("teams.json")
            data = teams_path.read_text(encoding="utf-8")
            target = outdir / "teams.json"
            target.write_text(data, encoding="utf-8")

    if "standings" in args.targets:
        standings = scraper.scrape_standings()
        _export_records(standings, outdir, "standings", emit_json=not args.no_json, emit_csv=not args.no_csv)


def handle_diagnostics(args: argparse.Namespace) -> None:
    results = run_diagnostics(team_id=args.team)

    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=2), encoding="utf-8")

    print(f"Diagnostics for team {args.team}")
    for label, result in results.items():
        status = "OK" if result.get("success") else "ERROR"
        method = result.get("method") or "n/a"
        tables = result.get("tables", 0)
        print(f" - {label}: {status} | tables: {tables} | method: {method}")
        if result.get("js_frameworks"):
            frameworks = ", ".join(result["js_frameworks"])
            print(f"     JS hints: {frameworks}")
        if not result.get("success"):
            print(f"     Error: {result.get('error')}")

    print()
    print(summarize_recommendation(results))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Tools for scraping the Amherst Adult Hockey League site.")
    parser.add_argument("--team", default="DSMALL", help="Team id to target (default: DSMALL)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    scrape_parser = subparsers.add_parser("scrape", help="Scrape schedule, stats, and standings data")
    scrape_parser.add_argument("--backend", choices=("http", "playwright"), default="http", help="Scraping backend to use")
    scrape_parser.add_argument("--outdir", default="data", help="Directory where output files will be written")
    scrape_parser.add_argument("--no-json", action="store_true", help="Skip writing JSON output files")
    scrape_parser.add_argument("--no-csv", action="store_true", help="Skip writing CSV output files")
    scrape_parser.add_argument(
        "--targets",
        nargs="+",
        choices=("schedule", "results", "stats", "standings", "rosters", "teams"),
        default=("schedule", "results", "stats", "standings"),
        help="Data sets to scrape (default: all)",
    )
    scrape_parser.add_argument("--sort-stats", default="points", help="Sort order for stats endpoint")
    scrape_parser.add_argument("--recent-weeks", type=int, help="Also emit recent_games.json filtered by trailing weeks")
    scrape_parser.add_argument("--current-week", action="store_true", help="Also emit current_week_games.json")
    scrape_parser.set_defaults(func=handle_scrape)

    diag_parser = subparsers.add_parser("diagnostics", help="Run diagnostics to determine best scraping strategy")
    diag_parser.add_argument("--output", help="Optional path to write diagnostic results as JSON")
    diag_parser.set_defaults(func=handle_diagnostics)

    return parser


def main(argv: List[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
