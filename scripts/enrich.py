"""Contact info extraction using Claude. Visits event websites and extracts structured data."""

import json
import re
import requests
from bs4 import BeautifulSoup
import anthropic

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) KPEventsBot/1.0"
}

EXTRACT_PROMPT = """Extract structured event information from this web page content.

Event name: {name}
Page URL: {url}

Page content:
{content}

Extract and return a JSON object with these fields (use empty string if not found):
{{
  "start_date": "YYYY-MM-DD format",
  "end_date": "YYYY-MM-DD format",
  "venue": "venue name",
  "city": "city",
  "state": "state/province abbreviation",
  "country": "two-letter country code (US, CA, DE, etc.)",
  "lat": null or decimal latitude,
  "lng": null or decimal longitude,
  "email": "contact email",
  "phone": "contact phone",
  "website": "official event website URL",
  "description": "one-sentence event description (max 200 chars)"
}}

Respond ONLY with valid JSON, no other text."""


def enrich_event(candidate, api_key):
    """Enrich a single candidate event with contact info and structured data."""
    url = candidate.get("source_url") or candidate.get("event_website", "")
    if not url:
        return candidate

    # Fetch the page
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Remove scripts and styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        page_text = soup.get_text(separator=" ", strip=True)[:4000]

        # Also grab any mailto/tel links directly
        emails = set()
        phones = set()
        for a in soup.select("a[href^='mailto:']"):
            emails.add(a["href"].replace("mailto:", "").split("?")[0])
        for a in soup.select("a[href^='tel:']"):
            phones.add(a["href"].replace("tel:", ""))

        # Use Claude to extract structured info
        client = anthropic.Anthropic(api_key=api_key)
        prompt = EXTRACT_PROMPT.format(
            name=candidate.get("name", ""),
            url=url,
            content=page_text
        )

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )

        result_text = response.content[0].text.strip()

        # Parse JSON
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()

        data = json.loads(result_text)

        # Merge extracted data with candidate
        candidate["enriched"] = data

        # Use directly extracted emails/phones as fallback
        if not data.get("email") and emails:
            data["email"] = list(emails)[0]
        if not data.get("phone") and phones:
            data["phone"] = list(phones)[0]

        candidate["enriched"] = data
        print(f"[Enrich] Enriched: {candidate['name']}")

    except Exception as e:
        print(f"[Enrich] Error enriching {candidate.get('name', '?')}: {e}")

    return candidate


def enrich_batch(candidates, api_key):
    """Enrich a list of candidate events."""
    enriched = []
    for c in candidates:
        enriched.append(enrich_event(c, api_key))
    return enriched
