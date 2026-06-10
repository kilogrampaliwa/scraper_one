# 05 — Deployment & Secrets

Goal: $0/month, minimal moving parts, easy to demo live.

## Compute: GitHub Actions scheduled workflow

Run the orchestrator (`04_orchestrator.md`) as a scheduled GitHub Actions
workflow instead of a long-lived process:

`.github/workflows/run_pipeline.yml`:
- Trigger: `schedule` (cron, e.g. every 30 minutes — `*/30 * * * *`) and
  `workflow_dispatch` (manual run button, useful for live demos)
- Steps: checkout → setup Python 3.11 → `pip install -r requirements.txt` →
  `python -m scraper.orchestrator`
- Secrets passed as env vars (see below)
- Job timeout set conservatively (e.g. 5 minutes) — a single batch run should
  finish well within that

GitHub Actions free tier: 2000 min/month for private repos, unlimited for
public repos — far more than needed at a 30-minute cadence (~1440 min/month
worst case at 1 min/run).

### Alternative

Render "Cron Job" service (small paid tier, ~$1/month) or Fly.io scheduled
machines — only relevant if GitHub Actions cron granularity (min. every 5 min)
is insufficient, which it isn't for this project.

## Secrets

Stored as GitHub repository secrets (Settings → Secrets and variables →
Actions), injected as env vars in the workflow:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `GROQ_API_KEY`
- `OPENROUTER_API_KEY` (optional, only if `LLM_PROVIDER=openrouter`)

Never commit these. `.env.example` documents the required variables for local
runs; `.env` is gitignored.

## Database: Supabase free tier

- 500 MB database, 2 GB bandwidth/month — generous for a demo dataset
- **Free projects pause after 1 week with no API activity.** Since the
  scheduled workflow calls the API every 30 minutes, this keeps the project
  active automatically. If the workflow is paused/disabled for a while before
  a demo, manually unpause the project from the Supabase dashboard beforehand
- Schema applied once via `supabase/migrations/0001_init.sql`, run through the
  Supabase CLI (`supabase db push`) or pasted into the SQL editor

## LLM: Groq free tier

- Free tier has per-model requests-per-minute and tokens-per-minute limits
  (check current limits at console.groq.com — they change)
- Keep `BATCH_SIZE` and `LLM_REQUESTS_PER_MINUTE` conservative (e.g.
  batch size 10–20) so a single run stays under the limit
- `OpenRouter` free models are a fallback if Groq's limits are too tight for a
  given demo run

## Dashboard: Render free web service

- Hosts the Streamlit app (`07_dashboard.md`) as a free web service, started
  with `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- Chosen over Streamlit Community Cloud because it allows custom start
  command flags (e.g. `--server.baseUrlPath`), needed for the optional custom
  domain setup in `09_aws_gateway.md`
- **Free web services spin down after ~15 min of inactivity** — cold start
  takes 30-50s. Wake it up (open the URL once) shortly before a live demo

## Cost summary

| Component | Tier | Cost |
|---|---|---|
| Supabase | Free | $0 |
| Groq API | Free | $0 |
| GitHub Actions | Free (public repo) | $0 |
| Render (dashboard) | Free | $0 |
| AWS (Route 53 / CloudFront / S3, optional, `09_aws_gateway.md`) | Mostly free | ~$0.50/mo (existing hosted zone) |

## One-time setup checklist

1. Create Supabase project, apply `0001_init.sql`
2. Insert demo `tasks` rows (see `06_demo_tasks.md`)
3. Create Groq API key
4. Add repo secrets
5. Enable the scheduled workflow (and trigger once manually via
   `workflow_dispatch` to seed initial data before a demo)
