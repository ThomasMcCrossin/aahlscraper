# AAHL Hockey Display for Yodeck 🏒

A professional, auto-rotating hockey statistics display system for your canteen digital signage powered by Yodeck and your AAHL scraper.
The production source of truth is the repo-root `index.html`; the scraper pipeline exists to keep that app current.

## 📺 What You Get

A beautiful, full-screen display that rotates through:

1. **🏆 Team Standings** - Wins, Losses, Points
2. **🎯 Top 20 Scorers** - Player rankings by points
3. **📊 Last 10 Days Results** - Recent game scores
4. **📅 Next 10 Days Games** - Upcoming Amherst games

Each section displays for 15 seconds, then rotates. Perfect for a canteen display!

## ✨ Key Features

✅ **Smart Name Corrections**
- "Meathead" automatically becomes "Marshall"  
- "Mccrossin" automatically becomes "McCrossin"
- All player names are corrected throughout

✅ **Amherst-Only Games**
- Upcoming games filter shows only Amherst games
- Recent results include only games from the past 10 days

✅ **Professional Design**
- Sports-themed colors (blue/white)
- Large, readable text for distance viewing
- Full-screen responsive layout
- No external dependencies

✅ **Easy Setup**
- Single HTML5 file (self-contained)
- Python processor for data transformation
- Automated deployment helper
- Complete documentation included

## 🚀 Quick Start (5 Minutes)

### 1. Generate Data
```bash
cd /path/to/aahlscraper
python scripts/aahl_cli.py scrape --backend http
python aahl_yodeck_processor.py
```

### 2. Create Deployment Package
```bash
python aahl_yodeck_setup.py full
# Creates: aahl_display.zip
```

### 3. Upload to Yodeck
- Log into Yodeck portal
- **Custom Apps** → **Add New HTML App**
- Upload: `aahl_display.zip`
- Click **Save** → **Push Changes**

### 4. Add to Playlist
- **Playlists** → Add "AAHL Hockey Display"
- Set duration: 60 seconds
- Save and deploy

**Done!** Your canteen display will show live hockey stats 🎉

## Production Baseline

- `index.html` is the canonical production HTML used for Yodeck uploads.
- `python aahl_yodeck_setup.py zip` packages that file as `aahl_display.zip`.
- Archived legacy variants and retired upload artifacts live in `archive/yodeck/` and should not be treated as the live app.

## 📂 Files Included

| File | Purpose |
|------|---------|
| `index.html` | 🎯 Canonical production Yodeck display app |
| `aahl_yodeck_processor.py` | ⚙️ Data processor (run after scraper) |
| `aahl_yodeck_setup.py` | 🔧 Deployment helper (automation) |
| `quick-start.md` | 📖 2-minute setup guide |
| `yodeck-integration-guide.md` | 📚 Complete documentation |
| `technical-summary.md` | 🔬 Technical details |

## 🔄 Automatic Updates

Set up a cron job to automatically update the display every 2 hours:

```bash
0 */2 * * * cd /path/to/aahlscraper && python scripts/aahl_cli.py scrape --backend http && python aahl_yodeck_processor.py
```

The display will pull fresh data automatically!

## 🎨 Customization

### Change Display Timing
Edit `index.html`:
```javascript
const SECTION_DURATION = 15000; // 15 seconds
```

### Change Colors
Edit CSS variables in `index.html`:
```css
--primary-color: #003478;      /* Blue */
--secondary-color: #FFFFFF;    /* White */
--accent-color: #FF6B35;       /* Orange */
```

### Add More Name Corrections
Edit `aahl_yodeck_processor.py`:
```python
NAME_CORRECTIONS = {
    r'Meathead': 'Marshall',
    r'Mccrossin': 'McCrossin',
    r'YourPattern': 'Correction',  # Add here
}
```

## 🔍 Troubleshooting

### App not showing on Yodeck?
- ✓ Check ZIP file contains `index.html` in root (not in a folder)
- ✓ Verify you clicked "Push Changes" in Yodeck portal
- ✓ Wait 30-60 seconds for player to sync

### Data not updating?
- ✓ Run scraper: `python scripts/aahl_cli.py scrape --backend http`
- ✓ Run processor: `python aahl_yodeck_processor.py`
- ✓ Check `data/yodeck_display.json` exists

### Names showing incorrectly?
- ✓ Verify processor ran successfully
- ✓ Check raw data for exact spelling
- ✓ Add additional corrections if needed

## 📋 Requirements

- Python 3.7+
- AAHL scraper installed and working
- Yodeck account with player(s)
- Internet connection to Yodeck portal

## 📖 Documentation

- **New to this?** → Start with `quick-start.md`
- **Need details?** → See `yodeck-integration-guide.md`
- **Technical questions?** → Check `technical-summary.md`

## 🛠️ Advanced Setup

### Multi-Display Deployment
The same setup works for multiple displays:
1. Add the app to multiple Yodeck playlists
2. Each display will show the same data
3. Updates sync automatically across all screens

### Custom Data Integration
You can manually provide data in `data/yodeck_display.json`:

```json
{
  "timestamp": "2025-11-02T22:30:00",
  "standings": [...],
  "top_scorers": [...],
  "recent_results": [...],
  "upcoming_games": [...]
}
```

### Yodeck REST API
For programmatic control, use Yodeck's REST API to:
- Deploy updates remotely
- Manage playlists
- Monitor player status

See: https://www.yodeck.com/docs/user-manual/introducing-yodecks-rest-api-seamless-integration-for-your-digital-signage-needs/

## 💡 Tips

💡 **Best Practice:** Run the scraper every 2 hours for fresh data
💡 **Display Placement:** Mount at eye level, 5-10 feet from typical viewing area
💡 **Brightness:** Use 80-90% brightness for optimal visibility
💡 **Rotation:** Auto-rotation every 15 seconds keeps content fresh
💡 **Test First:** Display app in a test playlist before deploying to main screens

## 🤝 Support

### Issues?
1. Check troubleshooting section above
2. Review documentation files
3. Check AAHL scraper: https://github.com/ThomasMcCrossin/aahlscraper
4. Yodeck support: https://www.yodeck.com/

### Feedback?
Have suggestions or found a bug? Please report it!

## 📝 License

This project is provided as-is for displaying public AAHL website data.

---

**Version:** 1.0  
**Created:** November 2, 2025  
**Author:** Thomas McCrossin  

Enjoy your new hockey display! 🎉🏒
