# KP Events Calendar

Internal King Palm event tracking tool with automated scraping and Slack updates.

## Project Structure
- `index.html`, `app.js`, `styles.css` — Single-page frontend (GitHub Pages, zero build)
- `data/events.json` — Source of truth for all events
- `scripts/` — Python scraping/filtering/enrichment pipeline
- `.github/workflows/` — GitHub Actions for deploy + weekly scrape

## Event Categories
- `business` — Trade shows (TPE, CHAMPS, Hall of Flowers, NACS, MJBizCon)
- `end_user` — Consumer festivals (reggae fests, 420 events, cannabis cups)

## Urgency Colors
- Green: 45+ days out
- Yellow: 15-45 days
- Red: <14 days
- Gray: past

## Key Decisions
- No build step — CDN for FullCalendar + Leaflet, vanilla JS
- Events filtered by Claude (21+, cannabis/smoke/reggae, mid-to-large, no family events)
- Wednesday 10am PT Slack digest to #kp-events (C0434HK1077)
- 80% US focus, 20% international emerging cannabis markets

## Secrets (GitHub repo settings)
- `ANTHROPIC_API_KEY` — Claude for filtering + enrichment
- `SLACK_BOT_TOKEN` — Weekly Slack digest

## Managing Events
Events are managed via Claude Code terminal. Edit `data/events.json` directly.
