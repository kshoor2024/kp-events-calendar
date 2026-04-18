"""Weekly Slack digest for #kp-events channel."""

import os
import math
from datetime import datetime
from slack_sdk import WebClient

SLACK_CHANNEL = "C0434HK1077"  # #kp-events


def get_urgency(start_date_str):
    """Calculate urgency level for an event."""
    try:
        start = datetime.strptime(start_date_str, "%Y-%m-%d")
        days = (start - datetime.now()).days
        if days < 0:
            return "past", days
        if days < 14:
            return "urgent", days
        if days <= 45:
            return "soon", days
        return "comfortable", days
    except (ValueError, TypeError):
        return "unknown", 0


def format_event_line(ev):
    """Format a single event for the Slack digest."""
    date_range = ev.get("start_date", "TBD")
    if ev.get("end_date") and ev["end_date"] != ev["start_date"]:
        # Shorten to "May 6-9"
        try:
            start = datetime.strptime(ev["start_date"], "%Y-%m-%d")
            end = datetime.strptime(ev["end_date"], "%Y-%m-%d")
            if start.month == end.month:
                date_range = f"{start.strftime('%b')} {start.day}-{end.day}"
            else:
                date_range = f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"
        except ValueError:
            date_range = f"{ev['start_date']} to {ev['end_date']}"

    location = ""
    loc = ev.get("location", {})
    if loc.get("city"):
        location = loc["city"]
        if loc.get("state"):
            location += f", {loc['state']}"
        elif loc.get("country") and loc["country"] != "US":
            location += f", {loc['country']}"

    category = "Business" if ev.get("category") == "business" else "End User"
    outreach = ev.get("outreach_status", "not_started")
    outreach_labels = {
        "not_started": ":white_circle: not started",
        "contacted": ":large_yellow_circle: contacted",
        "confirmed": ":white_check_mark: confirmed",
        "declined": ":no_entry_sign: declined"
    }

    contact_str = ""
    contact = ev.get("contact", {})
    if contact.get("email"):
        contact_str = f" | {contact['email']}"
    elif contact.get("website"):
        contact_str = f" | <{contact['website']}|website>"

    return f"• *{ev['name']}* — {location} ({date_range}) [{category}]\n  Outreach: {outreach_labels.get(outreach, outreach)}{contact_str}"


def build_digest_message(all_events, new_events=None):
    """Build the full Slack digest message."""
    today = datetime.now().strftime("%A, %B %d, %Y")

    # Categorize events by urgency
    urgent = []
    soon = []
    comfortable = []
    past_count = 0

    for ev in all_events:
        level, days = get_urgency(ev.get("start_date", ""))
        if level == "urgent":
            urgent.append((ev, days))
        elif level == "soon":
            soon.append((ev, days))
        elif level == "comfortable":
            comfortable.append((ev, days))
        elif level == "past":
            past_count += 1

    # Sort each group by days (soonest first)
    urgent.sort(key=lambda x: x[1])
    soon.sort(key=lambda x: x[1])
    comfortable.sort(key=lambda x: x[1])

    blocks = [
        f":palm_tree: *KP Events Calendar — Weekly Digest*\n{today}\n"
    ]

    if urgent:
        blocks.append(":red_circle: *URGENT — Under 14 Days*")
        for ev, days in urgent:
            blocks.append(format_event_line(ev))
        blocks.append("")

    if soon:
        blocks.append(":large_yellow_circle: *COMING UP — 15-45 Days*")
        for ev, days in soon:
            blocks.append(format_event_line(ev))
        blocks.append("")

    if comfortable:
        blocks.append(":large_green_circle: *ON THE HORIZON — 45+ Days*")
        for ev, days in comfortable[:10]:  # Cap at 10 for readability
            blocks.append(format_event_line(ev))
        if len(comfortable) > 10:
            blocks.append(f"  _...and {len(comfortable) - 10} more_")
        blocks.append("")

    # New events section
    if new_events:
        blocks.append(f":new: *New Events Found This Week:* {len(new_events)}")
        for ev in new_events:
            blocks.append(f"  + {ev['name']} ({ev.get('start_date', 'TBD')})")
        blocks.append("")

    # Summary
    total_active = len(urgent) + len(soon) + len(comfortable)
    blocks.append(f":bar_chart: *Summary:* {total_active} upcoming | {past_count} past | {len(urgent)} need immediate attention")

    # Link to calendar
    blocks.append("\n:link: <https://kshoor.github.io/kp-events-calendar/|View Full Calendar>")

    return "\n".join(blocks)


def send_weekly_digest(all_events, new_events=None):
    """Send the weekly digest to Slack."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("[Slack] No SLACK_BOT_TOKEN set, skipping digest")
        return

    message = build_digest_message(all_events, new_events)

    client = WebClient(token=token)
    try:
        result = client.chat_postMessage(
            channel=SLACK_CHANNEL,
            text=message,
            mrkdwn=True
        )
        print(f"[Slack] Digest sent to #{SLACK_CHANNEL}: {result['ts']}")
    except Exception as e:
        print(f"[Slack] Error sending digest: {e}")


if __name__ == "__main__":
    import json
    from pathlib import Path

    events_file = Path(__file__).parent.parent / "data" / "events.json"
    with open(events_file) as f:
        data = json.load(f)

    message = build_digest_message(data.get("events", []))
    print(message)
