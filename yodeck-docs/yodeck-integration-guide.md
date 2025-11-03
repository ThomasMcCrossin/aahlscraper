# AAHL Yodeck Display Integration Guide

## Overview

This guide explains how to set up the AAHL Hockey League display app on your Yodeck digital signage system for the canteen display.

## What You're Getting

1. **Yodeck HTML5 App** (`index.html`) - A professional hockey statistics display that shows:
   - Team standings with wins/losses/points
   - Top 20 scorers ranked by points
   - Last 10 days of game results
   - Next 10 days of upcoming games (Amherst only)
   - Auto-rotating sections every 15 seconds
   - Professional sports display theme

2. **Data Processor Script** (`aahl_yodeck_processor.py`) - Python utility that:
   - Processes raw AAHL scraper data
   - Applies name corrections (Meathead → Marshall, Mccrossin → McCrossin)
   - Filters games to show only Amherst-related matches
   - Exports data in Yodeck-ready format

## Setup Steps

### Step 1: Prepare Your AAHL Scraper Data

First, run your existing AAHL scraper to generate the raw data files:

```bash
cd /path/to/aahlscraper
python scripts/aahl_cli.py scrape --backend http
```

This creates:
- `data/schedule.json` or `data/schedule.csv`
- `data/player_stats.json` or `data/player_stats.csv`
- `data/standings.json` or `data/standings.csv`

### Step 2: Process Data for Yodeck

Place the `aahl_yodeck_processor.py` script in your scraper directory and run it:

```bash
# From the aahlscraper directory
python aahl_yodeck_processor.py
```

This generates `data/yodeck_display.json` with all data properly formatted and name corrections applied.

Output example:
```json
{
  "timestamp": "2025-11-02T22:30:00",
  "standings": [
    {
      "team": "Amherst Hawks",
      "wins": 8,
      "losses": 2,
      "points": 16
    }
  ],
  "top_scorers": [
    {
      "rank": 1,
      "player_name": "Marshall MacDonald",
      "team": "Amherst Hawks",
      "points": 24
    }
  ],
  "recent_results": [...],
  "upcoming_games": [...]
}
```

### Step 3: Set Up the Yodeck App

#### Option A: Upload to Yodeck Portal (Recommended)

1. Create a ZIP file with the Yodeck app:
   ```bash
   # Create a folder with just the index.html
   mkdir aahl_display
   cp index.html aahl_display/
   
   # ZIP it (important: zip contents, not the folder)
   cd aahl_display
   zip -r ../aahl_display.zip index.html
   cd ..
   ```

2. Log into your Yodeck account
3. Go to **Custom Apps** section
4. Click **Add New HTML App**
5. Fill in the form:
   - **Name**: AAHL Hockey Display
   - **Icon**: Choose a sports icon
   - **Description**: Amherst Adult Hockey League standings, scores, and schedule
   - **Zoom Factor**: 100%
   - **Enable Chromium**: Disabled (not needed)
   - **Upload ZIP**: Select `aahl_display.zip`

6. Click **Save**
7. Click **Push Changes** to deploy to your screens

#### Option B: Manual Player Setup

If you have direct access to the Yodeck Player (Raspberry Pi):

1. SSH into the player
2. Navigate to the apps directory (usually `/home/yodeck/apps/`)
3. Create a new directory: `mkdir aahl_display`
4. Extract the ZIP file contents there
5. Restart the Yodeck service

### Step 4: Add to Your Playlist

1. In Yodeck Portal, go to **Playlists**
2. Create a new playlist or edit an existing one
3. Add the **AAHL Hockey Display** app
4. Set display duration (suggested: 60 seconds per full rotation, 15 seconds per section)
5. Drag it to the desired position in the playlist
6. Save and push changes

### Step 5: Data Update Workflow (Automated)

Set up a cron job to automatically update the Yodeck data:

```bash
# Add to your crontab (crontab -e)
# Update every 2 hours
0 */2 * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http > /tmp/aahl_scrape.log 2>&1 && python aahl_yodeck_processor.py >> /tmp/aahl_scrape.log 2>&1
```

