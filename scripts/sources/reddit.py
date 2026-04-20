"""Reddit cannabis event scraper — searches cannabis subreddits for event posts."""

import requests
from datetime import datetime

HEADERS = {
    "User-Agent": "KPEventsBot/1.0 (event sourcing)"
}

# Subreddits from Brandon's metros_to_sweep.md
SUBREDDITS = [
    "LAcannabis", "BayAreaCannabis", "cocannabis",
    "azcannabis", "wacannabis", "orcannabis",
    "nycweed", "nyccannabis", "massgrowing",
    "michigents", "ILTrees", "njweed",
]

SEARCH_TERMS = ["event", "sesh", "420", "cup", "festival", "popup", "pop up"]


def scrape():
    """Search cannabis subreddits for event-related posts."""
    all_events = []
    seen = set()

    for sub in SUBREDDITS:
        for term in SEARCH_TERMS[:3]:  # Limit to avoid rate limiting
            try:
                events = _search_subreddit(sub, term)
                for ev in events:
                    key = ev["name"].lower().strip()
                    if key not in seen:
                        seen.add(key)
                        all_events.append(ev)
            except Exception as e:
                print(f"[Reddit] Error r/{sub}/{term}: {e}")

    print(f"[Reddit] Found {len(all_events)} unique event posts across {len(SUBREDDITS)} subreddits")
    return all_events


def _search_subreddit(subreddit, term):
    """Search a subreddit for event-related posts."""
    events = []
    url = f"https://www.reddit.com/r/{subreddit}/search.json"
    params = {
        "q": term,
        "sort": "new",
        "t": "month",  # Last month
        "limit": 10,
        "restrict_sr": "true",
    }

    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        if resp.status_code != 200:
            return events

        data = resp.json()
        posts = data.get("data", {}).get("children", [])

        for post in posts:
            p = post.get("data", {})
            title = p.get("title", "")
            selftext = p.get("selftext", "")[:500]
            url = p.get("url", "")
            permalink = f"https://www.reddit.com{p.get('permalink', '')}"
            created = datetime.fromtimestamp(p.get("created_utc", 0))

            # Filter for actual events (not just discussion)
            text_lower = (title + " " + selftext).lower()
            is_event = any(kw in text_lower for kw in [
                "event", "sesh", "come through", "pop up", "popup",
                "this weekend", "this saturday", "this friday",
                "next week", "hosting", "join us", "rsvp",
                "tickets", "free entry", "consumption lounge",
            ])

            if not is_event:
                continue

            events.append({
                "name": title[:100],
                "source_url": permalink,
                "date_text": created.strftime("%Y-%m-%d"),
                "location_text": f"r/{subreddit}",
                "source": "reddit",
                "subreddit": subreddit,
                "description": selftext[:200],
            })

    except Exception as e:
        print(f"[Reddit] Request failed r/{subreddit}: {e}")

    return events


if __name__ == "__main__":
    results = scrape()
    for r in results[:10]:
        print(f"  - [r/{r['subreddit']}] {r['name'][:60]}")
