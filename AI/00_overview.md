# Cloud Scraper Pipeline — Overview

This is the cloud/API-based variant of the local-first design in `promt_form_chat.txt`.
Goal: a task-driven scraping + LLM-enrichment pipeline, deployable on free/cheap cloud
tiers, suitable as a portfolio/demo project for a Data/ETL-oriented role.

## Stack

- Language: Python 3.11+, asyncio
- Scraping: aiohttp + BeautifulSoup
- Storage & queue: Supabase (Postgres) — replaces SQLite
- LLM: Groq API (free tier, Llama 3.x) for structured extraction; OpenRouter as
  alternative/fallback
- Orchestration: scheduled worker run (GitHub Actions cron) instead of a
  long-lived asyncio loop — each run processes one batch and exits
- Demo dashboard: Streamlit, reads directly from Supabase

## Layer mapping (local → cloud)

| Local design          | Cloud design                                           |
|------------------------|--------------------------------------------------------|
| SQLite `queue` table   | Supabase Postgres `queue` table + RPC functions         |
| OpenRouter (free tier) | Groq (default), OpenRouter (alternative)                |
| asyncio infinite loop  | scheduled batch run (cron), exits after one pass        |
| BaseScraper subclasses hardcoded | BaseScraper driven by rows in a `tasks` table   |

## Task-driven design

The system is generic: scraping targets are not hardcoded as classes but defined
as rows in a `tasks` table:

- `task_id`, `name`, `type` (`api` / `html`)
- `target_url`, `request_params`
- `parse_config` — CSS selectors / JSON paths describing how to extract raw fields
- `llm_schema` — target JSON schema the LLM layer should produce from raw data
- `enabled`, `schedule_interval_minutes`

Adding a new scraping target = inserting a new `tasks` row, no code change.

## Reference demos (two task packs, same pipeline)

The framework is demonstrated with two independent task packs — same code,
different `tasks` rows and `llm_schema`s, proving the "no code change needed to
add a target" claim.

### A. E-commerce price monitoring

- 2-3 tasks scraping product listing pages (different stores or categories)
- Raw fields per product: name, price text, currency, availability text — often
  inconsistent in format/units across sources
- LLM layer normalizes raw fields into: `product_name`, `brand`, `category`,
  `price` (numeric), `currency` (ISO code), `in_stock` (bool)
- Clean data is appended to a `price_history` table, enabling a simple
  price-over-time view per product

### B. Job listings analysis

- 2-3 tasks scraping job board listing/detail pages
- Raw fields per posting: job title, company, location text, salary text,
  description/requirements text — free-form, varies widely per source
- LLM layer normalizes raw fields into: `job_title`, `company`, `seniority`,
  `tech_stack` (array), `salary_min`, `salary_max`, `currency`, `location`,
  `remote` (bool)
- Clean data is appended to a `job_postings` table, enabling filtering/aggregation
  by tech stack, seniority, and salary range

## Prompt / module structure

- `00_overview.md` — this file
- `01_database.md` — Supabase schema: `tasks`, `queue`, `price_history`,
  `job_postings` tables + RPC functions for the queue lifecycle (claim,
  mark ready/rejected, finalize analysis, scheduling, recovery, purge) and
  read-only dashboard views
- `02_scrapers.md` — BaseScraper ABC, APIScraper, HTMLScraper, task-driven config,
  retry/backoff
- `03_llm_layer.md` — Groq-based structured extraction layer
- `04_orchestrator.md` — scheduled worker: batch processing, stale-row recovery
- `05_deployment.md` — deployment & secrets (GitHub Actions / Render), free-tier
  limits and cost notes
- `06_demo_tasks.md` — concrete task definitions for both demo packs
  (e-commerce + job listings)
- `07_dashboard.md` — Streamlit demo dashboard covering both demo packs
- `08_compliance.md` — robots.txt / rate-limiting / GDPR data-minimization
  safeguards (see `risk.txt` for the underlying legal analysis prompt)
- `09_aws_gateway.md` — exposing the dashboard on the user's own domain via
  Route 53 / CloudFront / S3, with basic-auth gating, while keeping the
  engine and dashboard hosting on free tiers

`start_prompt.md` (no number, outside this sequence) — kickoff prompt for the
chat/agent session that implements this project; it instructs reading
`00`-`09` first.

## Out of scope

- Auth / multi-tenancy
- Per-domain rate limiting beyond simple exponential backoff
- Proxy rotation / anti-bot evasion
