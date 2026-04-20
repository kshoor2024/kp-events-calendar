"""Weedmaps and Leafly event scrapers."""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}

WEEDMAPS_URLS = [
    "https://weedmaps.com/events",
]

LEAFLY_URLS = [
    "https://www.leafly.com/events",
]


def scrape():
    """Scrape Weedmaps and Leafly for cannabis events."""
    all_events = []

    # Weedmaps events
    for url in WEEDMAPS_URLS:
        try:
            events = _scrape_page(url, "weedmaps")
            all_events.extend(events)
            print(f"[Weedmaps] Found {len(events)} events")
        except Exception as e:
            print(f"[Weedmaps] Error: {e}")

    # Leafly events
    for url in LEAFLY_URLS:
        try:
            events = _scrape_page(url, "leafly")
            all_events.extend(events)
            print(f"[Leafly] Found {len(events)} events")
        except Exception as e:
            print(f"[Leafly] Error: {e}")

    return all_events


def _scrape_page(url, source):
    """Generic event page scraper."""
    events = []
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            print(f"[{source}] Status {resp.status_code} for {url}")
            return events

        soup = BeautifulSoup(resp.text, "lxml")

        # Look for event cards/articles
        cards = soup.select("article, .event-card, [class*='event'], .card")

        for card in cards[:30]:
            try:
                title_el = card.select_one("h2, h3, h4, a[class*='title'], .title")
                if not title_el:
                    continue

                name = title_el.get_text(strip=True)
                if not name or len(name) < 5:
                    continue

                link_el = title_el if title_el.name == "a" else card.select_one("a[href]")
                link = link_el.get("href", "") if link_el else ""
                if link and not link.startswith("http"):
                    link = f"https://{source}.com{link}"

                date_el = card.select_one("time, [class*='date'], .date")
                date_text = date_el.get_text(strip=True) if date_el else ""

                loc_el = card.select_one("[class*='location'], .location, .venue")
                loc_text = loc_el.get_text(strip=True) if loc_el else ""

                events.append({
                    "name": name,
                    "source_url": link,
                    "date_text": date_text,
                    "location_text": loc_text,
                    "source": source,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"[{source}] Error scraping {url}: {e}")

    return events


if __name__ == "__main__":
    results = scrape()
    for r in results[:10]:
        print(f"  - [{r['source']}] {r['name']} | {r.get('date_text', '')}")
