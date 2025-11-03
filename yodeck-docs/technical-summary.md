# AAHL Yodeck Display - Technical Summary

## Project Overview

Transform your AAHL scraper data into a professional, auto-rotating hockey statistics display for your canteen digital signage using Yodeck.

## Components

### 1. **index.html** (Yodeck Display App)
**Type:** Single-file HTML5 application  
**Size:** ~15 KB (fully self-contained)  
**Platform:** Yodeck Players (Raspberry Pi 3/4)

**Features:**
- 4-section rotating display (15 seconds each)
  - Team Standings
  - Top 20 Scorers  
  - Last 10 Days Results
  - Next 10 Days Games
- Professional sports theme (blue/white colors)
- Full-screen responsive layout
- No external dependencies
- Cross-browser compatible

**Technical Details:**
- Pure HTML5/CSS3/JavaScript
- Embedded styling (no external CSS)
- Local data rendering (fast, reliable)
- Touch-friendly interface (optional)
- Print-friendly layout

### 2. **aahl_yodeck_processor.py** (Data Processor)
**Type:** Python 3 utility  
**Dependencies:** Standard library (json, csv, re, pathlib, datetime)

**Functions:**
- Load scraper output (JSON or CSV format)
- Apply name corrections
  - "Meathead" → "Marshall"
  - "Mccrossin" → "McCrossin"
- Filter games for Amherst only
  - Upcoming: next 10 calendar days
  - Recent: last 10 calendar days
- Sort standings and scorers
- Generate timestamped output
- Export to `yodeck_display.json`

**Input:** AAHL scraper output files
- `data/schedule.json` or `.csv`
- `data/player_stats.json` or `.csv`
- `data/standings.json` or `.csv`

**Output:** `data/yodeck_display.json`
```json
{
  "timestamp": "ISO-8601 datetime",
  "standings": [...],
  "top_scorers": [...],
  "recent_results": [...],
  "upcoming_games": [...]
}
```

### 3. **aahl_yodeck_setup.py** (Deployment Helper)
**Type:** Python 3 automation script  
**Commands:**
- `full` - Complete setup with validation
- `check` - Verify files and data
- `process` - Run data processor
- `zip` - Create Yodeck-ready ZIP
- `preview` - Show data summary

### 4. **Documentation**
- `quick-start.md` - 2-minute setup guide
- `yodeck-integration-guide.md` - Complete documentation
- `TECHNICAL_SUMMARY.md` - This file

## Data Flow Architecture

```
┌─────────────────────────┐
│   AAHL Website          │
│   (amherstaad.com)      │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  aahlscraper            │
│  HTTP Backend           │
│  (BeautifulSoup)        │
└────────────┬────────────┘
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
  schedule    player_stats   standings
  (JSON)      (JSON)         (JSON)
  
┌────────────────────────────────────┐
│  aahl_yodeck_processor.py          │
│  - Load data                       │
│  - Apply name corrections          │
│  - Filter Amherst games            │
│  - Sort & rank                     │
│  - Generate JSON export            │
└────────────┬───────────────────────┘
             │
             ▼
  ┌─────────────────────────┐
  │ yodeck_display.json     │
  │ (formatted data)        │
  └────────────┬────────────┘
               │
               ▼
  ┌──────────────────────────────┐
  │ Yodeck Player               │
  │ (Raspberry Pi)              │
  │ ┌────────────────────────┐   │
  │ │ index.html             │   │
  │ │ (Display app)          │   │
  │ └──────────┬─────────────┘   │
  │            │                  │
  │            ▼                  │
  │ ┌────────────────────────┐   │
  │ │ Canteen Display        │   │
  │ │ (4K/HD Monitor)        │   │
  │ └────────────────────────┘   │
  └──────────────────────────────┘
```

## Installation & Deployment

### Prerequisites
- Python 3.7+
- AAHL scraper installed and working
- Yodeck account with at least one player
- Internet connection for Yodeck portal

### Deployment Steps

1. **Prepare Data (5 min)**
   ```bash
   cd /path/to/aahlscraper
   python scripts/aahl_cli.py scrape --backend http
   ```

2. **Process Data (1 min)**
   ```bash
   python aahl_yodeck_processor.py
   # or
   python aahl_yodeck_setup.py process
   ```

3. **Create Deployment Package (1 min)**
   ```bash
   python aahl_yodeck_setup.py zip
   # Generates: aahl_display.zip
   ```

4. **Upload to Yodeck (5 min)**
   - Log into Yodeck portal
   - Custom Apps → Add New HTML App
   - Upload: aahl_display.zip
   - Click Save → Push Changes

5. **Add to Playlist (2 min)**
   - Playlists → Add AAHL Hockey Display app
   - Set duration: 60 seconds
   - Save and Push

**Total Setup Time: ~20 minutes**

## Automation & Updates

