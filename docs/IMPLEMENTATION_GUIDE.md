
# Amherst Adult Hockey Scraper - Implementation Guide

## Overview
This guide provides multiple approaches to scrape data from the Amherst Adult Hockey website and convert it to clean JSON format.

## Problem Analysis
The website uses ASP.NET Classic (.asp pages) which typically:
- Renders HTML on the server side
- Uses ViewState and form data for interactions
- May include some JavaScript for dynamic behavior
- Doesn't expose public REST APIs

## Solution Approaches

### Approach 1: BeautifulSoup (Recommended for Static Content)

**Best for:** Sites where data is in the HTML source
**Pros:** Fast, lightweight, no browser overhead
**Cons:** Won't work if data loads via JavaScript

**Installation:**
```bash
pip install requests beautifulsoup4 pandas lxml
```

**Usage:**
```python
from pathlib import Path

from aahlscraper import AmherstHockeyScraper
from aahlscraper.exporters import export_csv, export_json

scraper = AmherstHockeyScraper(team_id="DSMALL")

# Get all games
schedule = scraper.scrape_schedule()

# Get last week's games
recent_games = scraper.get_recent_games(weeks=1)

# Get current week (games from last 7 days to future)
current_week = scraper.get_recent_games(weeks=0)

# Get stats
stats = scraper.scrape_stats(sort_by='points')

# Get standings
standings = scraper.scrape_standings()

# Export to disk
export_json(schedule, Path('data/schedule.json'))
export_csv(schedule, Path('data/schedule.csv'))
```

### Approach 2: Playwright (For JavaScript-Heavy Pages)

**Best for:** Sites that load data dynamically via JavaScript
**Pros:** Handles JavaScript, captures final rendered state
**Cons:** Slower, requires browser installation

**Installation:**
```bash
pip install playwright pandas
playwright install chromium
```

**Usage:**
```python
from pathlib import Path

from aahlscraper import AmherstHockeyPlaywrightScraper
from aahlscraper.exporters import export_json

scraper = AmherstHockeyPlaywrightScraper(team_id="DSMALL")

schedule = scraper.scrape_schedule()
stats = scraper.scrape_stats()
standings = scraper.scrape_standings()

export_json(schedule, Path('data/schedule_playwright.json'))
```

### Approach 3: Hybrid Selenium Approach (Fallback)

**Installation:**
```bash
pip install selenium pandas
```

**Quick Implementation:**
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json

def scrape_with_selenium(url):
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    driver = webdriver.Chrome(options=options)

    try:
        driver.get(url)
        # Wait for table to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "table"))
        )

        # Get page source and parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        table = soup.find('table')

        # Extract data
        data = []
        for row in table.find_all('tr')[1:]:
            cells = [cell.get_text(strip=True) for cell in row.find_all(['td', 'th'])]
            data.append(cells)

        return data
    finally:
        driver.quit()

# Usage
url = "https://www.amherstadulthockey.com/teams/default.asp?u=DSMALL&s=hockey&p=schedule&format=List&d=ALL"
data = scrape_with_selenium(url)
```

## Determining Which Approach to Use

### Step 1: Test with BeautifulSoup First

Run this diagnostic script:

```python
import requests
from bs4 import BeautifulSoup

url = "https://www.amherstadulthockey.com/teams/default.asp?u=DSMALL&s=hockey&p=schedule&format=List&d=ALL"
response = requests.get(url)
soup = BeautifulSoup(response.text, 'html.parser')

# Check if data is in HTML
tables = soup.find_all('table')
print(f"Found {len(tables)} tables")

for idx, table in enumerate(tables):
    rows = table.find_all('tr')
    print(f"\nTable {idx}: {len(rows)} rows")
    if rows:
        first_row = rows[0]
        cells = first_row.find_all(['td', 'th'])
        print(f"First row has {len(cells)} cells")
        print(f"Sample: {[c.get_text(strip=True) for c in cells[:3]]}")
```

**If you see game data:** Use BeautifulSoup approach (faster)
**If tables are empty:** Use Playwright/Selenium approach (JavaScript required)

## Data Structure Examples

### Schedule JSON Structure
```json
[
  {
    "date": "11/01/2025",
    "time": "8:00 PM",
    "opponent": "Team Name",
    "location": "Rink 1",
    "result": "W",
    "score": "5-3"
  }
]
```

### Stats JSON Structure
```json
[
  {
    "player": "John Doe",
    "games_played": "10",
    "goals": "8",
    "assists": "12",
    "points": "20",
    "penalties": "4"
  }
]
```

### Standings JSON Structure
```json
[
  {
    "team": "Team Name",
    "games_played": "10",
    "wins": "7",
    "losses": "2",
    "ties": "1",
    "points": "15",
    "goals_for": "45",
    "goals_against": "28"
  }
]
```

## Advanced Features

### Filtering by Date Range

```python
from datetime import datetime, timedelta

