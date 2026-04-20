"""Eventbrite scraper — sweeps cannabis events by metro."""

import requests
from bs4 import BeautifulSoup
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}

# Metro Eventbrite search URLs from Brandon's metros_to_sweep.md
TIER_1_METROS = {
    "Los Angeles, CA": "ca--los-angeles",
    "San Francisco, CA": "ca--san-francisco",
    "San Diego, CA": "ca--san-diego",
    "Denver, CO": "co--denver",
    "Las Vegas, NV": "nv--las-vegas",
    "Phoenix, AZ": "az--phoenix",
    "Seattle, WA": "wa--seattle",
    "Portland, OR": "or--portland",
    "New York, NY": "ny--new-york",
    "Boston, MA": "ma--boston",
}

TIER_2_METROS = {
    "Sacramento, CA": "ca--sacramento",
    "Detroit, MI": "mi--detroit",
    "Chicago, IL": "il--chicago",
    "Newark, NJ": "nj--newark",
    "Washington, DC": "dc--washington",
    "Philadelphia, PA": "pa--philadelphia",
    "Miami, FL": "fl--miami",
}

TIER_3_METROS = {
    "St. Louis, MO": "mo--st-louis",
    "Minneapolis, MN": "mn--minneapolis",
    "Baltimore, MD": "md--baltimore",
    "Columbus, OH": "oh--columbus",
    "Albuquerque, NM": "nm--albuquerque",
}

SEARCH_TERMS = ["cannabis", "420", "sesh", "smoke", "hemp", "dispensary"]


def scrape(tiers=None):
    """Scrape Eventbrite for cannabis events across metros."""
    if tiers is None:
        tiers = [1, 2]  # Default: Tier 1 + 2

    metros = {}
    if 1 in tiers:
        metros.update(TIER_1_METROS)
    if 2 in tiers:
        metros.update(TIER_2_METROS)
    if 3 in tiers:
        metros.update(TIER_3_METROS)

    all_events = []
    seen = set()

    for metro_name, metro_slug in metros.items():
        for term in SEARCH_TERMS[:2]:  # Limit to top 2 terms per metro to stay fast
            try:
                events = _scrape_metro(metro_name, metro_slug, term)
                for ev in events:
                    key = ev["name"].lower().strip()
                    if key not in seen:
                        seen.add(key)
                        all_events.append(ev)
            except Exception as e:
                print(f"[Eventbrite] Error {metro_name}/{term}: {e}")

    print(f"[Eventbrite] Found {len(all_events)} unique events across {len(metros)} metros")
    return all_events


def _scrape_metro(metro_name, metro_slug, search_term):
    """Scrape a single metro + search term combo."""
    events = []
    url = f"https://www.eventbrite.com/d/{metro_slug}/{search_term}/"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        if resp.status_code != 200:
            return events

        soup = BeautifulSoup(resp.text, "lxml")

        # Eventbrite uses structured data or card elements
        cards = soup.select("[data-testid='event-card'], .search-event-card-wrapper, .eds-event-card, article")

        for card in cards[:15]:  # Cap per page
            try:
                # Find title
                title_el = card.select_one("h2, h3, .event-card__formatted-name--is-clamped, [data-testid='event-card-title']")
                if not title_el:
                    continue
                name = title_el.get_text(strip=True)
                if not name or len(name) < 5:
                    continue

                # Find link
                link_el = card.select_one("a[href*='eventbrite.com/e/']")
                link = link_el["href"] if link_el else ""

                # Find date
                date_el = card.select_one("p, [data-testid='event-card-date'], .event-card__date")
                date_text = date_el.get_text(strip=True) if date_el else ""

                # Find location
                loc_el = card.select_one("[data-testid='event-card-location'], .event-card__venue")
                location_text = loc_el.get_text(strip=True) if loc_el else metro_name

                events.append({
                    "name": name,
                    "source_url": link,
                    "date_text": date_text,
                    "location_text": location_text,
                    "metro": metro_name,
                    "source": "eventbrite",
                    "search_term": search_term,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"[Eventbrite] Request failed {url}: {e}")

    return events


if __name__ == "__main__":
    results = scrape(tiers=[1])
    for r in results[:20]:
        print(f"  - {r['name']} | {r.get('date_text', '')} | {r['metro']}")