### Cron Job Setup
```bash
# Update every 2 hours
0 */2 * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http && python aahl_yodeck_processor.py >> /tmp/aahl_update.log 2>&1

# Daily at 6 AM
0 6 * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http && python aahl_yodeck_processor.py >> /tmp/aahl_daily.log 2>&1
```

### Manual Updates
```bash
python aahl_yodeck_setup.py full
```

## Name Corrections

The processor applies these regex-based corrections:

| Original Pattern | Replacement | Scope |
|-----------------|-------------|-------|
| Meathead | Marshall | Player names, team names |
| Mccrossin | McCrossin | Player names, team names |

**Note:** Corrections are case-insensitive during matching but preserve intended capitalization in output.

### Adding New Corrections

Edit `aahl_yodeck_processor.py`:

```python
NAME_CORRECTIONS = {
    r'Meathead': 'Marshall',
    r'Mccrossin': 'McCrossin',
    r'NewPattern': 'Corrected Name',  # Add here
}
```

## Performance & Scalability

| Metric | Performance |
|--------|-------------|
| App Load Time | <1 second |
| Data Processing | <2 seconds |
| Data Update Frequency | Every 30 min - 2 hours |
| Storage (App) | ~15 KB |
| Storage (Data) | ~50-100 KB |
| Network Requirements | HTTP only |
| Display Resolution | 1080p - 4K |

## Error Handling

### Processor Error Handling
- Missing files: Alert user to run scraper
- Invalid date formats: Skip malformed records
- Missing standings/stats: Continue with partial data
- Encoding issues: UTF-8 fallback

### Display Error Handling
- Missing data sections: Show "No data available"
- Load failures: Retry with timeout
- Date parsing: Display raw date if format unknown

## Customization Options

### Display Timing
```javascript
const SECTION_DURATION = 15000; // milliseconds per section
```

### Colors/Theme
```css
--primary-color: #003478;      /* Blue */
--secondary-color: #FFFFFF;    /* White */
--accent-color: #FF6B35;       /* Orange */
--text-color: #222222;         /* Dark gray */
```

### Games Filter
Edit processor to:
- Change location filter (currently "amherst")
- Adjust date ranges (currently ±10 days)
- Filter by team name

### Display Sections
Comment out sections in HTML to hide them:
```javascript
const sections = [
  'standings',      // Team standings
  'scorers',        // Top 20 scorers
  'recent',         // Last 10 days
  'upcoming'        // Next 10 days
];
```

## Troubleshooting

### Common Issues & Solutions

**Blank screen on display**
- Cause: Missing yodeck_display.json
- Solution: Run processor, check data directory

**Old data showing**
- Cause: Scraper not running
- Solution: Run scraper manually, check cron job

**Wrong player names**
- Cause: Corrections not applied
- Solution: Verify processor ran, check NAME_CORRECTIONS

**Games not filtering to Amherst**
- Cause: Location data not containing "amherst"
- Solution: Check raw schedule data, update filter logic

**ZIP file not accepted by Yodeck**
- Cause: Wrong folder structure
- Solution: ZIP should contain index.html in root, not in subfolder

## Integration Points

### AAHL Scraper
- Depends on: `scripts/aahl_cli.py`, `data/` directory
- Provides: JSON/CSV files with schedule, stats, standings

### Yodeck Platform
- Upload: `aahl_display.zip` HTML app
- Integration: REST API available for programmatic control
- Updates: Automatic via playlist management

### Data Sources
- Input: AAHL website (via scraper)
- Processing: Local Python script
- Output: JSON file for display

## Security Considerations

- ✅ No external API calls from display app
- ✅ No credentials stored in app
- ✅ All data is public AAHL website data
- ✅ Runs completely offline on Yodeck player
- ✅ No data persistence (ephemeral display)

## Future Enhancements

Potential additions:
- 🔮 Real-time game score updates
- 🔮 Player headshots from scraper
- 🔮 Team logos and branding
- 🔮 Custom playlist scheduling
- 🔮 Multi-display synchronization
- 🔮 Weather forecast integration
- 🔮 Announcements/news ticker

## Support & Maintenance

**Version:** 1.0  
**Last Updated:** November 2, 2025  
**Maintainer:** Thomas McCrossin  
**Repository:** github.com/ThomasMcCrossin/aahlscraper

### Issues & Feedback
1. Check `yodeck-integration-guide.md` troubleshooting section
2. Review AAHL scraper documentation
3. Check Yodeck support: https://www.yodeck.com/docs/

### Updates
Check GitHub repository for:
- Bug fixes
- New features
- Documentation updates
- Community contributions

---

**Files Included:**
- `index.html` - Yodeck display app (main deliverable)
- `aahl_yodeck_processor.py` - Data processor
- `aahl_yodeck_setup.py` - Setup automation
- `quick-start.md` - Quick start guide
- `yodeck-integration-guide.md` - Full documentation
- `TECHNICAL_SUMMARY.md` - This document
