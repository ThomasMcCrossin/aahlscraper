#!/usr/bin/env python3
"""
Persist timestamped snapshots of key AAHL data outputs.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _copy_if_exists(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)


def main() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stamp = _utc_stamp()

    copies: Iterable[tuple[str, str]] = (
        ("standings.json", f"standings/standings-{stamp}.json"),
        ("results.json", f"results/results-{stamp}.json"),
        ("schedule.json", f"schedule/schedule-{stamp}.json"),
        ("player_stats.json", f"player_stats/player_stats-{stamp}.json"),
        ("player_registry.json", f"player_registry/player_registry-{stamp}.json"),
    )

    for source_name, target_name in copies:
        _copy_if_exists(DATA_DIR / source_name, HISTORY_DIR / target_name)


if __name__ == "__main__":
    main()
