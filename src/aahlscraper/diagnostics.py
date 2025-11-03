"""
Diagnostic helpers to determine which scraping strategy to use.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from .common import build_url

AJAX_INDICATORS = ("ajax", "fetch", "xmlhttprequest", "axios", "jquery", "react", "angular", "vue")


def _summarize_table(table: Tag) -> Dict[str, Any]:
    rows = table.find_all("tr")
    summary: Dict[str, Any] = {
        "rows": len(rows),
        "class": table.get("class"),
        "id": table.get("id"),
        "sample": [],
    }

    for row in rows[:3]:
        cells = row.find_all(["td", "th"])
        summary["sample"].append([cell.get_text(strip=True)[:30] for cell in cells[:5]])

    return summary


def analyze_page(team_id: str, page_type: str, label: str, **params: str) -> Dict[str, Any]:
    """
    Fetch a page and inspect the structure to recommend a scraping strategy.
    """
    url = build_url(team_id, page_type, **params)
    result: Dict[str, Any] = {
        "label": label,
        "url": url,
        "success": False,
        "method": None,
        "tables": 0,
        "table_info": [],
        "js_frameworks": [],
    }

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException as exc:
        result["error"] = str(exc)
        return result

    result["success"] = True
    result["status_code"] = response.status_code
    result["content_length"] = len(response.text)

    soup = BeautifulSoup(response.text, "html.parser")
    tables = soup.find_all("table")
    result["tables"] = len(tables)
    result["table_info"] = [_summarize_table(table) for table in tables]

    # Determine scraping method
    if tables and any(len(table.find_all("tr")) > 1 for table in tables):
        result["method"] = "beautifulsoup"
    else:
        result["method"] = "playwright"

    content_lower = response.text.lower()
    result["js_frameworks"] = [indicator for indicator in AJAX_INDICATORS if indicator in content_lower]

    return result


def run_diagnostics(team_id: str = "DSMALL") -> Dict[str, Dict[str, Any]]:
    """
    Run diagnostics on the schedule, stats, and standings pages.
    """
    pages = (
        ("schedule", "Schedule", {"format": "List", "d": "ALL"}),
        ("stats", "Player Statistics", {"psort": "points"}),
        ("standings", "Standings", {}),
    )

    results: Dict[str, Dict[str, Any]] = {}
    for page_type, label, params in pages:
        results[label] = analyze_page(team_id, page_type, label, **params)
    return results


def summarize_recommendation(results: Dict[str, Dict[str, Any]]) -> str:
    """
    Produce a human-readable summary recommendation based on diagnostic results.
    """
    methods = [result.get("method") for result in results.values() if result.get("success")]

    if not methods:
        return "Could not analyze pages. Please check connectivity."

    if all(method == "beautifulsoup" for method in methods):
        return "Use the HTTP (BeautifulSoup) scraper."
    if all(method == "playwright" for method in methods):
        return "Use the Playwright scraper."
    return "Use a hybrid approach: prefer HTTP scraping and fall back to Playwright as needed."
