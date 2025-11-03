# AAHL Yodeck Display System - Complete Architecture

## System Overview Diagram

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    AAHL YODECK DISPLAY SYSTEM ARCHITECTURE               ║
║                                                                           ║
║  DATA SOURCE → PROCESSING → DEPLOYMENT → DISPLAY → OUTPUT                ║
╚══════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: DATA COLLECTION                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐                                                       │
│  │ AAHL Website │                                                       │
│  │ (amherstaad) │                                                       │
│  └──────┬───────┘                                                       │
│         │                                                               │
│         │ HTTP Requests                                                 │
│         ▼                                                               │
│  ┌──────────────────────────┐                                           │
│  │  aahlscraper             │                                           │
│  │  (BeautifulSoup Backend) │                                           │
│  │  CLI: aahl_cli.py        │                                           │
│  └────────┬─────────────────┘                                           │
│           │                                                             │
│           │ Generates                                                   │
│           ├─ schedule.json/csv                                          │
│           ├─ player_stats.json/csv                                      │
│           └─ standings.json/csv                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

        │
        │ (Put files in data/ directory)
        ▼

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: DATA PROCESSING                                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────┐                                    │
│  │ aahl_yodeck_processor.py        │                                    │
│  │                                 │                                    │
│  │ 1. Load JSON/CSV data           │                                    │
│  │ 2. Apply name corrections:      │                                    │
│  │    • Meathead → Marshall        │                                    │
│  │    • Mccrossin → McCrossin      │                                    │
│  │ 3. Filter Amherst games:        │                                    │
│  │    • Recent: past 10 days       │                                    │
│  │    • Upcoming: next 10 days     │                                    │
│  │ 4. Sort & rank:                 │                                    │
│  │    • Standings by points        │                                    │
│  │    • Players by points (top 20) │                                    │
│  │ 5. Generate JSON output         │                                    │
│  └─────────┬───────────────────────┘                                    │
│            │                                                            │
│            │ Produces                                                   │
│            ▼                                                            │
│     ┌──────────────────────┐                                            │
│     │ yodeck_display.json  │                                            │
│     │  • timestamp         │                                            │
│     │  • standings[]       │                                            │
│     │  • top_scorers[]     │                                            │
│     │  • recent_results[]  │                                            │
│     │  • upcoming_games[]  │                                            │
│     └──────────────────────┘                                            │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

        │
        │ (Run: python aahl_yodeck_processor.py)
        ▼

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: DEPLOYMENT PREPARATION                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────┐                                           │
│  │ aahl_yodeck_setup.py     │                                           │
│  │                          │                                           │
│  │ Commands:                │                                           │
│  │ • full - Complete setup  │                                           │
│  │ • check - Validate       │                                           │
│  │ • process - Run proc.    │                                           │
│  │ • zip - Create package   │                                           │
│  │ • preview - Show data    │                                           │
│  └────────┬─────────────────┘                                           │
│           │                                                             │
│           │ Creates                                                     │
│           ▼                                                             │
│     ┌────────────────────┐                                              │
│     │ aahl_display.zip   │ ← Ready to upload to Yodeck                  │
│     │ (contains:)        │                                              │
│     │  └─ index.html     │                                              │
│     └────────────────────┘                                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

        │
        │ (Run: python aahl_yodeck_setup.py full)
        ▼

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: YODECK DEPLOYMENT                                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────┐                                   │
│  │ Yodeck Portal (Web Browser)      │                                   │
│  │                                  │                                   │
│  │ 1. Custom Apps → Add New         │                                   │
│  │ 2. Select: HTML App              │                                   │
│  │ 3. Upload: aahl_display.zip      │                                   │
│  │ 4. Click: Save                   │                                   │
│  │ 5. Click: Push Changes           │                                   │
│  └────────┬─────────────────────────┘                                   │
│           │                                                             │
│           │ Syncs to                                                    │
│           ▼                                                             │
│     ┌─────────────────────────────────────────┐                         │
│     │ Yodeck Players (Raspberry Pi 3/4)       │                         │
│     │                                         │                         │
│     │ ┌─────────────────────────────────────┐ │                         │
│     │ │ Player 1 (Canteen Display)          │ │                         │
│     │ │  └─ index.html (downloaded)         │ │                         │
│     │ └─────────────────────────────────────┘ │                         │
│     │                                         │                         │
│     │ ┌─────────────────────────────────────┐ │                         │
│     │ │ Player 2 (Hallway Display)          │ │                         │
│     │ │  └─ index.html (downloaded)         │ │                         │
│     │ └─────────────────────────────────────┘ │                         │
│     └─────────────────────────────────────────┘                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

        │ (Auto-runs)
        ▼

┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 5: DISPLAY OUTPUT                                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────────────────────────────────────────┐                   │
│  │           CANTEEN DIGITAL DISPLAY               │                   │
│  │        (Full Screen, 4K or HD Monitor)          │                   │
│  ├──────────────────────────────────────────────────┤                   │
│  │                                                  │                   │
│  │  AMHERST ADULT HOCKEY LEAGUE                     │                   │
│  │                                                  │                   │
│  │  ┌───────────────────────────────────────────┐   │                   │
│  │  │ SECTION 1: TEAM STANDINGS                 │   │  ← 15 sec        │
│  │  │                                           │   │                   │
│  │  │ Team              W  L  P                 │   │                   │
│  │  │ ─────────────────────────────             │   │                   │
│  │  │ Amherst Hawks     8  2  16                │   │                   │
│  │  │ Downtown Small    7  3  14                │   │                   │
│  │  │ Frontier City     6  4  12                │   │                   │
│  │  │ Maple Grove       5  5  10                │   │                   │
│  │  └───────────────────────────────────────────┘   │                   │
│  │                    [Auto-rotate]                  │                   │
│  ├──────────────────────────────────────────────────┤                   │
│  │                                                  │                   │
│  │  ┌───────────────────────────────────────────┐   │                   │
│  │  │ SECTION 2: TOP 20 SCORERS                 │   │  ← 15 sec        │
│  │  │                                           │   │                   │
│  │  │ Rank  Player Name       Team         Pts │   │                   │
│  │  │ ─────────────────────────────────────    │   │                   │
│  │  │ 1.    Marshall MacDonald Amherst    24  │   │                   │
│  │  │ 2.    Thomas McCrossin   Downtown    22  │   │                   │
│  │  │ 3.    Jake Thompson      Frontier    20  │   │                   │
│  │  │ ...                                    │   │                   │
│  │  └───────────────────────────────────────────┘   │                   │
│  │                    [Auto-rotate]                  │                   │
│  ├──────────────────────────────────────────────────┤                   │
│  │                                                  │                   │
│  │  ┌───────────────────────────────────────────┐   │                   │
│  │  │ SECTION 3: LAST 10 DAYS RESULTS           │   │  ← 15 sec        │
│  │  │                                           │   │                   │
│  │  │ Date        Score                      │   │                   │
│  │  │ ──────────────────────                  │   │                   │
│  │  │ Oct 31  Amherst Hawks 5 - Frontier 3  │   │                   │
│  │  │ Oct 28  Downtown Sm 4 - Maple Gr 2    │   │                   │
│  │  │ Oct 26  Frontier City 2 - Amherst 6   │   │                   │
│  │  │ ...                                    │   │                   │
│  │  └───────────────────────────────────────────┘   │                   │
│  │                    [Auto-rotate]                  │                   │
│  ├──────────────────────────────────────────────────┤                   │
│  │                                                  │                   │
│  │  ┌───────────────────────────────────────────┐   │                   │
│  │  │ SECTION 4: NEXT 10 DAYS (AMHERST GAMES)   │   │  ← 15 sec        │
│  │  │                                           │   │                   │
│  │  │ Date  Time     Game                    │   │                   │
│  │  │ ─────────────────────────────────────  │   │                   │
│  │  │ Nov 7  8:00 PM  Amherst vs Maple Gr    │   │                   │
│  │  │ Nov 9  7:30 PM  Downtown vs Amherst    │   │                   │
│  │  │ Nov 12 8:00 PM  Amherst vs Frontier    │   │                   │
│  │  │ ...                                    │   │                   │
│  │  └───────────────────────────────────────────┘   │                   │
│  │                    [Auto-rotate]                  │                   │
│  │                    (Loop continues)               │                   │
│  │                                                  │                   │
│  └──────────────────────────────────────────────────┘                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
AAHL Website
     ↓
  Scraper (HTTP)
     ↓
JSON Data Files (schedule, stats, standings)
     ↓
Processor (Name corrections, filtering, sorting)
     ↓
yodeck_display.json (Formatted output)
     ↓
Yodeck Portal (Upload ZIP)
     ↓
Yodeck Players (Download app)
     ↓
