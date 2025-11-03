#!/usr/bin/env python3
"""
Backward-compatible entry point for the Playwright scraper.
Delegates to the consolidated CLI in scripts/aahl_cli.py.
"""

from __future__ import annotations

from scripts.aahl_cli import main


if __name__ == "__main__":
    main(["scrape", "--backend", "playwright"])
