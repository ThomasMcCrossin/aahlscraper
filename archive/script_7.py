
# Create a quick reference cheat sheet

cheat_sheet = """
# QUICK START GUIDE - Amherst Adult Hockey Scraper

## 🚀 Quick Start (3 Steps)

### Step 1: Run Diagnostic
```bash
python diagnostic_check.py
```
This will tell you which scraping method to use.

### Step 2: Install Dependencies

**If diagnostic recommends BeautifulSoup:**
```bash
pip install requests beautifulsoup4 pandas lxml
```

**If diagnostic recommends Playwright:**
```bash
pip install playwright pandas
playwright install chromium
```

### Step 3: Run Scraper

**BeautifulSoup version:**
```bash
python amherst_hockey_scraper.py
```

**Playwright version:**
```bash
python amherst_hockey_scraper_playwright.py
```

## 📦 Output Files

After running, you'll get:
- `schedule.json` - All games
- `recent_games.json` - Last week's games  
- `current_week_games.json` - This week's games
- `player_stats.json` - Player statistics
- `standings.json` - Team standings
- `.csv` versions of all files

## 🔧 Customization Examples

### Get specific date range:
```python
from amherst_hockey_scraper import AmherstHockeyScraper
from datetime import datetime, timedelta

scraper = AmherstHockeyScraper()

# Last 2 weeks
recent = scraper.get_recent_games(weeks=2)

# Next 2 weeks (requires custom filtering)
schedule = scraper.scrape_schedule()
# Filter for future dates...
```

### Change team:
```python
scraper = AmherstHockeyScraper(team_id="YOUR_TEAM_ID")
```

### Sort stats differently:
```python
stats = scraper.scrape_stats(sort_by='goals')  # or 'assists', 'points'
```

## 🐛 Troubleshooting

**Problem:** Empty data returned
**Solution:** Run diagnostic - probably need Playwright

**Problem:** Connection timeout
**Solution:** Check internet, try again, increase timeout:
```python
scraper.session.get(url, timeout=30)
```

**Problem:** Wrong data structure
**Solution:** Inspect actual HTML, adjust selectors in code

## 📚 Key Files Reference

| File | Purpose |
|------|---------|
| `diagnostic_check.py` | Analyze website, recommend approach |
| `amherst_hockey_scraper.py` | Main scraper (BeautifulSoup) |
| `amherst_hockey_scraper_playwright.py` | Alternative scraper (Playwright) |
| `IMPLEMENTATION_GUIDE.md` | Full documentation |
| `sample_output_structure.json` | Example outputs |

## 💡 Pro Tips

1. **Run diagnostic first** - saves time debugging
2. **Start with BeautifulSoup** - it's much faster
3. **Add delays** - be nice to the server: `time.sleep(2)`
4. **Cache results** - don't re-scrape unnecessarily  
5. **Validate data** - check for empty/missing fields
6. **Handle errors** - always use try-except blocks

## 🔄 Automation Examples

**Daily scraping (cron):**
```bash
0 6 * * * cd /path/to/scraper && python amherst_hockey_scraper.py
```

**Python scheduler:**
```python
import schedule
import time

def job():
    scraper = AmherstHockeyScraper()
    scraper.scrape_schedule()

schedule.every().day.at("06:00").do(job)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 🌐 Ubuntu Server Deployment

Since you use Ubuntu servers, here's a quick setup:

```bash
# Install Python dependencies
sudo apt update
sudo apt install python3 python3-pip

# Install scraper dependencies
pip3 install requests beautifulsoup4 pandas lxml

# Optional: If you need Playwright
pip3 install playwright
playwright install --with-deps chromium

# Set up cron job
crontab -e
# Add: 0 6 * * * /usr/bin/python3 /path/to/amherst_hockey_scraper.py

# Or use systemd timer for better control
```

## 🔗 Integration with Your Stack

**Cloudflare Workers:**
```javascript
// Call the scraper via HTTP
export default {
  async fetch(request) {
    // Trigger Python scraper on your Ubuntu server
    const response = await fetch('YOUR_SERVER/scrape-endpoint');
    const data = await response.json();
    return new Response(JSON.stringify(data));
  }
}
```

**REST API Wrapper (Flask):**
```python
from flask import Flask, jsonify
from amherst_hockey_scraper import AmherstHockeyScraper

app = Flask(__name__)

@app.route('/api/schedule')
def schedule():
    scraper = AmherstHockeyScraper()
    return jsonify(scraper.scrape_schedule())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

## 📞 Need Help?

1. Check `IMPLEMENTATION_GUIDE.md` for detailed docs
2. Run `diagnostic_check.py` to identify issues
3. Check error messages and adjust selectors
4. Verify website structure hasn't changed

## ⚡ Performance Tips

- Use sessions for multiple requests: `session = requests.Session()`
- Scrape in parallel: `ThreadPoolExecutor` for multiple pages
- Cache results: Don't scrape more than once per hour
- Use BeautifulSoup when possible: 10-20x faster than Playwright

---

**Last Updated:** November 2025
**Version:** 1.0
"""

with open('QUICK_START.md', 'w') as f:
    f.write(cheat_sheet)

print("✅ Created: QUICK_START.md")
print("\n" + "="*80)
print("COMPLETE SOLUTION PACKAGE")
print("="*80)
print("\n📁 Core Scraper Files:")
print("  1. amherst_hockey_scraper.py (BeautifulSoup - Fast)")
print("  2. amherst_hockey_scraper_playwright.py (Playwright - JS support)")
print("  3. diagnostic_check.py (Run this first!)")

print("\n📚 Documentation:")
print("  4. IMPLEMENTATION_GUIDE.md (Complete guide)")
print("  5. QUICK_START.md (Quick reference)")
print("  6. sample_output_structure.json (Example outputs)")

print("\n📊 Reference Files:")
print("  7. scraping_approaches_comparison.csv (Approach comparison)")

print("\n🎯 Getting Started:")
print("  Step 1: Run 'python diagnostic_check.py'")
print("  Step 2: Follow the recommendation")
print("  Step 3: Get your JSON/CSV files!")

print("\n" + "="*80)
