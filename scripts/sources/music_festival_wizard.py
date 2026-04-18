"""Scraper for Music Festival Wizard (musicfestivalwizard.com)"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

BASE_URL = "https://www.musicfestivalwizard.com"

# Genres and keywords that signal relevant events
RELEVANT_GENRES = ["reggae", "hip-hop", "hip hop", "r&b"]
RELEVANT_KEYWORDS = [
    "cannabis", "420", "hemp", "smoke", "weed", "marijuana",
    "counterculture", "adult", "21+", "21 and over",
    "reggae", "dub", "roots", "dancehall"
]

GENRE_URLS = [
    f"{BASE_URL}/festival-genre/reggae/",
    f"{BASE_URL}/festival-genre/hip-hop/",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}


def scrape():
    """Scrape Music Festival Wizard for relevant festivals. Returns list of raw event dicts."""
    candidates = []

    for genre_url in GENRE_URLS:
        try:
            candidates.extend(_scrape_genre_page(genre_url))
        except Exception as e:
            print(f"[MFW] Error scraping {genre_url}: {e}")

    # Also search for cannabis/smoke-specific festivals
    search_terms = ["cannabis", "420", "smoke"]
    for term in search_terms:
        try:
            candidates.extend(_scrape_search(term))
        except Exception as e:
            print(f"[MFW] Error searching '{term}': {e}")

    # Deduplicate by name
    seen = set()
    unique = []
    for c in candidates:
        key = c["name"].lower().strip()
        if key not in seen:
            seen.add(key)
            unique.append(c)

    print(f"[MFW] Found {len(unique)} unique candidate events")
    return unique


def _scrape_genre_page(url):
    """Scrape a genre listing page for festival entries."""
    events = []
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # MFW uses article cards for festival listings
    articles = soup.select("article, .festival-card, .search-results-item, .entry")

    for article in articles:
        try:
            event = _parse_article(article)
            if event:
                events.append(event)
        except Exception as e:
            print(f"[MFW] Error parsing article: {e}")
            continue

    # Check for pagination
    next_link = soup.select_one("a.next, .nav-next a, a.pagination-next")
    if next_link and next_link.get("href"):
        try:
            events.extend(_scrape_genre_page(next_link["href"]))
        except Exception:
            pass

    return events


def _scrape_search(term):
    """Search MFW for a specific term."""
    events = []
    url = f"{BASE_URL}/?s={term}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        articles = soup.select("article, .festival-card, .search-results-item, .entry")
        for article in articles:
            try:
                event = _parse_article(article)
                if event:
                    events.append(event)
            except Exception:
                continue
    except Exception as e:
        print(f"[MFW] Search error for '{term}': {e}")

    return events


def _parse_article(article):
    """Parse a single article/card element into an event dict."""
    # Find title and link
    title_el = article.select_one("h2 a, h3 a, .entry-title a, a.festival-title")
    if not title_el:
        return None

    name = title_el.get_text(strip=True)
    link = title_el.get("href", "")

    if not name or not link:
        return None

    # Skip if it looks like a non-2026 event
    if "2025" in name and "2026" not in name:
        return None

    # Extract date text
    date_text = ""
    date_el = article.select_one(".festival-date, .entry-date, time, .date")
    if date_el:
        date_text = date_el.get_text(strip=True)

    # Extract location
    location_text = ""
    loc_el = article.select_one(".festival-location, .location, .entry-location")
    if loc_el:
        location_text = loc_el.get_text(strip=True)

    return {
        "name": name,
        "source_url": link if link.startswith("http") else f"{BASE_URL}{link}",
        "date_text": date_text,
        "location_text": location_text,
        "source": "scrape_mfw",
        "raw_html": str(article)[:500]
    }


def get_event_details(url):
    """Fetch detailed info from an individual festival page."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        details = {"source_url": url}

        # Get description
        desc_el = soup.select_one(".entry-content, .festival-description, article .content")
        if desc_el:
            details["description"] = desc_el.get_text(strip=True)[:500]

        # Look for dates
        date_el = soup.select_one(".festival-date, .event-date, time")
        if date_el:
            details["date_text"] = date_el.get_text(strip=True)

        # Look for location
        loc_el = soup.select_one(".festival-location, .event-location, .location")
        if loc_el:
            details["location_text"] = loc_el.get_text(strip=True)

        # Look for website links (external links to the actual event)
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            text = a.get_text(strip=True).lower()
            if ("official" in text or "website" in text or "tickets" in text) and "musicfestivalwizard" not in href:
                details["event_website"] = href
                break

        # Get full page text for AI filtering
        details["full_text"] = soup.get_text(separator=" ", strip=True)[:2000]

        return details

    except Exception as e:
        print(f"[MFW] Error fetching details from {url}: {e}")
        return {"source_url": url}


if __name__ == "__main__":
    results = scrape()
    for r in results[:10]:
        print(f"  - {r['name']} | {r.get('date_text', 'no date')} | {r.get('location_text', 'no location')}")
