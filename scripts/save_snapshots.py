#!/usr/bin/env python3
"""
Persist timestamped snapshots of key AAHL data outputs.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Set

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
HISTORY_DIR = DATA_DIR / "history"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _latest_snapshot(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    snapshots = sorted(directory.glob("*.json"))
    return snapshots[-1] if snapshots else None


def _files_match(a: Path, b: Path) -> bool:
    try:
        return a.read_bytes() == b.read_bytes()
    except FileNotFoundError:
        return False


def _copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)

    latest = _latest_snapshot(dest.parent)
    if latest and _files_match(src, latest):
        print(f"Snapshot unchanged for {src.name}; skipping copy.")
        return False

    shutil.copy2(src, dest)
    return True


def _prune_consecutive_duplicates(directory: Path) -> int:
    if not directory.exists():
        return 0

    removed = 0
    last_bytes: bytes | None = None

    for path in sorted(directory.glob("*.json")):
        try:
            current = path.read_bytes()
        except FileNotFoundError:
            continue

        if last_bytes is not None and current == last_bytes:
            path.unlink(missing_ok=True)
            removed += 1
        else:
            last_bytes = current

    if removed:
        print(f"Pruned {removed} duplicate snapshot(s) from {directory.relative_to(HISTORY_DIR)}")

    return removed


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

    touched_dirs: Set[Path] = set()
    for source_name, target_name in copies:
        target_path = HISTORY_DIR / target_name
        _copy_if_exists(DATA_DIR / source_name, target_path)
        touched_dirs.add(target_path.parent)

    for directory in touched_dirs:
        _prune_consecutive_duplicates(directory)


if __name__ == "__main__":
    main()
