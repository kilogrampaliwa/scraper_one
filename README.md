# Cloud Scraper Pipeline

A task-driven web scraping + LLM enrichment pipeline, built to run entirely on
free/cheap cloud tiers. It demonstrates a generic ETL pattern: scraping
targets are rows in a database table, not hardcoded classes — adding a new
target is a SQL `INSERT`, not a code change.

Two independent demo packs run on the same code:

- **E-commerce price monitoring** — scrapes product listings, normalizes
  price/brand/category via an LLM, and appends to a `price_history` table.
- **Job listings analysis** — scrapes job postings, normalizes
  title/seniority/tech-stack/salary via an LLM, and appends to a
  `job_postings` table.

## Architecture

```
GitHub Actions (cron, every 30 min)
        |
        v
  scraper.orchestrator.run_once()
        |
        |-- enqueue_due_tasks()         -- schedule new work from `tasks`
        |-- reset_stale_in_progress()   -- recover from crashed runs
        |
        |-- Phase A: scrape `raw` queue rows
        |     BaseScraper -> APIScraper / HTMLScraper
        |     -> mark_ready() / mark_rejected()
        |
        |-- Phase B: LLM-normalize `ready` queue rows
        |     LLMClient (Groq / OpenRouter)
        |     -> finalize_analysis() / mark_rejected()
        |
        '-- purge_old_data()            -- drop stale rows (90 days)

Supabase (Postgres)
  tasks, queue, price_history, job_postings
  + RPC functions for the queue lifecycle
  + read-only views (v_pipeline_status, v_price_history, v_job_postings)
        |
        v
Streamlit dashboard (Render) -- reads the views via the anon key
```

Full design rationale lives in [`AI/00_overview.md`](AI/00_overview.md)
through [`AI/08_compliance.md`](AI/08_compliance.md).

## Project layout

```
supabase/migrations/0001_init.sql   Schema, RPC functions, dashboard views
seed/demo_tasks.sql                 Demo task definitions (2 task packs)
scraper/                            Pipeline package
  base.py                           BaseScraper ABC, robots.txt + retry/backoff, factory
  api.py                            APIScraper (JSON APIs)
  html.py                           HTMLScraper (HTML pages, BeautifulSoup)
  db.py                             Supabase client wrapper (RPC calls)
  llm.py                            LLMClient (Groq / OpenRouter)
  config.py                         Env-var driven configuration
  orchestrator.py                   run_once() — single batch pass
  main.py                           Entry point (python -m scraper.main)
dashboard/app.py                    Streamlit demo dashboard
.github/workflows/run_pipeline.yml  Scheduled GitHub Actions workflow
tests/                               Unit tests for parsing/LLM logic
```

## Compliance & data minimization

- `BaseScraper.fetch()` checks `robots.txt` before every request and enforces
  a minimum per-domain delay.
- Failed/blocked requests use exponential backoff and are retried up to
  `queue.max_retries` before being marked `rejected`.
- For job postings, `finalize_analysis()` clears `queue.raw_data` once the
  normalized record is stored — the `llm_schema` for jobs deliberately
  excludes any personal data (no recruiter names/emails).
- `purge_old_data()` deletes analyzed/rejected queue rows and old
  `price_history`/`job_postings` rows after 90 days.

See [`AI/08_compliance.md`](AI/08_compliance.md) for details, and
[`AI/risk.txt`](AI/risk.txt) for the underlying legal-analysis prompt (not a
legal opinion — review before pointing this at a real/commercial site).

## Setup

### 1. Supabase project

1. Create a free project at [supabase.com](https://supabase.com).
2. Apply the schema: paste
   [`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql)
   into the SQL editor (or run it via `supabase db push` if using the CLI).
3. Seed the demo tasks: paste [`seed/demo_tasks.sql`](seed/demo_tasks.sql)
   into the SQL editor and run it once.
4. Note your project's `SUPABASE_URL`, `service_role` key, and `anon` key
   (Project Settings → API).

### 2. Groq API key

Create a free API key at [console.groq.com](https://console.groq.com).
(OpenRouter is supported as an alternative — set `LLM_PROVIDER=openrouter`
and `OPENROUTER_API_KEY` instead.)

### 3. Local run

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
# source .venv/bin/activate      # macOS/Linux

pip install -r requirements.txt
cp .env.example .env            # fill in SUPABASE_URL, keys, etc.

python -m scraper.main
```

`run_once()` prints a JSON summary (rows enqueued/scraped/analyzed/rejected/
purged, and total duration).

### 4. Scheduled pipeline (GitHub Actions)

1. Repo Settings → Secrets and variables → Actions, add:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `GROQ_API_KEY`
   - `OPENROUTER_API_KEY` (optional)
2. The workflow [`run_pipeline.yml`](.github/workflows/run_pipeline.yml) runs
   every 30 minutes and is also manually triggerable from the Actions tab
   (`workflow_dispatch`) — use that for a live demo or to seed initial data.

### 5. Dashboard

Run locally:

```bash
streamlit run dashboard/app.py
```

Requires `SUPABASE_URL` and `SUPABASE_ANON_KEY` (anon key is safe to expose —
it can only read the three `v_*` views).

For deployment, see [`AI/05_deployment.md`](AI/05_deployment.md) (Render free
web service). Putting the dashboard behind a custom domain with basic auth via
AWS CloudFront is described in [`AI/09_aws_gateway.md`](AI/09_aws_gateway.md)
(stretch goal, not required).

## Running tests

```bash
pip install -r requirements.txt
pytest
```

Tests cover parsing/extraction logic (`scraper/api.py`, `scraper/html.py`)
and LLM prompt construction / response validation (`scraper/llm.py`) — no
network access required.

## Configuration reference

All settings are environment variables, see [`.env.example`](.env.example):

| Variable | Default | Description |
|---|---|---|
| `SUPABASE_URL` | — | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | — | Service role key (worker, bypasses RLS) |
| `SUPABASE_ANON_KEY` | — | Anon key (dashboard, read-only views) |
| `LLM_PROVIDER` | `groq` | `groq` or `openrouter` |
| `LLM_REQUESTS_PER_MINUTE` | `30` (groq) / `20` (openrouter) | Rate-limit pacing |
| `GROQ_API_KEY` / `GROQ_MODEL` | — / `llama-3.1-8b-instant` | Groq settings |
| `OPENROUTER_API_KEY` / `OPENROUTER_MODEL` | — / `meta-llama/llama-3.1-8b-instruct:free` | OpenRouter settings |
| `BATCH_SIZE` | `20` | Rows claimed per phase per run |
| `MAX_CONCURRENT_SCRAPERS` | `5` | Concurrent scraper tasks |
| `BASE_DELAY` | `1.0` | Base seconds for retry/backoff |

## Adding a new scraping target

No code change needed — insert a row into `tasks` with:

- `type`: `"api"` or `"html"`
- `target_url`, `request_params`
- `parse_config`: selectors/JSON paths (see [`AI/02_scrapers.md`](AI/02_scrapers.md))
- `llm_schema`: target normalized fields (see [`AI/03_llm_layer.md`](AI/03_llm_layer.md))
- `output_table`: `"price_history"` or `"job_postings"`

The next orchestrator run picks it up via `enqueue_due_tasks()`.
