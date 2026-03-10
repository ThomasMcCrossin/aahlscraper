# AAHL Yodeck Quick Start

## 30-Second Summary

You have a **professional hockey stats display** ready for your canteen screen.

### What It Shows
- 🏒 Team standings (wins/losses/points)
- 🎯 Top 20 scorers
- 📊 Last 10 days of results
- 📅 Next 10 days of games (Amherst only)

### The Files You Need

1. **index.html** - Canonical production Yodeck app source
2. **aahl_yodeck_processor.py** - Run this to update the data
3. **yodeck-integration-guide.md** - Full setup documentation

Archived legacy variants and retired upload artifacts live in `archive/yodeck/` and should not be used for production uploads.

## Two-Minute Setup

### 1. Prepare Data
```bash
cd /path/to/aahlscraper
python scripts/aahl_cli.py scrape --backend http
python /path/to/aahl_yodeck_processor.py
```

### 2. Upload to Yodeck
- Log into Yodeck portal
- **Custom Apps** → **Add New HTML App**
- Name: "AAHL Hockey Display"
- Run: `python aahl_yodeck_setup.py zip`
- Upload ZIP: `aahl_display.zip`
- Click Save
- Click Push Changes

### 3. Add to Playlist
- Go to **Playlists**
- Add "AAHL Hockey Display" app
- Set duration: 60 seconds (shows all 4 sections)
- Save and Push

Done! Your canteen display will show hockey stats.

## Automatic Updates

Schedule the scraper to run every 2 hours:

```bash
0 */2 * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http && python aahl_yodeck_processor.py
```

## Key Features

✅ **Name corrections applied:**
- "Meathead" → "Marshall"
- "Mccrossin" → "McCrossin"

✅ **Smart filtering:**
- Only shows Amherst games in upcoming/recent sections
- Automatically rotates between sections every 15 seconds

✅ **Professional design:**
- Sports-themed colors and typography
- Large, readable text for distance viewing
- Full-screen, responsive layout

## Troubleshooting

**App not showing?**
- Check the ZIP file has `index.html` in the root (not in a subfolder)
- Push changes in Yodeck portal

**Data not updating?**
- Run scraper: `python scripts/aahl_cli.py scrape --backend http`
- Run processor: `python aahl_yodeck_processor.py`
- Check `data/yodeck_display.json` exists

**Wrong names showing?**
- Ensure processor ran successfully
- Check raw data for name spelling
- Update corrections in `aahl_yodeck_processor.py` if needed

## Full Documentation

See **yodeck-integration-guide.md** for:
- Detailed setup steps
- Customization options
- Advanced automation
- Troubleshooting guide

---

You're all set! 🎉
