"""Claude-powered event filtering. Determines if scraped events are relevant for King Palm."""

import json
import anthropic


FILTER_PROMPT = """You are an event curator for King Palm, a premium pre-rolled cone and smoking accessories brand.

Evaluate each candidate event and determine if it's relevant for King Palm to attend or sponsor.

INCLUDE events that meet ALL of these criteria:
- 21+ or adult-oriented (NOT family/kids/all-ages events)
- Related to: cannabis, smoke, hemp, CBD, reggae music, counterculture, tobacco/vape trade
- Mid-to-large scale (NOT small local meetups under ~500 people)
- Located in the US (primary focus, ~80%) OR in emerging international cannabis markets (Germany, Thailand, Canada, Spain, Netherlands, etc.) if mid-to-large scale

EXCLUDE events that are:
- Family-friendly / all-ages / kids events
- Small local meetups or private parties
- Religious or political events
- Events with no clear cannabis/smoke/reggae connection
- Events in countries with strict cannabis prohibition and no reform movement

For each event, respond with a JSON array. Each item should have:
- "name": the event name
- "relevant": true/false
- "reason": brief reason for inclusion/exclusion
- "category": "business" or "end_user" (business = trade shows, B2B expos; end_user = festivals, consumer events)
- "adult_only": true/false (is this 21+ or adult-oriented?)

Events to evaluate:
{events}

Respond ONLY with a valid JSON array, no other text."""


def filter_events(candidates, api_key):
    """Filter candidate events using Claude. Returns list of relevant event dicts."""
    if not candidates:
        return []

    client = anthropic.Anthropic(api_key=api_key)

    # Process in batches of 15
    batch_size = 15
    relevant = []

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i:i + batch_size]

        # Build event summaries for the prompt
        event_summaries = []
        for ev in batch:
            summary = {
                "name": ev.get("name", ""),
                "date": ev.get("date_text", ""),
                "location": ev.get("location_text", ""),
                "description": ev.get("full_text", ev.get("raw_html", ""))[:300]
            }
            event_summaries.append(summary)

        prompt = FILTER_PROMPT.format(events=json.dumps(event_summaries, indent=2))

        try:
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}]
            )

            result_text = response.content[0].text.strip()

            # Parse JSON from response (handle markdown code blocks)
            if result_text.startswith("```"):
                result_text = result_text.split("```")[1]
                if result_text.startswith("json"):
                    result_text = result_text[4:]
                result_text = result_text.strip()

            results = json.loads(result_text)

            for j, result in enumerate(results):
                if result.get("relevant") and j < len(batch):
                    batch[j]["ai_category"] = result.get("category", "end_user")
                    batch[j]["ai_reason"] = result.get("reason", "")
                    batch[j]["ai_adult_only"] = result.get("adult_only", False)
                    relevant.append(batch[j])

            print(f"[Filter] Batch {i // batch_size + 1}: {len([r for r in results if r.get('relevant')])} relevant out of {len(batch)}")

        except Exception as e:
            print(f"[Filter] Error processing batch: {e}")
            continue

    return relevant
