# AAHL Yodeck Display - Complete Package Contents

## 📦 What You're Getting

A complete, production-ready solution to display AAHL hockey statistics on your Yodeck canteen display. This package includes the display app, data processor, setup automation, and comprehensive documentation.

---

## 📄 Files Breakdown

### Core Application Files

#### 1. **index.html** (Main Yodeck App)
- **Type:** HTML5 Display Application
- **Size:** ~15 KB
- **Purpose:** The actual app that displays on your Yodeck player
- **What to do with it:** Upload to Yodeck as an HTML custom app
- **Format:** Single self-contained file with embedded CSS and JavaScript
- **Browser:** Works on any modern browser, optimized for Yodeck players

**Key features:**
- 4-section rotating display (standings, scorers, results, upcoming)
- 15-second auto-rotation per section
- Professional sports theme
- Fully responsive (works at any resolution)
- No external dependencies or CDN calls
- Ready to deploy immediately

**How it works:**
1. Display app loads on Yodeck player
2. App expects data in JSON format
3. Auto-rotates through 4 sections
4. Updates when new data is available

---

### Data Processing Files

#### 2. **aahl_yodeck_processor.py** (Data Transformation)
- **Type:** Python 3 utility script
- **Dependencies:** Standard library only (json, csv, re, pathlib, datetime)
- **Purpose:** Convert raw AAHL scraper output to Yodeck-ready format
- **What to do with it:** Run after your AAHL scraper completes

**Key functions:**
- Loads scraper output (JSON or CSV files)
- Applies name corrections (Meathead → Marshall, Mccrossin → McCrossin)
- Filters games to show only Amherst-related
- Calculates top scorers (rank by points)
- Separates games into "recent" and "upcoming"
- Generates timestamped JSON export
- Handles missing/malformed data gracefully

**How to use:**
```bash
# Make sure you're in the AAHL scraper directory
python aahl_yodeck_processor.py

# Or with explicit path
python /path/to/aahl_yodeck_processor.py
```

**Input files required:**
- `data/schedule.json` or `data/schedule.csv`
- `data/player_stats.json` or `data/player_stats.csv`
- `data/standings.json` or `data/standings.csv`

**Output file generated:**
- `data/yodeck_display.json` (ready for display app)

---

#### 3. **aahl_yodeck_setup.py** (Automation & Deployment Helper)
- **Type:** Python 3 automation script
- **Dependencies:** Standard library only
- **Purpose:** Automate the entire setup process
- **What to do with it:** Run to set up and validate everything

**Available commands:**
```bash
python aahl_yodeck_setup.py full      # Complete setup with validation
python aahl_yodeck_setup.py check     # Check if all requirements are met
python aahl_yodeck_setup.py process   # Run data processor only
python aahl_yodeck_setup.py zip       # Create ZIP for Yodeck upload
python aahl_yodeck_setup.py preview   # Show preview of processed data
```

**What it does:**
1. Validates required files exist (index.html, processor script)
2. Checks AAHL scraper data is available
3. Runs the processor
4. Creates deployment ZIP file
5. Shows data preview
6. Provides next steps

---

### Documentation Files

#### 4. **README.md** (Project Overview)
- **Type:** Markdown documentation
- **Audience:** Everyone (start here if new)
- **Content:** Project overview, features, quick start
- **Length:** ~2 pages
- **When to read:** First thing - gets you oriented

**Contains:**
- Feature overview
- Quick start guide (5 minutes)
- File reference table
- Troubleshooting basics
- Customization tips
- Support information

---

#### 5. **quick-start.md** (Fast Setup Guide)
- **Type:** Markdown documentation
- **Audience:** In a hurry developers
- **Content:** Bare minimum to get running
- **Length:** ~1 page
- **When to read:** If you want to skip details and just deploy

**Contains:**
- 30-second summary
- 2-minute setup procedure
- Key features
- Auto-update cron command
- Quick troubleshooting

---

#### 6. **yodeck-integration-guide.md** (Detailed Setup)
- **Type:** Markdown documentation
- **Audience:** Detailed technical users
- **Content:** Step-by-step comprehensive guide
- **Length:** ~4 pages
- **When to read:** When you need all the details

