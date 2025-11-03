# AAHL Display Customization - 1080p 42" TV + Amherst Stadium

## Display Specifications

**Hardware:** 42-inch 1080p TV (Amherst Stadium)  
**Resolution:** 1920 × 1080 pixels  
**Aspect Ratio:** 16:9 (landscape)  
**Typical Viewing Distance:** 20-30 feet  

This larger display requires optimized text sizing and spacing for visibility from a distance.

## Optimized Settings for 42" 1080p Display

### Text Sizing

```css
/* Updated for 42" display visibility */
body {
  font-size: 48px;  /* Larger base for distance viewing */
}

h1 {
  font-size: 72px;  /* Huge header */
}

h2 {
  font-size: 60px;  /* Section titles */
}

table {
  font-size: 52px;  /* Table content */
}

.player-name {
  font-size: 54px;  /* Player names - very readable */
}

.score-large {
  font-size: 88px;  /* Game scores */
}
```

### Padding & Spacing

```css
/* Increased spacing for 42" screen */
:root {
  --section-padding: 60px;    /* Was 30px */
  --section-margin: 40px;     /* Was 20px */
  --table-row-height: 120px;  /* Was 60px */
  --table-gap: 80px;          /* Was 40px */
}
```

### Column Count

```css
/* Fewer columns = larger items */

/* Standings table: 3 columns instead of 4 */
standings-table {
  column-count: 3;
  column-gap: 60px;
}

/* Top scorers: 2 columns instead of 3 */
scorers-table {
  column-count: 2;
  column-gap: 60px;
}

/* Results: 1 item per row */
results-item {
  width: 95%;
  margin-bottom: 40px;
}
```

## Amherst Stadium Context

The display is in **Amherst Stadium** (not canteen).

**Implications:**
- Stadium is an official venue/arena
- Likely high traffic during games
- Professional sports environment
- May want to highlight Amherst teams/home games more prominently

### Updated Filtering

```python
# Suggest showing ALL Amherst games prominently
# Also show: Games at Amherst Stadium specifically

def filter_amherst_games(schedule):
    """
    For stadium display: Show all Amherst games + 
    any games AT Amherst Stadium (home games)
    """
    amherst_games = []
    for game in schedule:
        home = game.get('home_team', '').lower()
        location = game.get('location', '').lower()
        
        # Include if:
        # 1. Amherst is home or away team
        # 2. Game is at Amherst Stadium (even if neutral)
        if 'amherst' in home or 'amherst' in location or 'stadium' in location:
            amherst_games.append(game)
    
    return amherst_games
```

## Additional Data Sources

The AAHL website has more data that could enhance the display:

### 1. Team Rosters
**URL:** `https://www.amherstadulthockey.com/teams/default.asp?u=DSMALL&s=hockey&p=roster`

**Available Data:**
- Player names (by team)
- Player numbers
- Player positions (if available)
- Any player stats on roster page

**Integration Idea:**
```python
# Scrape rosters for each team
rosters = {
    'DSMALL': ['Player 1', 'Player 2', ...],
    'TEAM_ID': [...],
}

# Use to:
# - Show team lineup for upcoming games
# - Validate player names (catch misspellings)
# - Show "Player of Game" or "Hot Players"
```

### 2. Team Stats
Likely available on AAHL site:
- Team win/loss streaks
- Head-to-head records
- Seasonal statistics

### 3. League Statistics
- Goals per game average
- Scoring leaders (entire league)
- Shutouts
- Penalty statistics

### 4. Game Details
More detailed game information:
- Final scores (already have)
- Goal scorers (if available)
- Assists
- Penalties
- Attendance

## Enhanced Scraper Configuration

To capture team rosters, consider adding to your scraper:

```python
class AAHLRosterScraper:
    """Scrape team rosters from AAHL website"""
    
    TEAM_IDS = ['DSMALL', 'TEAM2', 'TEAM3', ...]  # From website
    
    def scrape_roster(self, team_id):
        """
        Scrape roster from:
        https://www.amherstadulthockey.com/teams/default.asp?u={team_id}&s=hockey&p=roster
        
        Returns:
            List of players with names, numbers, positions
        """
        url = f"https://www.amherstadulthockey.com/teams/default.asp?u={team_id}&s=hockey&p=roster"
        # ... BeautifulSoup parsing ...
        return roster_data
    
    def scrape_all_rosters(self):
        """Scrape all team rosters and save to JSON"""
        for team_id in self.TEAM_IDS:
            roster = self.scrape_roster(team_id)
            # Save to: data/rosters/{team_id}.json
```

## Updated Display Ideas with Additional Data

### Display Section 5: Team Spotlight (Optional Rotation)
```
┌──────────────────────────┐
│ DOWNTOWN SMALL ROSTER    │
├──────────────────────────┤
│ #  Player Name   Pos     │
│ ──────────────────────   │
│ 5   John Smith    F      │
│ 7   Mike Johnson  D      │
│ 12  Dave Wilson   G      │
│ ... (Show ~10 players)   │
└──────────────────────────┘
```

