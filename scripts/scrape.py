"""Main scraper orchestrator v2 — multi-source metro sweep per Brandon's spec."""

import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent))

from sources import music_festival_wizard, eventbrite, weedmaps_leafly, reddit, cannabis_events, trade_shows
from filter import filter_events
from enrich import enrich_batch

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
CSV_FILE = DATA_DIR / "events_database.csv"
SCRAPE_LOG_FILE = DATA_DIR / "scrape_log.json"

DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
SEND_SLACK = os.environ.get("SEND_SLACK", "0") == "1"

CSV_HEADERS = [
    "Event Name", "Date(s)", "End Date", "City", "State", "Country", "Type",
    "Consumption On-Site", "Participation Cost", "Accepts Free Product",
    "Event Size", "Source URL", "Contact Email or IG", "Contact Name",
    "Date Added", "Status", "Last Touch Date", "Product Sent", "Ship Tracking",
    "Notes", "Priority", "Tags", "Outreach Draft Location", "Content Received"
]

# Load skip list
SKIP_FILE = Path(__file__).parent.parent / "reference" / "skip_list.md"


def load_existing_csv():
    """Load existing events from CSV."""
    if not CSV_FILE.exists():
        return []
    with open(CSV_FILE, newline="") as f:
        return list(csv.DictReader(f))


def save_csv(rows):
    """Save events to CSV."""
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"[Scrape] Saved {len(rows)} events to {CSV_FILE}")


def is_duplicate(candidate_name, existing_rows):
    """Check if an event name already exists in the database."""
    name = candidate_name.lower().strip()
    for row in existing_rows:
        existing = row.get("Event Name", "").lower().strip()
        if name == existing or (len(name) > 10 and name in existing) or (len(existing) > 10 and existing in name):
            return True
    return False


def is_past_event(date_str):
    """Check if a date string is in the past."""
    try:
        if not date_str or date_str == "TBD" or "recurring" in date_str.lower():
            return False
        event_date = datetime.strptime(date_str[:10], "%Y-%m-%d")
        return event_date.date() < datetime.now().date()
    except (ValueError, TypeError):
        return False


def candidate_to_csv_row(candidate):
    """Convert a filtered/enriched candidate to a CSV row."""
    enriched = candidate.get("enriched", {})
    today = datetime.now().strftime("%Y-%m-%d")

    name = candidate.get("name", "")
    category = candidate.get("ai_category", "end_user")
    ev_type = "Business" if category == "business" else "End User"

    # Priority based on type and source quality
    priority = "B"
    if candidate.get("competitor_active"):
        priority = "A"
    elif ev_type == "End User":
        tags = candidate.get("tags", "")
        if any(t in tags for t in ["consumption", "lounge", "sesh", "recurring", "dispensary", "budtender"]):
            priority = "A"

    return {
        "Event Name": name,
        "Date(s)": enriched.get("start_date", candidate.get("date_text", "")),
        "End Date": enriched.get("end_date", ""),
        "City": enriched.get("city", ""),
        "State": enriched.get("state", ""),
        "Country": enriched.get("country", "US"),
        "Type": ev_type,
        "Consumption On-Site": "Unknown",
        "Participation Cost": "$0",
        "Accepts Free Product": "Unknown",
        "Event Size": "",
        "Source URL": candidate.get("source_url", ""),
        "Contact Email or IG": enriched.get("email", ""),
        "Contact Name": "",
        "Date Added": today,
        "Status": "Not contacted",
        "Last Touch Date": "",
        "Product Sent": "",
        "Ship Tracking": "",
        "Notes": enriched.get("description", candidate.get("description", ""))[:300],
        "Priority": priority,
        "Tags": candidate.get("tags", candidate.get("source", "")),
        "Outreach Draft Location": "",
        "Content Received": "",
    }


