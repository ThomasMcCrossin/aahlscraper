# Amherst Adult Hockey Scraper – Local Run Guide

This guide walks you through setting up the scraper on your own machine, running the diagnostic script, choosing the appropriate scraping approach, and verifying the outputs. It assumes basic familiarity with the command line.

---

## 1. Prerequisites

- **Operating system:** macOS, Linux, or Windows (PowerShell/Git Bash).
- **Python:** 3.9 or newer installed and available as `python3` (Linux/macOS) or `python` (Windows).  
  - On macOS: `brew install python` (or use the Python.org installer).  
  - On Windows: install from https://www.python.org/downloads/ and check “Add python.exe to PATH”.
- **Git (optional):** For cloning the repository instead of downloading a ZIP.
- **Internet access:** Required for installing dependencies and reaching `www.amherstadulthockey.com`.

---

## 2. Get the Project

1. **Clone or download the repository.**
   ```bash
   git clone https://github.com/your-org/aahlscraper.git
   cd aahlscraper
   ```
   Or download/extract the ZIP and open a terminal in the extracted folder.

2. **Inspect the layout (optional).**
   ```bash
   ls
   ```
   You should see directories like `src/`, `scripts/`, `data/`, and `docs/`.

---

## 3. Create a Virtual Environment

Keeping dependencies isolated prevents conflicts with system Python packages.

```bash
python3 -m venv .venv          # Windows: python -m venv .venv
source .venv/bin/activate      # Windows PowerShell: .\.venv\Scripts\Activate.ps1
```

When the environment is active, your prompt will include `(.venv)` or similar.

> Tip: To leave the virtual environment later, run `deactivate`.

---

## 4. Install Dependencies

With the virtual environment active, install the base libraries:

```bash
pip install requests beautifulsoup4 pandas lxml
```

If you plan to use the Playwright-based scraper, install the extra packages as well:

```bash
pip install playwright
playwright install chromium
```

> On macOS with Apple Silicon, Playwright might prompt for additional system dependencies. Follow the on-screen instructions.

---

## 5. Run the Diagnostic

The diagnostic script determines whether the site exposes data directly in HTML (BeautifulSoup-friendly) or requires a browser automation approach.

```bash
python scripts/aahl_cli.py diagnostics
```

### Interpreting the Output

- Success messages for all pages → proceed with the HTTP backend.
- Warnings indicating missing tables or JavaScript-loaded content → switch to the Playwright backend (`--backend playwright`).
- Any errors (e.g., network issues) are logged, and the script saves a JSON report to `diagnostic_results.json` for review.

---

## 6. Run the HTTP scraper (default)

If the diagnostic recommends the static approach:

```bash
python scripts/aahl_cli.py scrape --backend http
```

This command fetches the schedule, stats, and standings, writing JSON and CSV files to `data/`.

### Custom team or filtering

```python
from pathlib import Path

from aahlscraper import AmherstHockeyScraper
from aahlscraper.exporters import export_csv, export_json

scraper = AmherstHockeyScraper(team_id="YOUR_TEAM_ID")
schedule = scraper.scrape_schedule(format_type="Calendar", date_filter="2025-01-01")
export_json(schedule, Path("data/schedule.json"))
export_csv(schedule, Path("data/schedule.csv"))
```

---

## 7. Run the Playwright scraper (if needed)

If the diagnostic indicates dynamic content:

```bash
python scripts/aahl_cli.py scrape --backend playwright
```

Requirements:
- Chromium installed via `playwright install chromium`.
- GUI is not required; Playwright runs headless by default.

---

## 8. Verify the Outputs

After running either scraper, confirm the expected files exist:

```bash
ls data
```

Inspect a sample:

```bash
python - <<'PY'
import json
from pathlib import Path
for name in ["schedule.json", "player_stats.json"]:
    path = Path("data") / name
    if path.exists():
        data = json.loads(path.read_text())
        print(name, "- sample:", data[:2])
PY
```

---

## 9. Automation (Optional)

- **Cron (Linux/macOS):** `crontab -e` → `0 6 * * * /path/to/.venv/bin/python /path/to/scripts/aahl_cli.py scrape --backend http`
- **Windows Task Scheduler:** Create a task that activates the virtual environment and runs the script.
- **Logging:** Redirect output to a log file, e.g., `python scripts/aahl_cli.py scrape >> scraper.log 2>&1`.

---

## 10. Troubleshooting

- **`ModuleNotFoundError`:** Ensure the virtual environment is active and dependencies are installed.
- **SSL or connection errors:** Verify internet connectivity, retry later, or run with a VPN if the site blocks your region.
- **Playwright failures:** Re-run `playwright install chromium`. On Linux servers, install additional system libraries listed in the Playwright docs.
- **Permission errors when writing files:** Confirm you have write access to the working directory.
- **Unexpected HTML changes:** Update the selectors in `src/aahlscraper/http_scraper.py` accordingly. Use developer tools to inspect new table structures.

---

## 11. Clean Up

When you are finished:

```bash
deactivate           # leave the virtual environment
rm -rf .venv         # optional; removes the environment
```

Remove generated JSON/CSV files if you no longer need them.

---

## 12. Need to Recreate Everything Quickly?

```bash
git clone https://github.com/your-org/aahlscraper.git
cd aahlscraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt      # if you generate one
python scripts/aahl_cli.py diagnostics
python scripts/aahl_cli.py scrape
```

> You can generate `requirements.txt` inside the virtual environment via `pip freeze > requirements.txt` if you want to capture exact versions.

---

With these steps, you should be able to run the diagnostic and scraper successfully on your own machine. Reach out to your team or maintainers if the site structure changes and scraping selectors need to be updated.