**Covers:**
- Overview of what you're getting
- Step-by-step setup instructions
- Two upload options (portal vs. manual)
- Automated update workflow (cron jobs)
- Name corrections reference
- Customization options (timing, colors, sections)
- Extensive troubleshooting guide
- Advanced: Real-time integration with REST API

---

#### 7. **technical-summary.md** (Architecture & Deep Dive)
- **Type:** Markdown documentation
- **Audience:** Developers, systems administrators
- **Content:** Technical architecture and implementation details
- **Length:** ~5 pages
- **When to read:** When you need to understand how it works

**Covers:**
- Component descriptions
- Data flow architecture (with diagram)
- Installation & deployment procedures
- Automation setup
- Performance metrics
- Error handling
- Customization technical details
- Security considerations
- Future enhancement ideas

---

#### 8. **FILE_MANIFEST.md** (This Document)
- **Type:** Markdown documentation
- **Audience:** Package administrators
- **Content:** Complete inventory of all files
- **Length:** ~6 pages
- **When to read:** To understand what each file does

---

## 🔄 How Everything Works Together

```
┌─────────────────────────────────────────────────────────────┐
│                      WORKFLOW DIAGRAM                        │
└─────────────────────────────────────────────────────────────┘

Step 1: Generate Data
  ↓
Run: python scripts/aahl_cli.py scrape --backend http
Produces: schedule.json, player_stats.json, standings.json
  ↓

Step 2: Process Data  
  ↓
Run: python aahl_yodeck_processor.py
Produces: yodeck_display.json (corrected, filtered, formatted)
  ↓

Step 3: Create Deployment Package
  ↓
Run: python aahl_yodeck_setup.py zip
Produces: aahl_display.zip (contains index.html)
  ↓

Step 4: Deploy to Yodeck
  ↓
Upload: aahl_display.zip to Yodeck Portal
Add: AAHL Hockey Display app to canteen playlist
  ↓

Step 5: Display on Canteen Screen
  ↓
Yodeck Player loads: index.html
Displays: 4 rotating sections (standings, scorers, results, games)
Refreshes: When new data is available
```

---

## 📋 File Usage Reference

### Initial Setup (One-Time)
1. Read: `README.md` - Get overview
2. Read: `quick-start.md` - Understand basic flow
3. Run: `aahl_yodeck_setup.py full` - Complete setup
4. Reference: `yodeck-integration-guide.md` - If you hit issues

### Ongoing Operations
- Run: `aahl_yodeck_setup.py process` - Weekly or bi-weekly data updates
- Or: Set up cron job from `quick-start.md`
- Or: Just re-run `aahl_yodeck_processor.py` after scraper runs

### Customization/Troubleshooting
- Edit: `index.html` - Change display design/timing
- Edit: `aahl_yodeck_processor.py` - Add name corrections
- Reference: `yodeck-integration-guide.md` - Comprehensive troubleshooting
- Reference: `technical-summary.md` - Deep technical details

---

## 🎯 Quick Navigation Guide

**I want to...**

| Need | File to Read |
|------|--------------|
| Get started quickly | `quick-start.md` |
| Understand the full setup | `yodeck-integration-guide.md` |
| Learn technical architecture | `technical-summary.md` |
| See all project features | `README.md` |
| Know what files do what | `FILE_MANIFEST.md` (this file) |
| Just run the setup | `aahl_yodeck_setup.py full` |
| Add new name corrections | Edit `aahl_yodeck_processor.py` |
| Change display design | Edit `index.html` CSS section |
| Debug data issues | Run `aahl_yodeck_setup.py preview` |
| Automate updates | Use cron commands from docs |

---

## 📊 Data Flow Summary

### Input (From AAHL Scraper)
```
schedule.json/csv
  ├─ Game dates
  ├─ Home/away teams
  ├─ Scores
  └─ Locations

player_stats.json/csv
  ├─ Player names
  ├─ Team affiliations
  ├─ Goals
  ├─ Assists
  └─ Points

standings.json/csv
  ├─ Team names
  ├─ Wins
  ├─ Losses
  └─ Points
```

### Processing (By aahl_yodeck_processor.py)
- Load all three files
- Apply name corrections to all player/team names
- Filter schedule for Amherst games only
  - Past 10 days → recent_results
  - Next 10 days → upcoming_games
- Sort standings by points
- Sort player stats by points (create ranking)
- Combine into single JSON output

