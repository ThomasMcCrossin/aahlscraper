# Quick Start Guide – Amherst Adult Hockey Scraper

## 1. Run the diagnostic
```bash
python scripts/aahl_cli.py diagnostics
```
This inspects the schedule, stats, and standings pages and recommends whether the fast HTTP scraper is sufficient or if you should switch to the Playwright backend. The JSON report is saved to `data/diagnostic_results.json`.

## 2. Install dependencies

**Always install the HTTP stack:**
```bash
pip install requests beautifulsoup4 pandas lxml
```

**Add Playwright only if the diagnostic suggests it:**
```bash
pip install playwright
playwright install chromium
```

## 3. Scrape data
```bash
python scripts/aahl_cli.py scrape --backend http
```

Key options:
- `--backend {http,playwright}` – pick the scraper implementation.
- `--team TEAM_ID` – override the default `DSMALL` team.
- `--targets schedule stats standings` – choose which datasets to collect.
- `--recent-weeks N` – also emit `recent_games.json` filtered to the last N weeks.
- `--current-week` – emit `current_week_games.json`.
- `--outdir path/to/output` – change where files are written (default `data/`).
- `--no-json` or `--no-csv` – skip a format.

## 4. Outputs
All generated files are stored in the `data/` directory by default:
- `schedule.json` / `schedule.csv`
- `player_stats.json` / `player_stats.csv`
- `standings.json` / `standings.csv`
- Optional `recent_games.json`, `current_week_games.json`

## 5. Use the Python API
```python
from pathlib import Path

from aahlscraper import AmherstHockeyScraper
from aahlscraper.exporters import export_csv, export_json

scraper = AmherstHockeyScraper(team_id="DSMALL")
schedule = scraper.scrape_schedule()
export_json(schedule, Path("data/schedule.json"))
export_csv(schedule, Path("data/schedule.csv"))
```

Swap in `AmherstHockeyPlaywrightScraper` if you need the browser-backed version.

## 6. Troubleshooting
- Empty tables → rerun the diagnostic; likely need the Playwright backend.
- Timeouts → retry with a better connection or increase the timeout when instantiating the scraper.
- Permission errors → ensure you have write access to the output directory.

## 7. Key project files

| Path | Purpose |
| --- | --- |
| `scripts/aahl_cli.py` | Unified CLI covering scraping and diagnostics |
| `scripts/run_diagnostics.py` | Thin wrapper around the diagnostic helpers |
| `src/aahlscraper/` | Python package with scrapers, exporters, and utilities |
| `data/` | Default location for generated outputs |
| `docs/` | Guides, diagrams, and sample data layouts |
