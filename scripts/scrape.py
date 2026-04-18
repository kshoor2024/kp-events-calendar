"""Main scraper orchestrator. Runs all source scrapers, filters, enriches, and updates events.json."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.sources import music_festival_wizard, cannabis_events, trade_shows
from scripts.filter import filter_events
from scripts.enrich import enrich_batch

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
EVENTS_FILE = DATA_DIR / "events.json"
SCRAPE_LOG_FILE = DATA_DIR / "scrape_log.json"

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def load_existing_events():
    """Load existing events from events.json."""
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            data = json.load(f)
            return data.get("events", [])
    return []


def save_events(events):
    """Save events to events.json."""
    data = {
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "events": events
    }
    with open(EVENTS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[Scrape] Saved {len(events)} events to {EVENTS_FILE}")


def save_scrape_log(log_entry):
    """Append to scrape log."""
    log = []
    if SCRAPE_LOG_FILE.exists():
        with open(SCRAPE_LOG_FILE) as f:
            log = json.load(f)

    log.append(log_entry)

    # Keep last 52 entries (1 year of weekly scrapes)
    log = log[-52:]

    with open(SCRAPE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def is_duplicate(candidate, existing_events):
    """Check if a candidate event already exists in our data."""
    candidate_name = candidate.get("name", "").lower().strip()

    for ev in existing_events:
        existing_name = ev.get("name", "").lower().strip()

        # Exact name match
        if candidate_name == existing_name:
            return True

        # Fuzzy: one contains the other and they share a year
        if (candidate_name in existing_name or existing_name in candidate_name):
            if "2026" in candidate_name and "2026" in existing_name:
                return True

    return False


def candidate_to_event(candidate):
    """Convert an enriched candidate into a proper event dict."""
    enriched = candidate.get("enriched", {})

    # Generate ID from name
    event_id = candidate.get("name", "unknown").lower()
    event_id = "".join(c if c.isalnum() or c == " " else "" for c in event_id)
    event_id = event_id.strip().replace(" ", "-")[:50]

    return {
        "id": event_id,
        "name": candidate.get("name", ""),
        "category": candidate.get("ai_category", "end_user"),
        "start_date": enriched.get("start_date", ""),
        "end_date": enriched.get("end_date", ""),
        "location": {
            "venue": enriched.get("venue", ""),
            "city": enriched.get("city", ""),
            "state": enriched.get("state", ""),
            "country": enriched.get("country", "US"),
            "lat": enriched.get("lat"),
            "lng": enriched.get("lng")
        },
        "contact": {
            "email": enriched.get("email", ""),
            "phone": enriched.get("phone", ""),
            "website": enriched.get("website", candidate.get("source_url", ""))
        },
        "description": enriched.get("description", ""),
        "source": candidate.get("source", "scrape"),
        "source_url": candidate.get("source_url", ""),
        "added_date": datetime.now().strftime("%Y-%m-%d"),
        "outreach_status": "not_started",
        "notes": ""
    }


def run():
    """Main scrape pipeline."""
    print("=" * 60)
    print(f"[Scrape] Starting event scrape at {datetime.now().isoformat()}")
    print(f"[Scrape] Dry run: {DRY_RUN}")
    print("=" * 60)

    # 1. Load existing events
    existing = load_existing_events()
    print(f"[Scrape] Existing events: {len(existing)}")

    # 2. Scrape all sources
    print("\n--- Scraping Sources ---")
    all_candidates = []

    mfw_candidates = music_festival_wizard.scrape()
    all_candidates.extend(mfw_candidates)

    cannabis_candidates = cannabis_events.scrape()
    all_candidates.extend(cannabis_candidates)

    trade_candidates = trade_shows.scrape()
    all_candidates.extend(trade_candidates)

    print(f"\n[Scrape] Total raw candidates: {len(all_candidates)}")

    # 3. Deduplicate against existing
    new_candidates = [c for c in all_candidates if not is_duplicate(c, existing)]
    print(f"[Scrape] New candidates (after dedup): {len(new_candidates)}")

    if not new_candidates:
        print("[Scrape] No new events found. Done.")
        save_scrape_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "candidates_found": len(all_candidates),
            "new_candidates": 0,
            "events_added": 0,
            "dry_run": DRY_RUN
        })
        return []

    # 4. Filter with Claude
    if ANTHROPIC_API_KEY:
        print("\n--- Filtering with Claude ---")
        # Fetch details for MFW candidates before filtering
        for c in new_candidates:
            if c.get("source") == "scrape_mfw" and c.get("source_url"):
                details = music_festival_wizard.get_event_details(c["source_url"])
                c.update(details)

        relevant = filter_events(new_candidates, ANTHROPIC_API_KEY)
        print(f"[Scrape] Relevant events after filtering: {len(relevant)}")

        # 5. Enrich with contact info
        print("\n--- Enriching Events ---")
        enriched = enrich_batch(relevant, ANTHROPIC_API_KEY)
    else:
        print("[Scrape] No ANTHROPIC_API_KEY set, skipping filter + enrich")
        enriched = new_candidates

    # 6. Convert to event format and merge
    new_events = [candidate_to_event(c) for c in enriched]

    # Filter out events with no valid date
    new_events = [e for e in new_events if e.get("start_date")]

    print(f"\n[Scrape] New events to add: {len(new_events)}")
    for ev in new_events:
        print(f"  + {ev['name']} ({ev['start_date']}) [{ev['category']}]")

    if not DRY_RUN and new_events:
        all_events = existing + new_events
        # Sort by start_date
        all_events.sort(key=lambda e: e.get("start_date", "9999"))
        save_events(all_events)

    # 7. Log
    save_scrape_log({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidates_found": len(all_candidates),
        "new_candidates": len(new_candidates),
        "relevant_after_filter": len(enriched),
        "events_added": len(new_events),
        "new_event_names": [e["name"] for e in new_events],
        "dry_run": DRY_RUN
    })

    # 8. Send Slack digest (if not dry run)
    if not DRY_RUN:
        try:
            from scripts.slack_digest import send_weekly_digest
            send_weekly_digest(existing + new_events, new_events)
        except Exception as e:
            print(f"[Scrape] Slack digest error: {e}")

    print(f"\n[Scrape] Done. Added {len(new_events)} new events.")
    return new_events


if __name__ == "__main__":
    run()
