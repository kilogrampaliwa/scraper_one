# Implementation Kickoff Prompt

Paste the prompt below into a new chat/agent session to start implementation.

---

Implement the cloud-based, task-driven web scraping + LLM enrichment pipeline
specified in `AI/00_overview.md` through `AI/08_compliance.md`. Read all of
those files first, in numeric order — they are the single source of truth for
architecture, database schema, module responsibilities, and constraints. Do
not invent additional scope beyond what they describe.

`AI/09_aws_gateway.md` (custom domain + basic auth via AWS) is a stretch goal,
not part of the core deliverables below — only pick it up if explicitly asked.

## Deliverables

1. `supabase/migrations/0001_init.sql` — schema, RPC functions, views per
   `01_database.md`
2. Python package `scraper/`:
   - `base.py` — `BaseScraper` ABC (`02_scrapers.md`)
   - `api.py` — `APIScraper`
   - `html.py` — `HTMLScraper`
   - `db.py` — Supabase client wrapper calling the RPC functions from
     `01_database.md`
   - `llm.py` — `LLMClient` / `GroqClient` / `OpenRouterClient`
     (`03_llm_layer.md`)
   - `orchestrator.py` — `run_once()` (`04_orchestrator.md`)
   - `config.py` — env-var driven config (`04_orchestrator.md`)
   - `main.py` — entry point
3. `seed/demo_tasks.sql` — the `INSERT` statements from `06_demo_tasks.md`
4. `.github/workflows/run_pipeline.yml` — scheduled workflow per
   `05_deployment.md`
5. `dashboard/app.py` — Streamlit app per `07_dashboard.md`
6. `requirements.txt`, `.env.example`, `README.md` (setup steps from
   `05_deployment.md`'s checklist)

## Suggested order

`01` (schema) → `02` (scrapers) → `03` (LLM layer) → `04` (orchestrator) →
seed demo tasks (`06`) → run end-to-end against the demo tasks → `05`
(deployment workflow) → `07` (dashboard). Apply the `08_compliance.md`
constraints (robots.txt check, rate limiting, raw_data clearing for job
postings, purge job) as part of `02`/`04`, not as an afterthought.

## Working agreements

- Code and code comments in English; all conversation in this session in
  Polish
- After each module, do a quick sanity check (unit test for parsing/prompt
  logic, or a dry run) before moving on
- If anything in the `AI/*.md` specs is ambiguous, underspecified, or
  conflicts between files, ask before proceeding rather than guessing
- Keep secrets out of source control (`.env`, gitignored); `.env.example`
  lists required variables
