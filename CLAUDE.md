# KP Events Calendar v2

Internal King Palm event tracking + outreach automation per Brandon's v2.2 spec.

## Architecture
- `index.html`, `app.js`, `styles.css` — Frontend (GitHub Pages, zero build)
- `data/events_database.csv` — Source of truth (23-column schema)
- `data/outreach_drafts/` — Auto-generated draft emails for Kate
- `scripts/` — Python scraping/filtering/enrichment/outreach pipeline
- `reference/` — Brandon's spec files (skip list, outreach philosophy, templates, metros)
- `.github/workflows/` — 4 scheduled GitHub Actions tasks

## Data Schema (CSV)
Event Name, Date(s), End Date, City, State, Country, Type, Consumption On-Site,
Participation Cost, Accepts Free Product, Event Size, Source URL,
Contact Email or IG, Contact Name, Date Added, Status, Last Touch Date,
Product Sent, Ship Tracking, Notes, Priority, Tags, Outreach Draft Location, Content Received

## Two-Track System
- **End User** — consumer events. Full outreach. Cowork drafts messages. Kate reviews and sends.
- **Business** — trade shows. Calendar visibility only. Tagged "Do Not Outreach — Business".

## Priority System
- **A** — consumption lounges, dispensary events, budtender events, recurring seshes, cups, competitor-active events
- **B** — festivals, one-off parties, concerts
- **C** — big festivals (hospitality angle only), business events, international

## 4 Scheduled Tasks (GitHub Actions)
1. **Friday 9am PT** — Weekly metro sweep (Eventbrite, MFW, Weedmaps, Leafly, Reddit) + outreach drafts
2. **Tuesday 10am PT** — Contact enrichment for events with missing email/IG
3. **1st of month 8am PT** — Auto-archive past events, flag stalled outreach
4. **Mar 20, Jun 10, Oct 15, Nov 15** — Surge sweeps (pre-420, pre-710, Q4 next-year hunt)

## Scraper Sources (no IG — skipped per Kay)
- Eventbrite (22 metros, cannabis/420/sesh/smoke searches)
- Music Festival Wizard (reggae, hip-hop, cannabis genres)
- Weedmaps events page
- Leafly events page
- Reddit cannabis subreddits (12 subs)
- Cannabis event aggregators

## Skip List (never outreach)
- Trade shows: CHAMPS, MJBizCon, TPE, NACS, HoF, NECANN, CannaCon, MJ Unpacked
- International: Spannabis, ICBC Berlin, Mary Jane Berlin, InterTabac, etc.
- Dead 2026: Hippie Hill, Seattle Hempfest, High Times Cups (unverified)

## Outreach Templates (7)
1. Event Email — festivals, cups, parties
2. Event IG DM — when email not available
3. Dispensary Recurring — ongoing partnership pitch
4. Lounge Recurring — consumption lounges
5. Sesh IG DM — small recurring seshes
6. Budtender Event — dispensary budtender nights
7. Big Festival — Rolling Loud, Coachella, etc. (hospitality angle)

## Secrets
- `ANTHROPIC_API_KEY` — Claude for filtering + enrichment + outreach drafts
- `SLACK_BOT_TOKEN` — Wednesday Slack digest to #kp-events (C0434HK1077)
