"""Known trade shows with semi-static dates. Scrape their sites for date updates."""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}

# Known trade shows relevant to King Palm
KNOWN_SHOWS = [
    {
        "name": "Total Product Expo (TPE)",
        "url": "https://totalproductexpo.com/",
        "category": "business"
    },
    {
        "name": "CHAMPS Trade Show",
        "url": "https://champstradeshows.com/",
        "category": "business"
    },
    {
        "name": "Hall of Flowers",
        "url": "https://www.hallofflowers.com/",
        "category": "business"
    },
    {
        "name": "MJBizCon",
        "url": "https://mjbizconference.com/",
        "category": "business"
    },
    {
        "name": "NACS Show",
        "url": "https://www.convenience.org/events",
        "category": "business"
    },
    {
        "name": "Spannabis",
        "url": "https://www.spannabis.com/",
        "category": "business"
    },
    {
        "name": "International Cannabis Business Conference",
        "url": "https://internationalcbc.com/",
        "category": "business"
    },
]


def scrape():
    """Check known trade show sites for updated event info. Returns raw event dicts."""
    candidates = []

    for show in KNOWN_SHOWS:
        try:
            details = _scrape_show_site(show)
            if details:
                candidates.append(details)
                print(f"[Trade] Scraped {show['name']}")
        except Exception as e:
            print(f"[Trade] Error scraping {show['name']}: {e}")

    return candidates


def _scrape_show_site(show):
    """Scrape a trade show website for date and contact info."""
    try:
        resp = requests.get(show["url"], headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        full_text = soup.get_text(separator=" ", strip=True)[:3000]

        # Extract any email addresses
        emails = set()
        for a in soup.select("a[href^='mailto:']"):
            email = a["href"].replace("mailto:", "").split("?")[0]
            emails.add(email)

        # Extract any phone numbers
        phones = set()
        for a in soup.select("a[href^='tel:']"):
            phone = a["href"].replace("tel:", "")
            phones.add(phone)

        return {
            "name": show["name"],
            "source_url": show["url"],
            "category": show["category"],
            "source": "scrape_trade",
            "full_text": full_text,
            "emails": list(emails),
            "phones": list(phones),
        }

    except Exception as e:
        print(f"[Trade] Failed to scrape {show['url']}: {e}")
        return None


if __name__ == "__main__":
    results = scrape()
    for r in results:
        print(f"  - {r['name']} | emails: {r.get('emails', [])} | phones: {r.get('phones', [])}")