### Display Section 6: League Leaders (Optional)
```
┌──────────────────────────┐
│ LEAGUE SCORING LEADERS   │
├──────────────────────────┤
│ Rank  Player    Goals Ast│
│ ───────────────────────  │
│ 1.    Marshall M   15   9│
│ 2.    Thomas M     13  10│
│ 3.    Jake T       12   8│
└──────────────────────────┘
```

## Implementation Recommendations

### Phase 1: Current System (Recommended First)
✅ Deploy the current 4-section display
- Standings
- Top 20 Scorers
- Last 10 Days Results
- Upcoming 10 Days Games

**Why:** Test on your 42" display first, ensure quality visibility

### Phase 2: Expand Data Sources (Optional Later)
❌ Wait until Phase 1 is working perfectly
- Add roster scraper
- Integrate additional stats
- Add more display sections
- Customize for stadium environment

### Phase 3: Stadium-Specific Features (Advanced)
❌ Only if you want to expand significantly
- Live score updates during games
- Team announcements/promos
- Player spotlights
- Attendance/records

## 42" Display Recommendations

### Layout Tips

1. **Increase Line Height**
   ```css
   line-height: 1.8;  /* More vertical space */
   ```

2. **Wider Tables**
   ```css
   table-width: 95%;  /* Use more screen space */
   ```

3. **Fewer Items Per Screen**
   ```css
   /* Show only top 8 scorers instead of 20 */
   /* Larger text means fewer items fit */
   max-items-per-section: 8;
   ```

4. **High Contrast Colors**
   - Use primary color (#003478) for backgrounds
   - White for text
   - Orange (#FF6B35) for accents
   - Makes text pop from distance

5. **Minimum Font Size**
   - Main title: 72px minimum
   - Content: 48px minimum
   - Large enough to read from 25+ feet

### Testing Checklist for 42" Display

- [ ] Text readable from back of stadium (25+ feet)
- [ ] No scrolling needed (all content visible)
- [ ] Colors distinct and not washed out
- [ ] Sections clearly separated
- [ ] Auto-rotation smooth and visible
- [ ] All scores/names display correctly
- [ ] Performance smooth (no stuttering)

## File Updates for Stadium Display

### Modified index.html Settings

```javascript
// For 42" 1080p display
const DISPLAY_CONFIG = {
  resolution: '1920x1080',
  display_size: '42 inches',
  viewing_distance: '25-30 feet',
  section_duration: 20000,  // Increased to 20 seconds (was 15)
  font_scale: 1.4,          // 40% larger fonts
  min_font_size: 48,        // Minimum 48px
  item_limit: 8,            // Fewer items, larger display
  row_height: 120,          // More vertical spacing
};
```

### CSS Media Query (Optional)

```css
/* For 42" 1080p display */
@media screen and (min-width: 1920px) and (min-height: 1080px) {
  body {
    font-size: 52px;
  }
  
  .section-title {
    font-size: 72px;
    margin-bottom: 40px;
  }
  
  table {
    font-size: 48px;
    line-height: 2;
  }
}
```

## Integration Steps for Stadium

1. **Deploy Current System**
   ```bash
   python aahl_yodeck_setup.py full
   # Upload to Yodeck for 42" TV
   ```

2. **Test and Adjust**
   - View from different distances
   - Adjust fonts if needed
   - Verify all sections visible
   - Check auto-rotation

3. **Set Up Auto-Updates**
   ```bash
   # Scraper runs every 2 hours
   0 */2 * * * /path/to/update.sh
   ```

4. **Monitor**
   - Check display daily
   - Verify fresh data showing
   - Monitor for any issues

## Optional: Later Data Expansion

If you want to add team rosters and more data later:

```python
# aahl_yodeck_processor_v2.py
# Add this function to existing processor

def scrape_and_process_rosters(self):
    """
    Optional: Scrape team rosters
    Save to: data/rosters.json
    """
    # Implementation here
```

## Summary

**Current System:**
- Optimized for 1080p 42" display
- Larger fonts for distance viewing
- 4-section auto-rotation
- Amherst games filtered
- Ready to deploy immediately

**Stadium Location:**
- Official arena environment
- Professional sports context
- High visibility requirement
- Perfect for this display type

**Future Enhancement Options:**
- Team rosters (if you scrape them)
- Additional league statistics
- Live updates during games
- More display sections

**Recommendation:**
🚀 Start with current 4-section system on 42" display
✅ Test and verify visibility
✅ Deploy to Amherst Stadium
⏰ Consider roster data as Phase 2 expansion

---

**Version:** 1.1 (42" Stadium Display)  
**Last Updated:** November 2, 2025
