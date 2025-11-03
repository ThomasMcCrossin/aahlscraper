#!/usr/bin/env python3
"""
Convenience wrapper around the aahlscraper diagnostics helpers.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from aahlscraper import run_diagnostics, summarize_recommendation


def main() -> None:
    parser = argparse.ArgumentParser(description="Run diagnostics for the AAHL scraper.")
    parser.add_argument("--team", default="DSMALL", help="Team id to analyze (default: DSMALL)")
    parser.add_argument(
        "--output",
        default="data/diagnostic_results.json",
        help="Path where diagnostic JSON results should be written",
    )
    args = parser.parse_args()

    results = run_diagnostics(team_id=args.team)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2), encoding="utf-8")

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
    print(f"\nDetailed results written to {output_path}")


if __name__ == "__main__":
    main()