Or for more frequent updates:

```bash
# Update every 30 minutes
*/30 * * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http && python aahl_yodeck_processor.py
```

## Name Corrections Applied

The data processor automatically applies these corrections:

| Original | Corrected |
|----------|-----------|
| Meathead | Marshall |
| Mccrossin | McCrossin |

These corrections are applied to:
- Player names in statistics
- Player names in scoring records
- Team names (if applicable)

## Customization

### Modify Display Timing

Edit the JavaScript in `index.html` to change section rotation:

```javascript
// Current: 15 seconds per section
const SECTION_DURATION = 15000; // milliseconds
```

### Change Colors/Theme

The app includes CSS variables for easy theming:

```css
--primary-color: #003478;     /* Deep blue */
--secondary-color: #FFFFFF;   /* White */
--accent-color: #FF6B35;      /* Orange accent */
```

### Customize Displayed Sections

The app rotates through these sections. To hide any section, modify the `sections` array in the HTML.

### Manual Data Update

If you don't want automated updates, you can manually update the data:

1. Run the scraper locally: `python scripts/aahl_cli.py scrape --backend http`
2. Process the data: `python aahl_yodeck_processor.py`
3. The data is formatted and ready in `data/yodeck_display.json`

## Troubleshooting

### App Not Showing Up on Yodeck Player

1. Ensure ZIP file was created correctly (index.html in root, not in a subfolder)
2. Push changes to your screens in the Yodeck portal
3. Check that the app appears in Custom Apps section
4. Verify player has internet connection and is receiving updates

### Data Not Updating

1. Check that the AAHL scraper runs successfully: `python scripts/aahl_cli.py diagnostics`
2. Verify `data/` directory has the three files: `schedule.json`, `player_stats.json`, `standings.json`
3. Run the processor manually: `python aahl_yodeck_processor.py`
4. Check for errors in the processor output

### Games Not Showing in Upcoming/Recent

The app filters for "Amherst" in:
- Home team name
- Away team name  
- Location/venue

Ensure your scraper data includes Amherst in these fields consistently.

### Names Not Corrected

The processor applies corrections during data generation. If corrections aren't showing:
1. Check the raw scraper data for exact spelling variations
2. Add new corrections to the `NAME_CORRECTIONS` dictionary in `aahl_yodeck_processor.py`
3. Re-run the processor

## Advanced: Real-Time Integration

For a fully automated workflow, you could:

1. Set up the AAHL scraper on an Ubuntu VM/server
2. Schedule hourly scraping with cron
3. Automatically generate `yodeck_display.json`
4. Use Yodeck's REST API to push updates to the player
5. The Yodeck app will refresh and display new data automatically

Yodeck REST API documentation: https://www.yodeck.com/docs/user-manual/introducing-yodecks-rest-api-seamless-integration-for-your-digital-signage-needs/

## Files Reference

| File | Purpose |
|------|---------|
| `index.html` | Yodeck display app (single HTML5 file with embedded CSS/JS) |
| `aahl_yodeck_processor.py` | Data processor script (process scraper output) |
| `yodeck-integration-guide.md` | This documentation |
| `data/yodeck_display.json` | Final formatted data (generated by processor) |

## Support & Updates

If you need to modify the display design or add new sections:

1. The HTML app is fully self-contained in `index.html`
2. All styling is in embedded CSS
3. No external dependencies required
4. Ready to deploy immediately to Yodeck

For AAHL scraper updates or issues, see: https://github.com/ThomasMcCrossin/aahlscraper

## Quick Commands Reference

```bash
# 1. Run scraper
python scripts/aahl_cli.py scrape --backend http

# 2. Process for Yodeck
python aahl_yodeck_processor.py

# 3. Create ZIP for upload
cd /path/with/index.html && zip -r aahl_display.zip index.html

# 4. View processed data
cat data/yodeck_display.json | python -m json.tool
```

---

**Last Updated**: November 2, 2025
**Version**: 1.0
