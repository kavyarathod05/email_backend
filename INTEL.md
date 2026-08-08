# Internship intel on the same backend

Internship discovery is mounted on this FastAPI app under `/api/v1/*`.
You do **not** need a second Render service.

## After deploy

```bash
# seed companies (once / after seed updates)
curl -X POST https://YOUR-RENDER-URL/api/v1/companies/seed

# crawl + filter + notify
curl -X POST https://YOUR-RENDER-URL/api/v1/scheduler/tick \
  -H "X-Scheduler-Secret: $SCHEDULER_SECRET"

# today's links
curl https://YOUR-RENDER-URL/api/v1/jobs/today

# ranked preference digest
curl https://YOUR-RENDER-URL/api/v1/jobs/digest
```

## Adding a company (custom career page)

For companies **without** Greenhouse/Lever/etc. boards, set:

| Field | Example |
|-------|---------|
| `careers_url` | `https://example.com/careers` |
| `ats_provider` | `json_ld` \| `sitemap` \| `playwright` |

Via API:

```bash
curl -X PATCH https://YOUR-RENDER-URL/api/v1/companies/COMPANY_ID \
  -H "Content-Type: application/json" \
  -d '{"ats_provider":"json_ld","careers_url":"https://example.com/careers"}'
```

Or edit `intel/data/seeds/companies_seed.json` and re-run `/companies/seed`.

**Adapter guide**

- **json_ld** — careers page embeds schema.org `JobPosting` JSON-LD (preferred; cheapest).
- **sitemap** — discovers job URLs from `/sitemap.xml`, then JSON-LD / light heuristics (capped, rate-limited).
- **playwright** — SPA-only; requires `PLAYWRIGHT_SCRAPE_ENABLED=1` and the `playwright` package + browser install. Leave off on Render free tier unless you need it.

Crawl eligibility: **(known ATS + board_token)** OR **(json_ld|sitemap|playwright + careers_url)**.

Heuristic helper (no Google search):

```bash
python -m intel.scripts.backfill_careers_urls --seed          # dry-run
python -m intel.scripts.backfill_careers_urls --seed --apply
```

## Filters (always on for crawl)

Hard gate in detection + filtering: internships, tech roles, India (configurable), no PhD/quant/trading/IIT-only.

Soft **preference ranker** scores `filter_pass` jobs for digests/notifications (`match_score` / `match_reasons`). Optional profile via `INTEL_PREFERENCE_JSON` or `INTEL_PREFERENCE_PATH`.

## New Render env vars

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `SCHEDULER_SECRET` | Recommended | Header for `/api/v1/scheduler/tick` |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram digests |
| `TELEGRAM_CHAT_ID` | Optional | Telegram chat |
| `DISCORD_WEBHOOK_URL` | Optional | Discord digests |
| `SLACK_WEBHOOK_URL` | Optional | Slack digests |
| `PLAYWRIGHT_SCRAPE_ENABLED` | Optional | Enable SPA scraper (`1`/`true`) |
| `INTEL_PREFERENCE_JSON` | Optional | Preference ranker overrides |

**Reuse as-is:** `MONGO_URI`, `MONGO_DB`, `PORT`, `FRONTEND_ORIGIN`, and all outreach vars.

Also add `httpx` via `requirements.txt` (already listed) — Render will install on next deploy.

### Local vs Render

- **Local:** `uvicorn app:app --reload`, seed + crawl as above. Playwright optional: `pip install playwright && playwright install chromium`.
- **Render:** bind `0.0.0.0:$PORT`; filesystem ephemeral — keep company config in Mongo (re-seed after deploy). Prefer `json_ld`/`sitemap` over Playwright on free tier.
