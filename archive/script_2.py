
# Now let's create an alternative solution using Playwright for dynamic content
# This is useful if the site loads data via JavaScript

playwright_solution = """
# Amherst Adult Hockey Web Scraper - Playwright Version
# For JavaScript-rendered content

from playwright.sync_api import sync_playwright
import json
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List

class AmherstHockeyScraperPlaywright:
    '''
    Playwright-based scraper for JavaScript-heavy pages
    Use this if BeautifulSoup doesn't capture the data
    '''
    
    BASE_URL = "https://www.amherstadulthockey.com/teams"
    
    def __init__(self, team_id: str = "DSMALL", headless: bool = True):
        self.team_id = team_id
        self.headless = headless
    
    def _build_url(self, page_type: str, **params) -> str:
        '''Build URL with parameters'''
        base_params = {
            'u': self.team_id,
            's': 'hockey',
            'p': page_type
        }
        base_params.update(params)
        param_str = '&'.join(f"{k}={v}" for k, v in base_params.items())
        return f"{self.BASE_URL}/default.asp?{param_str}"
    
    def scrape_schedule(self, format_type: str = "List", date_filter: str = "ALL") -> List[Dict]:
        '''Scrape schedule using Playwright'''
        url = self._build_url('schedule', format=format_type, d=date_filter)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            
            try:
                # Navigate to page
                page.goto(url, wait_until='networkidle')
                
                # Wait for table to load (adjust selector as needed)
                page.wait_for_selector('table', timeout=10000)
                
                # Extract table data using JavaScript
                games = page.evaluate('''() => {
                    const table = document.querySelector('table');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const data = [];
                    
                    // Skip header row
                    for (let i = 1; i < rows.length; i++) {
                        const cells = Array.from(rows[i].querySelectorAll('td, th'));
                        if (cells.length < 4) continue;
                        
                        data.push({
                            date: cells[0]?.textContent?.trim() || '',
                            time: cells[1]?.textContent?.trim() || '',
                            opponent: cells[2]?.textContent?.trim() || '',
                            location: cells[3]?.textContent?.trim() || '',
                            result: cells[4]?.textContent?.trim() || '',
                            score: cells[5]?.textContent?.trim() || ''
                        });
                    }
                    
                    return data;
                }''')
                
                return games
                
            except Exception as e:
                print(f"Error scraping schedule: {e}")
                return []
            finally:
                browser.close()
    
    def scrape_stats(self, sort_by: str = "points") -> List[Dict]:
        '''Scrape player statistics using Playwright'''
        url = self._build_url('stats', psort=sort_by)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            
            try:
                page.goto(url, wait_until='networkidle')
                page.wait_for_selector('table', timeout=10000)
                
                stats = page.evaluate('''() => {
                    const table = document.querySelector('table');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const headers = Array.from(rows[0]?.querySelectorAll('th, td') || [])
                        .map(h => h.textContent.trim().toLowerCase());
                    
                    const data = [];
                    
                    for (let i = 1; i < rows.length; i++) {
                        const cells = Array.from(rows[i].querySelectorAll('td, th'));
                        if (cells.length < 2) continue;
                        
                        const player = {};
                        cells.forEach((cell, idx) => {
                            const key = headers[idx] || `col_${idx}`;
                            player[key] = cell.textContent.trim();
                        });
                        
                        data.push(player);
                    }
                    
                    return data;
                }''')
                
                return stats
                
            except Exception as e:
                print(f"Error scraping stats: {e}")
                return []
            finally:
                browser.close()
    
    def scrape_standings(self) -> List[Dict]:
        '''Scrape team standings using Playwright'''
        url = self._build_url('standings')
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            page = browser.new_page()
            
            try:
                page.goto(url, wait_until='networkidle')
                page.wait_for_selector('table', timeout=10000)
                
                standings = page.evaluate('''() => {
                    const table = document.querySelector('table');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    const headers = Array.from(rows[0]?.querySelectorAll('th, td') || [])
                        .map(h => h.textContent.trim().toLowerCase());
                    
                    const data = [];
                    
                    for (let i = 1; i < rows.length; i++) {
                        const cells = Array.from(rows[i].querySelectorAll('td, th'));
                        if (cells.length < 2) continue;
                        
                        const team = {};
                        cells.forEach((cell, idx) => {
                            const key = headers[idx] || `col_${idx}`;
                            team[key] = cell.textContent.trim();
                        });
                        
                        data.push(team);
                    }
                    
                    return data;
                }''')
                
                return standings
                
            except Exception as e:
                print(f"Error scraping standings: {e}")
                return []
            finally:
                browser.close()
    
    def export_to_json(self, data: List[Dict], filename: str):
        '''Export data to JSON file'''
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Data exported to {filename}")
    
    def export_to_csv(self, data: List[Dict], filename: str):
        '''Export data to CSV file'''
        if not data:
            print("No data to export")
            return
        
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)
        print(f"Data exported to {filename}")


# Usage
if __name__ == "__main__":
    # Note: Install Playwright first:
    # pip install playwright
    # playwright install chromium
    
    scraper = AmherstHockeyScraperPlaywright(team_id="DSMALL", headless=True)
    
    print("Scraping with Playwright...")
    
    # Scrape all data
    schedule = scraper.scrape_schedule()
    scraper.export_to_json(schedule, 'schedule_playwright.json')
    
    stats = scraper.scrape_stats()
    scraper.export_to_json(stats, 'stats_playwright.json')
    
    standings = scraper.scrape_standings()
    scraper.export_to_json(standings, 'standings_playwright.json')
    
    print("Done!")
"""

with open('amherst_hockey_scraper_playwright.py', 'w') as f:
    f.write(playwright_solution)

print("Created: amherst_hockey_scraper_playwright.py")
