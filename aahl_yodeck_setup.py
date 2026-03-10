#!/usr/bin/env python3
"""
AAHL Yodeck Deployment Helper
Automated setup and deployment for the AAHL Hockey Display on Yodeck
"""

import os
import sys
import json
import subprocess
import zipfile
from pathlib import Path
from datetime import datetime

PRODUCTION_HTML = "index.html"
LEGACY_YODECK_ARCHIVE = Path("archive") / "yodeck"
LEGACY_HTML_VARIANTS = (
    LEGACY_YODECK_ARCHIVE / "index_redesign_v2_no_qr.html",
    LEGACY_YODECK_ARCHIVE / "index_alt_showcase.html",
    LEGACY_YODECK_ARCHIVE / "index_vibrant_centerice.html",
    LEGACY_YODECK_ARCHIVE / "index_vibrant_hypewall.html",
    LEGACY_YODECK_ARCHIVE / "index_vibrant_retroboard.html",
)

class AAHLYodeckSetup:
    """Helper for setting up AAHL display on Yodeck."""

    def __init__(self):
        self.base_dir = Path.cwd()
        self.data_dir = self.base_dir / "data"

    def check_requirements(self):
        """Check if all required files exist."""
        print("\n📋 Checking requirements...")

        required_files = {
            PRODUCTION_HTML: 'canonical production Yodeck display app',
            'aahl_yodeck_processor.py': 'Data processor',
        }

        missing = []
        for filename, description in required_files.items():
            if not (self.base_dir / filename).exists():
                missing.append(f"  ✗ {filename} ({description})")
            else:
                print(f"  ✓ {filename} ({description})")

        if missing:
            print("\n⚠️  Missing files:")
            for m in missing:
                print(m)
            return False

        legacy_present = [path for path in LEGACY_HTML_VARIANTS if (self.base_dir / path).exists()]
        if legacy_present:
            print("\nℹ️  Archived legacy HTML variants present for reference only:")
            for path in legacy_present:
                print(f"  - {path.as_posix()}")
            print(f"  Use {PRODUCTION_HTML} as the production Yodeck source of truth.")

        return True

    def check_scraper_data(self):
        """Check if scraper has generated data files."""
        print("\n📊 Checking scraper data...")

        required_data = {
            'standings.json': 'Team standings',
            'player_stats.json': 'Player statistics',
            'schedule.json': 'Game schedule',
        }

        # Also accept CSV versions
        alternatives = {
            'standings.csv': 'standings.json',
            'player_stats.csv': 'player_stats.json',
            'schedule.csv': 'schedule.json',
        }

        missing = []
        for filename, description in required_data.items():
            json_path = self.data_dir / filename
            csv_alt = self.data_dir / alternatives.get(filename, '')

            if json_path.exists():
                print(f"  ✓ {filename} ({description})")
            elif csv_alt.exists():
                alt_name = str(csv_alt).split('/')[-1]
                print(f"  ✓ {alt_name} ({description})")
            else:
                missing.append(f"  ✗ {filename} (need to run scraper)")

        if missing:
            print("\n⚠️  Missing data files. Run the scraper first:")
            print("  python scripts/aahl_cli.py scrape --backend http")
            return False

        return True

    def run_processor(self):
        """Run the data processor."""
        print("\n⚙️  Processing data for Yodeck...")

        try:
            from aahl_yodeck_processor import AAHLDataProcessor
            processor = AAHLDataProcessor(str(self.data_dir))
            data = processor.save_yodeck_data()
            print("  ✓ Data processed successfully")
            return True
        except Exception as e:
            print(f"  ✗ Error processing data: {e}")
            return False

    def create_zip(self):
        """Create ZIP file for Yodeck upload."""
        print("\n📦 Creating ZIP file...")

        zip_path = self.base_dir / "aahl_display.zip"
        source_html = self.base_dir / PRODUCTION_HTML

        try:
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                # Add index.html to root of ZIP
                zf.write(source_html, arcname='index.html')

            print(f"  ✓ Created: {zip_path}")
            print(f"  ✓ Size: {zip_path.stat().st_size / 1024:.1f} KB")
            print(f"  ✓ Source HTML: {source_html.name}")
            print(f"\n  Upload this ZIP to Yodeck:")
            print(f"    1. Go to Custom Apps in Yodeck portal")
            print(f"    2. Click 'Add New HTML App'")
            print(f"    3. Upload: {zip_path}")
            print(f"    4. Click Save and Push Changes")
            return True
        except Exception as e:
            print(f"  ✗ Error creating ZIP: {e}")
            return False

    def show_data_preview(self):
        """Show a preview of the processed data."""
        print("\n👁️  Data Preview")
        print("-" * 50)

        data_file = self.data_dir / "yodeck_display.json"
        if not data_file.exists():
            print("  Data file not found")
            return

        try:
            with open(data_file, 'r') as f:
                data = json.load(f)

            print(f"Generated: {data.get('timestamp', 'N/A')}")
            print(f"\nStandings: {len(data.get('standings', []))} teams")
            print(f"Top Scorers: {len(data.get('top_scorers', []))} players")
            print(f"Recent Results: {len(data.get('recent_results', []))} games")
            print(f"Upcoming Games: {len(data.get('upcoming_games', []))} games")

            if data.get('top_scorers'):
                print(f"\nTop Scorer: {data['top_scorers'][0].get('player_name')} - {data['top_scorers'][0].get('points')} points")

            if data.get('upcoming_games'):
                first_game = data['upcoming_games'][0]
                print(f"Next Game: {first_game.get('home_team')} vs {first_game.get('away_team')} - {first_game.get('date')}")

        except Exception as e:
            print(f"  Error reading data: {e}")

    def full_setup(self):
        """Run complete setup process."""
        print("=" * 60)
        print("  AAHL YODECK DISPLAY SETUP")
        print("=" * 60)

        # Check requirements
        if not self.check_requirements():
            print("\n❌ Setup incomplete - missing required files")
            return False

        # Check scraper data
        if not self.check_scraper_data():
            print("\n❌ Setup incomplete - run scraper first")
            return False

        # Process data
        if not self.run_processor():
            print("\n❌ Setup incomplete - data processing failed")
            return False

        # Create ZIP
        if not self.create_zip():
            print("\n❌ Setup incomplete - ZIP creation failed")
            return False

        # Show preview
        self.show_data_preview()

        print("\n" + "=" * 60)
        print("  ✅ SETUP COMPLETE!")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Log into Yodeck portal")
        print("  2. Go to Custom Apps")
        print("  3. Click 'Add New HTML App'")
        print("  4. Upload aahl_display.zip")
        print("  5. Click Save, then Push Changes")
        print("  6. Add the app to your canteen display playlist")
        print("\nFor more info, see: yodeck-integration-guide.md")

        return True

if __name__ == "__main__":
    setup = AAHLYodeckSetup()

    # Show menu
    if len(sys.argv) > 1:
        if sys.argv[1] == "full":
            setup.full_setup()
        elif sys.argv[1] == "process":
            setup.run_processor()
        elif sys.argv[1] == "check":
            setup.check_requirements()
            setup.check_scraper_data()
        elif sys.argv[1] == "zip":
            setup.create_zip()
        elif sys.argv[1] == "preview":
            setup.show_data_preview()
        else:
            print("Unknown command:", sys.argv[1])
    else:
        # Default: full setup
        setup.full_setup()