def run():
    """Main scrape pipeline."""
    print("=" * 60)
    print(f"[Scrape v2] Starting metro sweep at {datetime.now().isoformat()}")
    print(f"[Scrape v2] Dry run: {DRY_RUN}")
    print("=" * 60)

    existing = load_existing_csv()
    print(f"[Scrape v2] Existing events: {len(existing)}")

    # --- Source sweeps ---
    print("\n--- Scraping Sources ---")
    all_candidates = []

    # 1. Eventbrite metro sweep (primary source)
    try:
        eb = eventbrite.scrape(tiers=[1, 2])
        all_candidates.extend(eb)
    except Exception as e:
        print(f"[Scrape v2] Eventbrite error: {e}")

    # 2. Music Festival Wizard (reggae, hip-hop, cannabis genres)
    try:
        mfw = music_festival_wizard.scrape()
        all_candidates.extend(mfw)
    except Exception as e:
        print(f"[Scrape v2] MFW error: {e}")

    # 3. Weedmaps + Leafly
    try:
        wl = weedmaps_leafly.scrape()
        all_candidates.extend(wl)
    except Exception as e:
        print(f"[Scrape v2] Weedmaps/Leafly error: {e}")

    # 4. Reddit cannabis subs
    try:
        rd = reddit.scrape()
        all_candidates.extend(rd)
    except Exception as e:
        print(f"[Scrape v2] Reddit error: {e}")

    # 5. Cannabis event aggregators
    try:
        ce = cannabis_events.scrape()
        all_candidates.extend(ce)
    except Exception as e:
        print(f"[Scrape v2] Cannabis events error: {e}")

    print(f"\n[Scrape v2] Total raw candidates: {len(all_candidates)}")

    # --- Dedup against existing ---
    new_candidates = [c for c in all_candidates if not is_duplicate(c.get("name", ""), existing)]
    print(f"[Scrape v2] New candidates (after dedup): {len(new_candidates)}")

    # --- Hard date filter: never add past events ---
    new_candidates = [c for c in new_candidates if not is_past_event(c.get("date_text", ""))]
    print(f"[Scrape v2] After past-date filter: {len(new_candidates)}")

    if not new_candidates:
        print("[Scrape v2] No new events found.")
        _save_log(len(all_candidates), 0, 0, [])
        return []

    # --- Filter with Claude ---
    if ANTHROPIC_API_KEY:
        print("\n--- Filtering with Claude ---")
        for c in new_candidates:
            if c.get("source") == "scrape_mfw" and c.get("source_url"):
                details = music_festival_wizard.get_event_details(c["source_url"])
                c.update(details)

        relevant = filter_events(new_candidates, ANTHROPIC_API_KEY)
        print(f"[Scrape v2] Relevant after filtering: {len(relevant)}")

        print("\n--- Enriching ---")
        enriched = enrich_batch(relevant, ANTHROPIC_API_KEY)
    else:
        print("[Scrape v2] No ANTHROPIC_API_KEY, skipping filter + enrich")
        enriched = new_candidates

    # --- Convert to CSV rows ---
    new_rows = [candidate_to_csv_row(c) for c in enriched]

    # Filter out rows with no valid future date
    new_rows = [r for r in new_rows if r.get("Event Name")]

    print(f"\n[Scrape v2] New events to add: {len(new_rows)}")
    for r in new_rows:
        print(f"  + {r['Event Name']} ({r['Date(s)']}) [{r['Type']}] P:{r['Priority']}")

    # --- Merge and save ---
    if not DRY_RUN and new_rows:
        all_rows = existing + new_rows

        # Sort: active End User first, then Business, then archived
        def sort_key(r):
            is_archived = "ARCHIVED" in r.get("Status", "")
            is_skip = "Do Not" in r.get("Status", "")
            date = r.get("Date(s)", "9999")
            if is_archived:
                return (2, date)
            if is_skip:
                return (1, date)
            return (0, date)

        all_rows.sort(key=sort_key)
        save_csv(all_rows)

    # --- Log ---
    _save_log(len(all_candidates), len(new_candidates), len(new_rows),
              [r["Event Name"] for r in new_rows])

    # --- Slack digest (Wednesday only) ---
    if not DRY_RUN and SEND_SLACK:
        try:
            from slack_digest import send_weekly_digest
            send_weekly_digest(existing + new_rows, new_rows)
        except Exception as e:
            print(f"[Scrape v2] Slack digest error: {e}")
    elif not SEND_SLACK:
        print("[Scrape v2] Slack digest skipped (not Wednesday or not forced)")

    print(f"\n[Scrape v2] Done. Added {len(new_rows)} new events.")
    return new_rows


def _save_log(candidates, new_candidates, added, names):
    log = []
    if SCRAPE_LOG_FILE.exists():
        with open(SCRAPE_LOG_FILE) as f:
            log = json.load(f)
    log.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "candidates_found": candidates,
        "new_candidates": new_candidates,
        "events_added": added,
        "new_event_names": names,
        "dry_run": DRY_RUN,
    })
    log = log[-52:]
    with open(SCRAPE_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


if __name__ == "__main__":
    run()
