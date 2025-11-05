# AAHL Yodeck Display - Current Status & Context

**Last Updated**: November 3, 2025, 9:55 AM AST
**Repository**: https://github.com/ThomasMcCrossin/aahlscraper

---

## Quick Status Summary

### ✅ **WORKING**
1. **Team Standings** - Fully functional
   - Shows correct W-L-Pts (5-1 with 10 points, etc.)
   - All 5 teams displaying correctly

2. **Top 20 Scorers** - Data is correct, display needs work
   - Player names: ✅ FIXED (was showing "undefined", now shows actual names)
   - Points: ✅ Working (22, 18, 13 pts showing correctly)
   - Teams: ✅ Working

3. **GitHub Actions** - Runs 3x daily + game-night bursts
   - Scrapes AAHL website on the 8 AM / 12 PM / 4 PM Atlantic cadence
   - Adds 5-minute refreshes during Tue/Sun evening games
   - Schedule auto-adjusts between AST/ADT to keep local times accurate
   - Processes data with name corrections
   - Commits to repo
   - Last successful run: Today

### ⚠️ **PARTIALLY WORKING**
1. **Recent Results & Upcoming Games**
   - Empty arrays in yodeck_display.json
   - Processor's `filter_amherst_games()` is not populating data
   - Schedule data EXISTS but dates are empty strings

### ❌ **NEEDS FIXING**
1. **Schedule Dates** - Most critical issue
   - Dates showing as empty strings in schedule.json
   - Date headers ("Tuesday, October 28, 2025") not being captured
   - Scraper needs to detect gray header rows in HTML table

2. **Font Sizes** - Display too large for 1080p
   - Only showing 6 players instead of 20
   - Text is HUGE (current base: 48px)
   - Need to reduce to ~18-24px for 1080p
   - Viewing distance consideration needed

---

## Files Changed Today

### Modified Files
1. `aahl_yodeck_processor.py` - Fixed standings & player points parsing
2. `src/aahlscraper/http_scraper.py` - Attempted schedule date fix (WIP)
3. `index.html` - Fixed field name mappings for player names & games
4. `.gitignore` - Added .env exclusion
5. `README.md` - Updated with GitHub Actions info

### Key Commits
- `856a83d` - Fix processor to correctly parse standings and player points
- `2b7002e` - Attempt to fix schedule date parsing (WIP)
- Latest - Fixed index.html field name mappings

---

## Data Structure Reference

### yodeck_display.json (Current Structure)
```json
{
  "timestamp": "2025-11-03T09:29:16.085147",
  "standings": [
    {"team": "Maltby Sports", "wins": 5, "losses": 1, "points": 10}
  ],
  "top_scorers": [
    {"no": "98", "name": "Bridge, Issac", "team": "Maltby Sports", "points": 22, "rank": 1}
  ],
  "recent_results": [],  // ← EMPTY - NEEDS FIX
  "upcoming_games": []   // ← EMPTY - NEEDS FIX
}
```

### schedule.json (Current Structure)
```json
{
  "time": "8:45 pm",
  "away": "Maltby Sports",
  "": "4L",              // ← Score in unnamed field
  "home": "Ultramar",
  "location": "Amherst",
  "date": ""             // ← EMPTY - THIS IS THE PROBLEM
}
```

**Expected structure** (from AAHL website screenshot):
- Gray header rows: "Tuesday, October 28, 2025"
- Week headers: "Mon, 10/27/25 to Sun, 11/2/25 Week 3"
- Game rows: Time, Away Team, Score, vs, Home Team, Score, Location

---

## Critical Issues to Fix

### Issue #1: Schedule Dates Not Captured
**Problem**: Date headers are in separate table rows but scraper isn't detecting them

**Location**: `src/aahlscraper/http_scraper.py:64-118`

**Current Logic** (lines 89-96):
```python
# Check if this is a date header row (single cell with a date like "Tuesday, October 28, 2025")
if len(cells) == 1 and any(month in cells[0] for month in ['January', 'February', ...]):
    current_date = cells[0]
    continue  # Skip to next row
```

**Why it's failing**:
- `_extract_rows()` might be combining cells differently than expected
- Date headers may have different HTML structure (th vs td, colspan, etc.)
- Need to debug actual HTML structure from AAHL website

**Next Steps**:
1. Fetch schedule page HTML and examine actual table structure
2. Check if date headers are in `<th>` vs `<td>`
3. Check for rowspan/colspan attributes
4. Adjust detection logic accordingly
5. Test with: `python scripts/aahl_cli.py scrape --backend http --targets schedule`

### Issue #2: Processor Not Populating Games
**Problem**: `filter_amherst_games()` returns empty arrays

**Location**: `aahl_yodeck_processor.py:98-144`

**Current Logic**:
- Filters for `is_amherst_location` (checks location field for "amherst")
- Splits by whether score exists (has_result)
- Currently finding 57 Amherst games in schedule but NOT adding to arrays

**Why it's failing**:
- Dates are empty strings, so game_copy['date'] is empty
- Processor might be silently failing without dates
- Need to handle games without dates

**Fix Options**:
A. Populate games WITHOUT dates (use time as identifier)
B. Fix scraper first, then processor will work
C. Both - make processor work with/without dates

### Issue #3: Font Sizes Too Large
**Problem**: Only 6 players visible, text huge on 1080p screen

**Location**: `index.html:8-298` (CSS section)

**Current Settings**:
```css
body { font-size: 1.5em; }
.header h1 { font-size: 3.5em; }   // ~84px
.section-title { font-size: 2.8em; }  // ~67px
.scorer-card { font-size: 1.8em; }  // ~43px
```

