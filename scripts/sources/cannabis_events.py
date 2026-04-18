"""Scraper for cannabis-specific event sites."""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}

SOURCES = [
    {
        "name": "Cannabis Events Calendar",
        "url": "https://cannabisevent.munchmakers.com/calendar",
        "source_id": "scrape_cannabis_events"
    },
]


def scrape():
    """Scrape cannabis event aggregator sites. Returns list of raw event dicts."""
    candidates = []

    for source in SOURCES:
        try:
            events = _scrape_source(source)
            candidates.extend(events)
            print(f"[Cannabis] Found {len(events)} events from {source['name']}")
        except Exception as e:
            print(f"[Cannabis] Error scraping {source['name']}: {e}")

    return candidates


def _scrape_source(source):
    """Scrape a single cannabis event source."""
    events = []
    resp = requests.get(source["url"], headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Generic approach: look for event-like elements
    event_elements = soup.select(
        ".event-card, .event-item, .event-listing, "
        "[class*='event'], article, .card"
    )

    for el in event_elements:
        try:
            # Find title
            title_el = el.select_one("h2, h3, h4, .title, .event-title, a[class*='title']")
            if not title_el:
                continue

            name = title_el.get_text(strip=True)
            if not name or len(name) < 5:
                continue

            # Skip past events or non-2026
            if "2025" in name and "2026" not in name:
                continue

            # Find link
            link_el = title_el if title_el.name == "a" else el.select_one("a[href]")
            link = link_el.get("href", "") if link_el else ""

            # Find date
            date_el = el.select_one(".date, time, [class*='date']")
            date_text = date_el.get_text(strip=True) if date_el else ""

            # Find location
            loc_el = el.select_one(".location, [class*='location'], [class*='venue']")
            location_text = loc_el.get_text(strip=True) if loc_el else ""

            events.append({
                "name": name,
                "source_url": link if link.startswith("http") else "",
                "date_text": date_text,
                "location_text": location_text,
                "source": source["source_id"],
                "raw_html": str(el)[:500]
            })

        except Exception:
            continue

    return events


if __name__ == "__main__":
    results = scrape()
    for r in results[:10]:
        print(f"  - {r['name']} | {r.get('date_text', '')} | {r.get('location_text', '')}")