### Output (yodeck_display.json)
```json
{
  "timestamp": "ISO-8601 datetime",
  "standings": [
    {"team": "Team Name", "wins": 10, "losses": 5, "points": 20},
    ...
  ],
  "top_scorers": [
    {"rank": 1, "player_name": "Name", "team": "Team", "points": 25},
    ...
  ],
  "recent_results": [
    {"date": "2025-11-01", "home_team": "Team", "away_team": "Team", "home_score": 3, "away_score": 2},
    ...
  ],
  "upcoming_games": [
    {"date": "2025-11-05", "time": "8:00 PM", "home_team": "Team", "away_team": "Team", "location": "Amherst Ice Arena"},
    ...
  ]
}
```

### Display (In index.html)
- Parses JSON data
- Displays in 4 rotating sections
- Each section 15 seconds
- Shows standings, top scorers, results, upcoming games
- Updates when new data is available

---

## 🔐 Security & Privacy

✅ **No external API calls** - Display app runs completely locally
✅ **No credentials stored** - Nothing sensitive in the app
✅ **Public data only** - All data is from public AAHL website
✅ **No data persistence** - Display doesn't store anything
✅ **Firewall friendly** - Only needs to connect to Yodeck portal

---

## 🚀 Deployment Checklist

- [ ] Read `README.md` - Understand what this is
- [ ] Run AAHL scraper - Generate raw data
- [ ] Run `aahl_yodeck_setup.py full` - Complete setup validation
- [ ] Verify `aahl_display.zip` created successfully
- [ ] Log into Yodeck portal
- [ ] Upload ZIP as HTML custom app
- [ ] Add app to canteen display playlist
- [ ] Click "Push Changes" in Yodeck
- [ ] Wait 60 seconds for player to sync
- [ ] Verify display shows hockey stats on canteen screen
- [ ] Set up cron job for automatic updates (optional)

---

## 🆘 Support Quick Links

| Issue | Check |
|-------|-------|
| App not showing | `yodeck-integration-guide.md` Troubleshooting |
| Data not updating | Run processor manually, check logs |
| Wrong names showing | Verify processor ran, check NAME_CORRECTIONS |
| Can't upload to Yodeck | Check ZIP structure in `yodeck-integration-guide.md` |
| Need more details | Read `technical-summary.md` |

---

## 📞 Getting Help

1. **Check the docs** - Most answers are in the 3 main guides
2. **Run diagnostics** - `aahl_yodeck_setup.py check`
3. **Check logs** - Look for error messages
4. **Review AAHL scraper docs** - https://github.com/ThomasMcCrossin/aahlscraper
5. **Yodeck support** - https://www.yodeck.com/

---

## ✅ Verification Checklist

After setup, verify:

- [ ] `index.html` exists and is readable
- [ ] `aahl_yodeck_processor.py` exists and is executable
- [ ] `aahl_yodeck_setup.py` exists and is executable
- [ ] `data/yodeck_display.json` was created by processor
- [ ] ZIP file `aahl_display.zip` created successfully
- [ ] App uploaded to Yodeck
- [ ] App appears in Custom Apps list
- [ ] Canteen display screen shows hockey stats
- [ ] Display auto-rotates through 4 sections
- [ ] Player names are corrected (Marshall, McCrossin)
- [ ] Only Amherst games shown in upcoming/recent

---

## 🎓 Learning Path

**If you're new to this system:**
1. Start: `README.md`
2. Then: `quick-start.md`
3. Execute: `aahl_yodeck_setup.py full`
4. Reference: `yodeck-integration-guide.md` as needed

**If you're experienced:**
1. Skim: `README.md`
2. Execute: `aahl_yodeck_setup.py full`
3. Reference: `technical-summary.md` for advanced topics

**If you need to customize:**
1. Review: `yodeck-integration-guide.md` Customization section
2. Review: `technical-summary.md` Architecture section
3. Edit: `index.html` or `aahl_yodeck_processor.py`

---

**Version:** 1.0
**Last Updated:** November 2, 2025
**Status:** Production Ready ✅

---

## Additional Resources

- AAHL Scraper: https://github.com/ThomasMcCrossin/aahlscraper
- Yodeck Documentation: https://www.yodeck.com/docs/
- Yodeck Custom Apps: https://www.yodeck.com/docs/user-manual/introduction-to-custom-widgets/
