
import requests
from bs4 import BeautifulSoup
import json

# Let's try to fetch and analyze the schedule page structure
url = "https://www.amherstadulthockey.com/teams/default.asp?u=DSMALL&s=hockey&p=schedule&format=List&d=ALL"

try:
    response = requests.get(url)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Look for tables
    tables = soup.find_all('table')
    print(f"Found {len(tables)} tables on the page")
    
    # Find the schedule table - let's examine the first few tables
    for idx, table in enumerate(tables[:3]):
        print(f"\n--- Table {idx} ---")
        print(f"Classes: {table.get('class')}")
        print(f"ID: {table.get('id')}")
        
        # Get first few rows to understand structure
        rows = table.find_all('tr')[:3]
        print(f"Number of rows (sample): {len(rows)}")
        
        for row_idx, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            print(f"Row {row_idx}: {len(cells)} cells")
            if cells:
                print(f"  Cell contents: {[cell.get_text(strip=True)[:50] for cell in cells[:5]]}")
    
except Exception as e:
    print(f"Error fetching schedule: {e}")
