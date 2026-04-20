"""Outreach draft engine — generates personalized outreach drafts using Brandon's 7 templates."""

import json
import os
from pathlib import Path
import anthropic

TEMPLATES_FILE = Path(__file__).parent.parent / "reference" / "outreach_templates.md"

DRAFT_PROMPT = """You are Kate from King Palm, drafting outreach messages for cannabis events.

RULES (from Brandon — follow exactly):
- Lead with what we're bringing (product their attendees will love)
- Mention King Palm's scale (5,000+ shops nationally) as context, not a brag
- Leave the door open for bigger conversations
- Sound warm, direct, confident — NOT corporate or apologetic
- NEVER say "free", "at no cost", "we can't pay", "we don't have budget"
- Kate reviews every draft — make it 90% ready so she changes 1-2 words max

EVENT DETAILS:
Name: {name}
Date: {date}
City: {city}, {state}
Type: {event_type}
Size: {size}
Consumption On-Site: {consumption}
Contact: {contact}
Notes: {notes}
Tags: {tags}

Choose the right template style:
- Sesh / small recurring → short IG DM style
- Festival / cup / party with email → Event Email style
- Dispensary event → Dispensary Recurring style
- Consumption lounge → Lounge Recurring style
- Budtender event → Budtender Event style
- Big festival (Rolling Loud, Coachella, etc.) → Big Festival style

Write the draft outreach message. Include a subject line if it's an email. Use conversational contractions. Reference something specific about the event if possible. Close with a low-pressure next step.

Output ONLY the draft message, nothing else."""


def generate_outreach_drafts(events_csv_rows, api_key):
    """Generate outreach drafts for new End User events that haven't been contacted."""
    client = anthropic.Anthropic(api_key=api_key)
    drafts = []

    for row in events_csv_rows:
        # Only draft for End User events that haven't been contacted
        if row.get("Type") != "End User":
            continue
        if row.get("Status", "").lower() not in ("not contacted", "not_started"):
            continue
        if row.get("Outreach Draft Location"):  # Already has a draft
            continue

        name = row.get("Event Name", "")
        if not name:
            continue

        prompt = DRAFT_PROMPT.format(
            name=name,
            date=row.get("Date(s)", "TBD"),
            city=row.get("City", ""),
            state=row.get("State", ""),
            event_type=row.get("Type", ""),
            size=row.get("Event Size", "Unknown"),
            consumption=row.get("Consumption On-Site", "Unknown"),
            contact=row.get("Contact Email or IG", "Unknown"),
            notes=row.get("Notes", ""),
            tags=row.get("Tags", ""),
        )

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=800,
                messages=[{"role": "user", "content": prompt}]
            )
            draft = response.content[0].text.strip()

            drafts.append({
                "event_name": name,
                "contact": row.get("Contact Email or IG", ""),
                "draft": draft,
                "generated_at": row.get("Date Added", ""),
            })

            print(f"[Outreach] Drafted: {name}")
        except Exception as e:
            print(f"[Outreach] Error drafting {name}: {e}")

    return drafts


def save_drafts(drafts, output_dir=None):
    """Save drafts to a JSON file for Kate to review."""
    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "data" / "outreach_drafts"
    output_dir.mkdir(parents=True, exist_ok=True)

    from datetime import datetime
    filename = f"drafts_{datetime.now().strftime('%Y-%m-%d')}.json"
    filepath = output_dir / filename

    with open(filepath, "w") as f:
        json.dump(drafts, f, indent=2)

    print(f"[Outreach] Saved {len(drafts)} drafts to {filepath}")
    return filepath


if __name__ == "__main__":
    import csv
    from dotenv import load_dotenv
    load_dotenv()

    csv_file = Path(__file__).parent.parent / "data" / "events_database.csv"
    with open(csv_file) as f:
        rows = list(csv.DictReader(f))

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        drafts = generate_outreach_drafts(rows, api_key)
        if drafts:
            save_drafts(drafts)
    else:
        print("[Outreach] No ANTHROPIC_API_KEY set")
