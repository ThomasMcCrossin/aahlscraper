"""
Data export helpers for AAHL scraper outputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

import pandas as pd


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def export_json(records: Sequence[Mapping], path: Path) -> None:
    """
    Persist a sequence of mapping-like records to JSON.
    """
    _ensure_parent(path)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(list(records), handle, indent=2)


def export_csv(records: Sequence[Mapping], path: Path) -> None:
    """
    Persist a sequence of mapping-like records to CSV using pandas.
    """
    if not records:
        return

    _ensure_parent(path)
    frame = pd.DataFrame(records)
    frame.to_csv(path, index=False)
