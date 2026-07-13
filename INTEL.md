# Internship intel on the same backend

Internship discovery is mounted on this FastAPI app under `/api/v1/*`.
You do **not** need a second Render service.

## After deploy

```bash
# seed companies (once)
curl -X POST https://YOUR-RENDER-URL/api/v1/companies/seed

# crawl + filter + notify
curl -X POST https://YOUR-RENDER-URL/api/v1/scheduler/tick \
  -H "X-Scheduler-Secret: $SCHEDULER_SECRET"

# today's links
curl https://YOUR-RENDER-URL/api/v1/jobs/today
```

## New Render env vars

| Variable | Required? | Purpose |
|----------|-----------|---------|
| `SCHEDULER_SECRET` | Recommended | Header for `/api/v1/scheduler/tick` |
| `TELEGRAM_BOT_TOKEN` | Optional | Telegram digests |
| `TELEGRAM_CHAT_ID` | Optional | Telegram chat |
| `DISCORD_WEBHOOK_URL` | Optional | Discord digests |
| `SLACK_WEBHOOK_URL` | Optional | Slack digests |

**Reuse as-is:** `MONGO_URI`, `MONGO_DB`, `PORT`, `FRONTEND_ORIGIN`, and all outreach vars.

Also add `httpx` via `requirements.txt` (already listed) — Render will install on next deploy.