**Recommended Changes for 1080p**:
```css
body { font-size: 1em; }  // Base 16px
.header h1 { font-size: 2.5em; }   // ~40px
.section-title { font-size: 2em; }  // ~32px
.scorer-card { font-size: 1.2em; }  // ~19px
```

**Goal**: Fit 20 players in 2-column grid on 1080p screen

---

## What User Saw (Screenshots Analysis)

### Screenshot 1: Top 20 Scorers
- ✅ Points showing correctly (22, 18, 13)
- ❌ Names showing "undefined" (FIXED in latest index.html)
- ⚠️ Only 6 players visible (need smaller fonts)

### Screenshot 2: Recent Results
- ❌ "INVALID DATE" (empty date strings)
- ❌ "undefined - undefined" (FIXED field mappings)

### Screenshot 3: Upcoming Games
- ❌ "INVALID DATE"
- ❌ "undefined vs undefined" (FIXED field mappings)
- ✅ Time showing (8:45 pm)
- ✅ Location showing (Amherst)

### Screenshot 4: Team Standings
- ✅ PERFECT - Working correctly!

---

## Next Session TODO

### Priority 1: Fix Schedule Dates (CRITICAL)
1. Debug HTML table structure from AAHL website
2. Update `_extract_rows()` or detection logic
3. Test scraper captures dates correctly
4. Verify dates populate in schedule.json

### Priority 2: Fix Processor (CRITICAL)
1. Update `filter_amherst_games()` to handle empty dates
2. Use time + teams as game identifier if no date
3. Populate recent_results and upcoming_games arrays
4. Test processor outputs games correctly

### Priority 3: Reduce Font Sizes (HIGH)
1. Update CSS in index.html
2. Reduce all font sizes by ~40%
3. Test fits 20 players in grid
4. Test readable from ~10-15 feet (1080p screen)

### Priority 4: Test & Deploy
1. Run full scrape + process pipeline
2. Verify all 4 sections display correctly
3. Create new aahl_display.zip
4. Upload to Yodeck for testing

---

## Key Commands

### Run Scraper
```bash
source venv/bin/activate
python scripts/aahl_cli.py scrape --backend http
```

### Run Processor
```bash
source venv/bin/activate
python aahl_yodeck_processor.py
```

### Test Specific Target
```bash
python scripts/aahl_cli.py scrape --backend http --targets schedule
```

### Create Deployment ZIP
```bash
python3 -c "import zipfile; z = zipfile.ZipFile('aahl_display.zip', 'w', zipfile.ZIP_DEFLATED); z.write('index.html', 'index.html'); z.close()"
```

### Check Data
```bash
cat data/yodeck_display.json | python3 -m json.tool | less
cat data/schedule.json | head -50
```

---

## File Locations

- **Main display**: `/home/tom/aahlscraper/index.html`
- **Processor**: `/home/tom/aahlscraper/aahl_yodeck_processor.py`
- **Scraper**: `/home/tom/aahlscraper/src/aahlscraper/http_scraper.py`
- **Data output**: `/home/tom/aahlscraper/data/`
- **Deployment ZIP**: `/home/tom/aahlscraper/aahl_display.zip`
- **Screenshots**: `/home/tom/aahlscraper/FilesToProcess/*.png`

---

## GitHub Actions Setup

- **Workflow**: `.github/workflows/scrape-and-deploy.yml`
- **Schedule**: Every 2 hours (UTC)
- **Permissions**: contents: write (enabled)
- **Status**: ✅ Working
- **Last run**: Successful
- **Data file**: Commits to `data/yodeck_display.json`

---

## Environment Setup

### Required
- Python 3.12+
- Virtual env at `/home/tom/aahlscraper/venv/`
- Dependencies: requests, beautifulsoup4, pandas

### Optional (NOT needed)
- Playwright (only if diagnostics recommend it)

### GitHub MCP
- Configured with PAT in `.env` (gitignored)
- Remote HTTP server at api.githubcopilot.com

---

## Known Working Solutions

### Standings Parsing
```python
# Parse wins/losses from 'record' field (e.g., "5-1")
record = team.get('record', '')
if record and '-' in record:
    parts = record.split('-')
    wins = int(parts[0])
    losses = int(parts[1])

# Parse points from 'pts' field
points = int(team.get('pts', 0))
```

### Player Points Parsing
```python
# Try 'pts' field first (most common)
if 'pts' in stat and stat['pts']:
    stat['points'] = int(stat['pts'])
# Calculate from g + a
elif 'g' in stat and 'a' in stat:
    goals = int(stat.get('g', 0) or 0)
    assists = int(stat.get('a', 0) or 0)
    stat['points'] = goals + assists
```

---

## Questions to Resolve

1. **Schedule date format**: What's the actual HTML structure?
2. **Font sizes**: What's readable from how far away on 1080p?
3. **Display duration**: How long should each section show? (currently 15 sec)
4. **Games to show**: Top 10? All Amherst games?
5. **Date handling**: Show games without dates, or wait for fix?

---

## Resources

- **AAHL Website**: https://amherstaadulthockey.ca/?page=schedule&team=DSMALL
- **GitHub Repo**: https://github.com/ThomasMcCrossin/aahlscraper
- **Yodeck Preview**: webpreview.yodeck.com (URLs in screenshots)
- **Claude MCP Docs**: https://docs.claude.com/en/docs/claude-code/

---

## Contact/Notes

- Timezone: Atlantic (AST/ADT = UTC-4)
- Screen: 1080p (1920x1080)
- GitHub Actions runs: Even hours UTC = Even-2 hours AST
- Name corrections working: "Meathead" → "Marshall"

---

**Status**: Ready to continue. Priorities are date fixing and font sizing.
