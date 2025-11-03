
# Create a quick-start diagnostic script that the user can run first

diagnostic_script = """#!/usr/bin/env python3
'''
Diagnostic Script for Amherst Adult Hockey Website
Run this first to determine the best scraping approach
'''

import requests
from bs4 import BeautifulSoup
import json
from typing import Dict, List

def analyze_page(url: str, page_name: str) -> Dict:
    '''Analyze a page to determine scraping strategy'''
    print(f"\\n{'='*60}")
    print(f"Analyzing: {page_name}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        # Fetch the page
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        print(f"✓ Page loaded successfully (Status: {response.status_code})")
        print(f"✓ Content length: {len(response.text)} characters")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Analyze tables
        tables = soup.find_all('table')
        print(f"\\n📊 Found {len(tables)} table(s)")
        
        if not tables:
            print("⚠️  No tables found - data may be loaded via JavaScript")
            print("   → Recommendation: Use Playwright/Selenium approach")
            return {'success': False, 'method': 'playwright', 'tables': 0}
        
        # Analyze each table
        table_info = []
        for idx, table in enumerate(tables):
            rows = table.find_all('tr')
            if not rows:
                continue
                
            print(f"\\n  Table {idx + 1}:")
            print(f"    - Rows: {len(rows)}")
            print(f"    - Class: {table.get('class', 'none')}")
            print(f"    - ID: {table.get('id', 'none')}")
            
            # Get first few rows
            sample_rows = []
            for i, row in enumerate(rows[:3]):
                cells = row.find_all(['td', 'th'])
                if cells:
                    cell_texts = [cell.get_text(strip=True)[:30] for cell in cells[:5]]
                    sample_rows.append(cell_texts)
                    print(f"    - Row {i}: {len(cells)} cells - {cell_texts}")
            
            table_info.append({
                'index': idx,
                'rows': len(rows),
                'sample': sample_rows,
                'class': table.get('class'),
                'id': table.get('id')
            })
        
        # Check for JavaScript content
        scripts = soup.find_all('script')
        print(f"\\n📜 Found {len(scripts)} script tags")
        
        # Check for common AJAX/dynamic loading patterns
        ajax_indicators = [
            'ajax', 'fetch', 'XMLHttpRequest', 'axios',
            'jquery', 'react', 'angular', 'vue'
        ]
        
        page_text = response.text.lower()
        found_indicators = [ind for ind in ajax_indicators if ind in page_text]
        
        if found_indicators:
            print(f"⚠️  Detected JavaScript frameworks/libraries: {', '.join(found_indicators)}")
            print("   → Data might be loaded dynamically")
        
        # Determine recommendation
        if len(tables) > 0 and any(len(t.find_all('tr')) > 1 for t in tables):
            print(f"\\n✅ Recommendation: BeautifulSoup approach should work!")
            print("   → Data appears to be in HTML source")
            method = 'beautifulsoup'
        else:
            print(f"\\n⚠️  Recommendation: Use Playwright/Selenium")
            print("   → Tables are empty or data is JavaScript-loaded")
            method = 'playwright'
        
        return {
            'success': True,
            'method': method,
            'tables': len(tables),
            'table_info': table_info,
            'js_frameworks': found_indicators
        }
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Error fetching page: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"✗ Error analyzing page: {e}")
        return {'success': False, 'error': str(e)}


def main():
    '''Run diagnostic on all three pages'''
    print("\\n" + "="*60)
    print("AMHERST ADULT HOCKEY WEBSITE DIAGNOSTIC")
    print("="*60)
    
    team_id = "DSMALL"
    base_url = "https://www.amherstadulthockey.com/teams/default.asp"
    
    pages = [
        {
            'name': 'Schedule',
            'url': f"{base_url}?u={team_id}&s=hockey&p=schedule&format=List&d=ALL"
        },
        {
            'name': 'Player Statistics',
            'url': f"{base_url}?u={team_id}&s=hockey&p=stats&psort=points"
        },
        {
            'name': 'Standings',
            'url': f"{base_url}?u={team_id}&s=hockey&p=standings"
        }
    ]
    
    results = {}
    for page in pages:
        result = analyze_page(page['url'], page['name'])
        results[page['name']] = result
    
    # Summary
    print("\\n\\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    
    methods = [r.get('method') for r in results.values() if r.get('success')]
    
    if methods:
        if all(m == 'beautifulsoup' for m in methods):
            print("\\n✅ RECOMMENDATION: Use BeautifulSoup Approach")
            print("\\n   All pages have data in HTML source.")
            print("   Run: python amherst_hockey_scraper.py")
        elif all(m == 'playwright' for m in methods):
            print("\\n⚠️  RECOMMENDATION: Use Playwright Approach")
            print("\\n   Pages use JavaScript to load data.")
            print("   Install: pip install playwright")
            print("   Install: playwright install chromium")
            print("   Run: python amherst_hockey_scraper_playwright.py")
        else:
            print("\\n⚠️  RECOMMENDATION: Hybrid Approach")
            print("\\n   Some pages work with BeautifulSoup, others need Playwright.")
            print("   Start with BeautifulSoup and fall back to Playwright if needed.")
    else:
        print("\\n✗ Could not analyze pages. Check your internet connection.")
    
    # Save diagnostic results
    with open('diagnostic_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print("\\n📄 Detailed results saved to: diagnostic_results.json")
    
    print("\\n" + "="*60)
    print("NEXT STEPS")
    print("="*60)
    print("1. Review the diagnostic results above")
    print("2. Choose the recommended scraping approach")
    print("3. Run the appropriate scraper script")
    print("4. Check the output JSON/CSV files")
    print("\\nFor more details, see: IMPLEMENTATION_GUIDE.md")
    print("="*60 + "\\n")


if __name__ == "__main__":
    main()
"""

with open('diagnostic_check.py', 'w') as f:
    f.write(diagnostic_script)

print("✅ Created: diagnostic_check.py")
print("\n" + "="*60)
print("FILES CREATED")
print("="*60)
print("\n1. amherst_hockey_scraper.py")
print("   → BeautifulSoup-based scraper (fast, for static content)")
print("\n2. amherst_hockey_scraper_playwright.py")
print("   → Playwright-based scraper (for JavaScript-heavy pages)")
print("\n3. diagnostic_check.py")
print("   → Run this FIRST to determine which approach to use")
print("\n4. IMPLEMENTATION_GUIDE.md")
print("   → Complete guide with examples and best practices")
print("\n" + "="*60)
