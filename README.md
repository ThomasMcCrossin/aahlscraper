# AAHL Scraper

A web scraper for the Amherst Adult Hockey League website that extracts schedules, player statistics, and team standings.

## Features

- **HTTP Backend (Recommended)**: Fast, lightweight scraping using BeautifulSoup
- **Playwright Backend (Optional)**: Browser-based scraping for JavaScript-heavy scenarios
- **Multiple Output Formats**: JSON and CSV exports
- **Built-in Diagnostics**: Automatically determines which backend to use
- **CLI and Python API**: Use from command line or import as a package

## Quick Start

### 1. Install Dependencies

**Required dependencies** (HTTP backend - works for most cases):
```bash
python3 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 pandas
```

**Optional dependencies** (Playwright backend - only needed if diagnostics recommend it):
```bash
pip install playwright
playwright install chromium
# May also require system dependencies on Linux
```

### 2. Run Diagnostics (Recommended)

Check which backend works best for your use case:
```bash
python scripts/run_diagnostics.py
```

This will test both backends and recommend the best approach. **In most cases, the HTTP backend is sufficient and Playwright is not needed.**

### 3. Scrape Data

```bash
python scripts/aahl_cli.py scrape --backend http
```

Output files will be created in the `data/` directory:
- `schedule.json` / `schedule.csv`
- `player_stats.json` / `player_stats.csv`
- `standings.json` / `standings.csv`

## Usage

### Command Line

```bash
# Scrape all data using HTTP backend
python scripts/aahl_cli.py scrape --backend http

# Scrape specific targets
python scripts/aahl_cli.py scrape --backend http --targets schedule stats

# Change team (default is DSMALL)
python scripts/aahl_cli.py scrape --backend http --team TEAMID

# Run diagnostics
python scripts/aahl_cli.py diagnostics
```

### Python API

```python
from aahlscraper import AmherstHockeyScraper
from aahlscraper.exporters import export_json, export_csv
from pathlib import Path

# Create scraper instance
scraper = AmherstHockeyScraper(team_id="DSMALL")

# Scrape data
schedule = scraper.scrape_schedule()
stats = scraper.scrape_stats()
standings = scraper.scrape_standings()

# Export to files
export_json(schedule, Path("data/schedule.json"))
export_csv(stats, Path("data/player_stats.csv"))
```

## When Do I Need Playwright?

**You probably don't!** The HTTP backend (BeautifulSoup) works in most cases because the AAHL website serves content as static HTML.

Only install Playwright if:
- The diagnostics tool explicitly recommends it
- You're getting empty results with the HTTP backend
- The website changes to use more JavaScript rendering

## Documentation

- [`docs/QUICK_START.md`](docs/QUICK_START.md) - Quick start guide
- [`docs/RUN_GUIDE.md`](docs/RUN_GUIDE.md) - Detailed usage instructions
- [`docs/IMPLEMENTATION_GUIDE.md`](docs/IMPLEMENTATION_GUIDE.md) - Technical implementation details

## Project Structure

```
aahlscraper/
├── src/aahlscraper/          # Main package
│   ├── http_scraper.py       # BeautifulSoup-based scraper (recommended)
│   ├── playwright_scraper.py # Browser-based scraper (optional)
│   ├── diagnostics.py        # Backend testing and recommendations
│   ├── exporters.py          # JSON/CSV export utilities
│   └── utils.py              # Helper functions
├── scripts/
│   ├── aahl_cli.py          # Main CLI interface
│   └── run_diagnostics.py   # Diagnostics runner
├── data/                     # Generated output files (gitignored)
└── docs/                     # Documentation
```

## Dependencies

### Required (HTTP Backend)
- `requests` - HTTP client
- `beautifulsoup4` - HTML parsing
- `pandas` - CSV export

### Optional (Playwright Backend)
- `playwright` - Browser automation (only if needed)

## License

This project is provided as-is for scraping publicly available data from the Amherst Adult Hockey League website.
