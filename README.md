# AAHL Scraper

A web scraper for the Amherst Adult Hockey League website that extracts schedules, player statistics, and team standings.

## Features

- **HTTP Backend (Recommended)**: Fast, lightweight scraping using BeautifulSoup
- **Playwright Backend (Optional)**: Browser-based scraping for JavaScript-heavy scenarios
- **Multiple Output Formats**: JSON and CSV exports
- **Built-in Diagnostics**: Automatically determines which backend to use
- **CLI and Python API**: Use from command line or import as a package
- **🆕 Yodeck Digital Signage Integration**: Professional display for stadium/canteen screens

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
- `results.json`
- `player_stats.json` / `player_stats.csv`
- `standings.json` / `standings.csv`
- `rosters.json` (plus `rosters/<team>.json` when the `rosters` target is enabled)
- `teams.json` (when the `teams` target is enabled)

## Usage

### Command Line

```bash
# Scrape all data using HTTP backend
python scripts/aahl_cli.py scrape --backend http

# Scrape specific targets
python scripts/aahl_cli.py scrape --backend http --targets schedule results stats

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

## 🏒 Yodeck Digital Signage Integration

Display live AAHL hockey stats on your stadium or canteen TV screens using Yodeck!

### What It Shows

The digital display automatically rotates through four sections:
1. **🏆 Team Standings** - Current league standings
2. **🎯 Top 20 Scorers** - Player rankings by points
3. **📊 Last 10 Days Results** - Recent game scores
4. **📅 Next 10 Days Games** - Upcoming games

### Quick Setup (2 Minutes)

**The display now automatically fetches live data from GitHub!** No manual updates needed.

```bash
# 1. Create deployment package
python aahl_yodeck_setup.py full
# Creates: aahl_display.zip

# 2. Upload to Yodeck portal
# - Log into Yodeck → Custom Apps → Add New HTML App
# - Upload aahl_display.zip
# - Click Save & Push Changes
```

That's it! The display automatically shows the latest data collected three times per day (8 AM, 12 PM, 4 PM Atlantic) plus live five-minute refreshes during Tuesday and Sunday night games.

### Features

✅ **Smart Name Corrections** - Automatically fixes player names
✅ **Auto-Rotation** - Each section displays for 15 seconds
✅ **Professional Design** - Sports-themed colors optimized for viewing
✅ **No Dependencies** - Self-contained HTML5 app
✅ **🌟 Fully Automated** - GitHub Actions scrapes on a smart cadence (daily checkpoints + game-night bursts with automatic DST handling)
✅ **Cloud-Based** - No server or cron jobs needed, runs entirely on GitHub

### How It Works

1. **GitHub Actions** automatically runs the scraper on the timed schedule
2. Fresh data is committed to the repository (`data/yodeck_display.json`)
3. The Yodeck display fetches the latest data from GitHub
4. Your screen automatically shows the most current stats
5. Cron windows automatically adjust for Atlantic Daylight/Standard Time so the cadence stays aligned with real game times year-round

**Zero maintenance required!** Just upload the display once and it stays updated forever.

### Documentation

See the `yodeck-docs/` folder for complete documentation:
- `README.md` - Full overview and features
- `quick-start.md` - 2-minute setup guide
- `yodeck-integration-guide.md` - Detailed integration steps
- `STADIUM_DISPLAY_GUIDE.md` - Display optimization tips

### Files

- `index.html` - Yodeck display application (upload to Yodeck)
- `aahl_yodeck_processor.py` - Data processor with name corrections
- `aahl_yodeck_setup.py` - Automated deployment helper

## License

This project is provided as-is for scraping publicly available data from the Amherst Adult Hockey League website.