Canteen Display (Show rotating sections)
```

## Component Relationships

```
┌─────────────────────────────────────────────────────┐
│  Core Components                                    │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐      ┌──────────────────────┐   │
│  │ AAHL Scraper │      │ Yodeck Signage       │   │
│  │ (Existing)   │      │ Platform             │   │
│  │              │      │                      │   │
│  │ • schedule   │      │ • Portal/Playlists   │   │
│  │ • stats      │      │ • Players/Hardware   │   │
│  │ • standings  │      │ • Network Sync       │   │
│  └──────────────┘      └──────────────────────┘   │
│          ▲                         ▲               │
│          │                         │               │
│          └─────────────┬───────────┘               │
│                        │                           │
│            ┌───────────┴──────────┐               │
│            │   This Package       │               │
│            │                      │               │
│            ├──────────────────────┤               │
│            │ • Processor Script   │               │
│            │ • Display App        │               │
│            │ • Setup Automation   │               │
│            │ • Documentation      │               │
│            └──────────────────────┘               │
│                        │                           │
│            ┌───────────┴──────────┐               │
│            ▼                       ▼               │
│      (Processes)            (Displays)            │
│      Data                   On Screen             │
│                                                   │
└─────────────────────────────────────────────────────┘
```

## File Dependencies

```
AAHL Scraper Output
  ├─ schedule.json
  ├─ player_stats.json
  └─ standings.json
       │
       ├─ Used by ─────────────────────────────────────┐
       │                                               │
       │      aahl_yodeck_processor.py                 │
       │      (Data transformation)                    │
       │                                               │
       ├─ Produces ────────────────────────────────────┤
       │                                               │
       └─ yodeck_display.json                         │
            │                                          │
            ├─ Used by ─────────────────────────────┐ │
            │                                        │ │
            │    index.html                          │ │
            │    (Display app)                       │ │
            │                                        │ │
            ├─ Packages as ───────────────────────┤ │
            │                                      │ │
            └─ aahl_display.zip                   │ │
                 │                                 │ │
                 ├─ Upload to ────────────────────┤ │
                 │                                 │ │
                 └─ Yodeck Portal                 │ │
                      │                            │ │
                      ├─ Sync to ──────────────┤  │ │
                      │                        │  │ │
                      └─ Yodeck Players        │  │ │
                           │                   │  │ │
                           └─ Display on       │  │ │
                              Screen ◄────────┘  │ │
                                                  │ │
                 Optional Setup Automation ◄─────┘ │
                                                   │
                 aahl_yodeck_setup.py             │
                 (Orchestrates all steps) ◄────────┘
```

## Update Cycle

```
┌─────────────────────────────────────────────────┐
│  Automated Update Cycle (Optional Cron Job)     │
├─────────────────────────────────────────────────┤
│                                                 │
│  Every 2 Hours (or Custom Interval):            │
│                                                 │
│  1. Cron triggers scraper                       │
│     → python aahl_cli.py scrape                 │
│                                                 │
│  2. New data files generated                    │
│     → schedule.json, stats, standings           │
│                                                 │
│  3. Processor transforms data                   │
│     → python aahl_yodeck_processor.py           │
│                                                 │
│  4. JSON output updated                         │
│     → yodeck_display.json (with timestamp)      │
│                                                 │
│  5. Yodeck player detects change                │
│     → Auto-downloads new data                   │
│                                                 │
│  6. Display refreshes automatically             │
│     → Shows latest standings, scores, games     │
│                                                 │
│  Loop repeats every 2 hours...                  │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Key Features Mapping

```
Name Corrections
  ├─ Applied in: aahl_yodeck_processor.py
  ├─ Pattern: Regex-based substitution
  ├─ Scope: All player/team names
  └─ Output: Cleaned JSON

Game Filtering
  ├─ Applied in: aahl_yodeck_processor.py
  ├─ Logic: Check for "amherst" in location/teams
  ├─ Recent: Past 10 calendar days
  ├─ Upcoming: Next 10 calendar days
  └─ Output: Filtered arrays

Display Sections
  ├─ Implemented in: index.html
  ├─ Section 1: Standings (15 sec)
  ├─ Section 2: Top 20 Scorers (15 sec)
  ├─ Section 3: Last 10 Days (15 sec)
  ├─ Section 4: Next 10 Days (15 sec)
  └─ Rotation: Auto-loop

Professional Styling
  ├─ Implemented in: index.html CSS
  ├─ Colors: Blue/White/Orange
  ├─ Typography: Large, readable
  ├─ Layout: Full-screen responsive
  └─ Theme: Sports display

Automation
  ├─ Processor: aahl_yodeck_processor.py
  ├─ Setup: aahl_yodeck_setup.py
  ├─ Scheduling: Cron job (optional)
  └─ Sync: Yodeck player auto-sync
```

---

**Architecture Version:** 1.0  
**Last Updated:** November 2, 2025  
**Status:** Production Ready ✅