def filter_games_by_date_range(games, start_date, end_date):
    '''Filter games between two dates'''
    filtered = []
    for game in games:
        try:
            game_date = datetime.strptime(game['date'], '%m/%d/%Y')
            if start_date <= game_date <= end_date:
                filtered.append(game)
        except:
            continue
    return filtered

# Get last week's games
today = datetime.now()
last_week = today - timedelta(days=7)
recent_games = filter_games_by_date_range(all_games, last_week, today)

# Get current week's games (this week and next)
next_week = today + timedelta(days=7)
current_week = filter_games_by_date_range(all_games, today, next_week)
```

### Scheduling Automatic Scraping

**Using cron (Linux/Mac):**
```bash
# Run every day at 6 AM
0 6 * * * /usr/bin/python3 /path/to/scripts/aahl_cli.py scrape --backend http
```

**Using Task Scheduler (Windows):**
Create a .bat file:
```batch
@echo off
cd C:\path\to\scraper
python scripts/aahl_cli.py scrape
```

**Using Python schedule library:**
```python
from pathlib import Path

import schedule
import time

from aahlscraper import AmherstHockeyScraper
from aahlscraper.exporters import export_json


def job():
    scraper = AmherstHockeyScraper()
    games = scraper.scrape_schedule()
    export_json(games, Path('data/schedule.json'))

# Run every day at 6 AM
schedule.every().day.at("06:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Troubleshooting

### Issue: Empty Data Returned
**Solution:** The site likely uses JavaScript. Switch to Playwright approach.

### Issue: Connection Errors
**Solution:** Add retry logic with exponential backoff:

```python
import time
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

session = requests.Session()
retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

### Issue: Data Structure Changes
**Solution:** Add flexible parsing with error handling:

```python
def safe_extract(cells, index, default=''):
    try:
        return cells[index].get_text(strip=True)
    except (IndexError, AttributeError):
        return default
```

### Issue: Rate Limiting
**Solution:** Add delays between requests:

```python
import time

for page in pages:
    data = scrape_page(page)
    time.sleep(2)  # 2-second delay
```

## Performance Optimization

### 1. Use Session Objects
Reuse connections for faster requests:
```python
session = requests.Session()
response1 = session.get(url1)
response2 = session.get(url2)
```

### 2. Parallel Scraping
For multiple pages:
```python
from concurrent.futures import ThreadPoolExecutor

urls = [schedule_url, stats_url, standings_url]

with ThreadPoolExecutor(max_workers=3) as executor:
    results = list(executor.map(scrape_page, urls))
```

### 3. Caching
Store results to avoid repeated scraping:
```python
import json
from pathlib import Path
from datetime import datetime

def load_cached_data(filename, max_age_hours=1):
    path = Path(filename)
    if path.exists():
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age.total_seconds() < max_age_hours * 3600:
            with open(filename) as f:
                return json.load(f)
    return None
```

## Best Practices

1. **Respect the Website**
   - Add delays between requests
   - Don't overwhelm the server
   - Scrape during off-peak hours

2. **Error Handling**
   - Always use try-except blocks
   - Log errors for debugging
   - Implement retry logic

3. **Data Validation**
   - Verify data structure before saving
   - Check for missing or malformed data
   - Validate dates and numeric fields

4. **Version Control**
   - Track changes to scraper code
   - Document data structure changes
   - Keep examples of scraped data

## Integration Examples

### Node.js Integration
```javascript
const { exec } = require('child_process');

exec('python scripts/aahl_cli.py scrape', (error, stdout, stderr) => {
  if (error) {
    console.error(`Error: ${error}`);
    return;
  }

  // Read the JSON file
  const schedule = require('./data/schedule.json');
  console.log(schedule);
});
```

### REST API Wrapper
```python
from flask import Flask, jsonify

from aahlscraper import AmherstHockeyScraper

app = Flask(__name__)
scraper = AmherstHockeyScraper()

@app.route('/api/schedule')
def get_schedule():
    data = scraper.scrape_schedule()
    return jsonify(data)

@app.route('/api/stats')
def get_stats():
    data = scraper.scrape_stats()
    return jsonify(data)

@app.route('/api/standings')
def get_standings():
    data = scraper.scrape_standings()
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True)
```

## Next Steps

1. **Test the Scraper:** Run the diagnostic script to see which approach works
2. **Customize Selectors:** Adjust table selectors based on actual HTML structure
3. **Add Date Filtering:** Implement logic to filter games by week
4. **Set Up Automation:** Schedule regular scraping
5. **Build Integration:** Connect to your application or database

## Additional Resources

- BeautifulSoup Documentation: https://www.crummy.com/software/BeautifulSoup/
- Playwright Python: https://playwright.dev/python/
- Pandas Documentation: https://pandas.pydata.org/
- Web Scraping Best Practices: https://www.scrapingbee.com/blog/
