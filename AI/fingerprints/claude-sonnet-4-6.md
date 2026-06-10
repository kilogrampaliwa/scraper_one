# Fingerprint: claude-sonnet-4-6

## What I did

Implemented the full core pipeline described in `AI/00_overview.md` through
`AI/08_compliance.md`, per `AI/start_prompt.md`. Skipped `AI/09_aws_gateway.md`
(stretch goal, not requested).

- `supabase/migrations/0001_init.sql` — full schema (`tasks`, `queue`,
  `price_history`, `job_postings`), RPC functions (`claim_batch`, `mark_ready`,
  `mark_rejected`, `finalize_analysis`, `enqueue_due_tasks`,
  `reset_stale_in_progress`, `purge_old_data`), dashboard views, RLS + anon
  grants.
- `scraper/` package — `base.py` (BaseScraper ABC, robots.txt check,
  per-domain delay, retry/backoff, `build_scraper` factory), `api.py`
  (APIScraper), `html.py` (HTMLScraper), `db.py` (Supabase RPC wrapper),
  `llm.py` (Groq/OpenRouter clients, prompt builders, `validate_items`),
  `orchestrator.py` (`run_once`), `config.py`, `main.py`.
- `seed/demo_tasks.sql` — 3 demo tasks (2 e-commerce, 1 job listings).
- `.github/workflows/run_pipeline.yml` — cron + manual dispatch.
- `dashboard/app.py` — Streamlit dashboard, 3 tabs (pipeline status, price
  monitoring, job listings analysis).
- `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
- `tests/test_scrapers.py`, `tests/test_llm.py` — 20 unit tests, all passing,
  no network required. All modules import cleanly.

## What's left to reach the main goal

- Not yet a git repo — no `git init` / commit done.
- No real Supabase project created or schema applied yet (SQL files exist but
  unrun against live Postgres).
- No real Groq/OpenRouter API key configured/tested — LLM calls untested
  end-to-end against a live API.
- Pipeline never run end-to-end (`python -m scraper.main` against real DB +
  real targets) — only unit-tested with sample data.
- GitHub Actions secrets not configured; workflow never triggered.
- Dashboard not run/deployed (e.g. to Render); not viewed in a browser.
- `AI/09_aws_gateway.md` (custom domain + basic auth via CloudFront) —
  optional stretch goal, do only if explicitly requested.
