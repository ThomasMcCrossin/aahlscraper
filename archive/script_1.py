
# Let's create a comprehensive scraping solution for the Amherst Adult Hockey website
# Since we can't access the site directly in this environment, I'll create template code
# with explanations based on typical ASP.NET table structures

scraping_solution = """
# Amherst Adult Hockey Web Scraper
# Solution for extracting schedule, stats, and standings data

import requests
from bs4 import BeautifulSoup
import pandas as pd
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class AmherstHockeyScraper:
    '''
    Scraper for Amherst Adult Hockey league data
    Handles schedule, statistics, and standings pages
    '''
    
    BASE_URL = "https://www.amherstadulthockey.com/teams"
    
    def __init__(self, team_id: str = "DSMALL"):
        self.team_id = team_id
        self.session = requests.Session()
        # Add headers to appear more like a browser
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
    
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
        '''
        Scrape schedule data from the schedule page
        
        Args:
            format_type: Display format (List, Calendar)
            date_filter: Date filter (ALL, or specific date)
        
        Returns:
            List of game dictionaries
        '''
        url = self._build_url('schedule', format=format_type, d=date_filter)
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find the schedule table - typically has class 'table' or similar
            # ASP.NET sites often use tables with specific IDs
            schedule_table = soup.find('table', class_=['table', 'schedule-table', 'data-table'])
            
            if not schedule_table:
                # Fallback: find all tables and use the largest one
                tables = soup.find_all('table')
                if tables:
                    schedule_table = max(tables, key=lambda t: len(t.find_all('tr')))
            
            if not schedule_table:
                print("No schedule table found")
                return []
            
            games = []
            rows = schedule_table.find_all('tr')
            
            # Skip header row(s)
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) < 4:  # Skip rows with insufficient data
                    continue
                
                # Extract game data
                # Typical columns: Date, Time, Opponent, Location, Result/Score
                game = {
                    'date': cells[0].get_text(strip=True),
                    'time': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                    'opponent': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                    'location': cells[3].get_text(strip=True) if len(cells) > 3 else '',
                    'result': cells[4].get_text(strip=True) if len(cells) > 4 else '',
                    'score': cells[5].get_text(strip=True) if len(cells) > 5 else '',
                }
                
                games.append(game)
            
            return games
            
        except Exception as e:
            print(f"Error scraping schedule: {e}")
            return []
    
    def scrape_stats(self, sort_by: str = "points") -> List[Dict]:
        '''
        Scrape player statistics
        
        Args:
            sort_by: Sorting parameter (points, goals, assists, etc.)
        
        Returns:
            List of player stat dictionaries
        '''
        url = self._build_url('stats', psort=sort_by)
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find stats table
            stats_table = soup.find('table', class_=['table', 'stats-table', 'data-table'])
            
            if not stats_table:
                # Look for table with ID containing 'stats' or 'dt_p'
                stats_table = soup.find('table', id=lambda x: x and 'dt_p' in x.lower() if x else False)
            
            if not stats_table:
                tables = soup.find_all('table')
                if tables:
                    stats_table = max(tables, key=lambda t: len(t.find_all('tr')))
            
            if not stats_table:
                print("No stats table found")
                return []
            
            players = []
            rows = stats_table.find_all('tr')
            
            # Extract headers
            header_row = rows[0] if rows else None
            headers = []
            if header_row:
                headers = [cell.get_text(strip=True).lower() for cell in header_row.find_all(['th', 'td'])]
            
            # Common headers: Player, GP (Games Played), G (Goals), A (Assists), PTS (Points), PIM (Penalties)
            
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) < 2:
                    continue
                
                # Create dictionary using headers if available
                if headers and len(headers) == len(cells):
                    player = {headers[i]: cells[i].get_text(strip=True) for i in range(len(cells))}
                else:
                    # Fallback to common structure
                    player = {
                        'player': cells[0].get_text(strip=True),
                        'games_played': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                        'goals': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'assists': cells[3].get_text(strip=True) if len(cells) > 3 else '',
                        'points': cells[4].get_text(strip=True) if len(cells) > 4 else '',
                        'penalties': cells[5].get_text(strip=True) if len(cells) > 5 else '',
                    }
                
                players.append(player)
            
            return players
            
        except Exception as e:
            print(f"Error scraping stats: {e}")
            return []
    
    def scrape_standings(self) -> List[Dict]:
        '''
        Scrape team standings
        
        Returns:
            List of team standing dictionaries
        '''
        url = self._build_url('standings')
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find standings table
            standings_table = soup.find('table', class_=['table', 'standings-table', 'data-table'])
            
            if not standings_table:
                tables = soup.find_all('table')
                if tables:
                    standings_table = max(tables, key=lambda t: len(t.find_all('tr')))
            
            if not standings_table:
                print("No standings table found")
                return []
            
            teams = []
            rows = standings_table.find_all('tr')
            
            # Extract headers
            header_row = rows[0] if rows else None
            headers = []
            if header_row:
                headers = [cell.get_text(strip=True).lower() for cell in header_row.find_all(['th', 'td'])]
            
            # Common headers: Team, GP, W, L, T/OTL, PTS, GF, GA, DIFF
            
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                
                if len(cells) < 2:
                    continue
                
                if headers and len(headers) == len(cells):
                    team = {headers[i]: cells[i].get_text(strip=True) for i in range(len(cells))}
                else:
                    team = {
                        'team': cells[0].get_text(strip=True),
                        'games_played': cells[1].get_text(strip=True) if len(cells) > 1 else '',
                        'wins': cells[2].get_text(strip=True) if len(cells) > 2 else '',
                        'losses': cells[3].get_text(strip=True) if len(cells) > 3 else '',
                        'ties': cells[4].get_text(strip=True) if len(cells) > 4 else '',
                        'points': cells[5].get_text(strip=True) if len(cells) > 5 else '',
                        'goals_for': cells[6].get_text(strip=True) if len(cells) > 6 else '',
                        'goals_against': cells[7].get_text(strip=True) if len(cells) > 7 else '',
                    }
                
                teams.append(team)
            
            return teams
            
        except Exception as e:
            print(f"Error scraping standings: {e}")
            return []
    
    def get_recent_games(self, weeks: int = 1) -> List[Dict]:
        '''
        Filter schedule to get games from the last N weeks
        
        Args:
            weeks: Number of weeks to look back
        
        Returns:
            List of recent games
        '''
        all_games = self.scrape_schedule()
        
        if not all_games:
            return []
        
        # Calculate date threshold
        cutoff_date = datetime.now() - timedelta(weeks=weeks)
        
        recent_games = []
        for game in all_games:
            try:
                # Try to parse the date (format may vary)
                # Common formats: "MM/DD/YYYY", "MM-DD-YYYY", etc.
                date_str = game.get('date', '')
                
                # Try multiple date formats
                for fmt in ['%m/%d/%Y', '%m-%d-%Y', '%Y-%m-%d', '%m/%d/%y']:
                    try:
                        game_date = datetime.strptime(date_str, fmt)
                        if game_date >= cutoff_date:
                            recent_games.append(game)
                        break
                    except ValueError:
                        continue
            except:
                # If date parsing fails, include the game
                recent_games.append(game)
        
        return recent_games
    
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


# Usage Example
if __name__ == "__main__":
    scraper = AmherstHockeyScraper(team_id="DSMALL")
    
    # Get all schedule data
    print("Fetching schedule...")
    schedule = scraper.scrape_schedule()
    scraper.export_to_json(schedule, 'schedule.json')
    scraper.export_to_csv(schedule, 'schedule.csv')
    
    # Get last week's games
    print("\\nFetching last week's games...")
    recent_games = scraper.get_recent_games(weeks=1)
    scraper.export_to_json(recent_games, 'recent_games.json')
    
    # Get current week's games (adjust based on your needs)
    print("\\nFetching current week's games...")
    current_week = scraper.get_recent_games(weeks=0)  # Games from this week
    scraper.export_to_json(current_week, 'current_week_games.json')
    
    # Get player statistics
    print("\\nFetching player stats...")
    stats = scraper.scrape_stats(sort_by='points')
    scraper.export_to_json(stats, 'player_stats.json')
    scraper.export_to_csv(stats, 'player_stats.csv')
    
    # Get standings
    print("\\nFetching standings...")
    standings = scraper.scrape_standings()
    scraper.export_to_json(standings, 'standings.json')
    scraper.export_to_csv(standings, 'standings.csv')
    
    print("\\nScraping complete!")
"""

# Save the scraping solution
with open('amherst_hockey_scraper.py', 'w') as f:
    f.write(scraping_solution)

print("Created: amherst_hockey_scraper.py")
print("\nScraper features:")
print("- Scrapes schedule, stats, and standings")
print("- Filters games by date range")
print("- Exports to JSON and CSV")
print("- Handles ASP.NET page structures")
