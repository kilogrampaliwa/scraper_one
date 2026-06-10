# 01 — Database (Supabase / Postgres)

Define the Supabase Postgres schema and RPC functions backing the pipeline,
replacing the SQLite `queue` table from the local design (see `00_overview.md`).

## Tables

### `tasks`

Defines scraping targets. Adding a row = adding a new scraping target, no code
change required.

- `task_id` bigserial PK
- `name` text, unique
- `type` text, check in (`'api'`, `'html'`)
- `target_url` text
- `request_params` jsonb, default `'{}'`
- `parse_config` jsonb — CSS selectors / JSON paths per field (HTML/API specific)
- `llm_schema` jsonb — target structure for LLM extraction (field name → type/description)
- `output_table` text — `'price_history'` or `'job_postings'`
- `enabled` boolean, default `true`
- `schedule_interval_minutes` int, default `60`
- `created_at` timestamptz, default `now()`

### `queue`

Mirrors the local SQLite `queue`, scoped per task.

- `id` bigserial PK
- `task_id` bigint, FK → `tasks(task_id)`
- `url` text
- `priority` int, default `0`
- `status` text, check in (`'raw'`, `'in_progress'`, `'ready'`, `'analyzed'`, `'rejected'`), default `'raw'`
- `retry_count` int, default `0`
- `max_retries` int, default `3`
- `last_checked` timestamptz
- `raw_data` jsonb
- `clean_data` jsonb
- `error` text
- `created_at` timestamptz, default `now()`
- `updated_at` timestamptz, default `now()`

Index on `(status, priority desc, id)` for efficient claiming.

### `price_history`

- `id` bigserial PK
- `task_id` bigint, FK → `tasks(task_id)`
- `queue_id` bigint, FK → `queue(id)`
- `product_name` text, `brand` text, `category` text
- `price` numeric, `currency` char(3)
- `in_stock` boolean
- `source_url` text
- `scraped_at` timestamptz, default `now()`

### `job_postings`

- `id` bigserial PK
- `task_id` bigint, FK → `tasks(task_id)`
- `queue_id` bigint, FK → `queue(id)`
- `job_title` text, `company` text, `seniority` text
- `tech_stack` text[]
- `salary_min` numeric, `salary_max` numeric, `currency` char(3)
- `location` text, `remote` boolean
- `source_url` text
- `scraped_at` timestamptz, default `now()`

## RPC functions

All functions are `SECURITY DEFINER`, called from the backend worker via the
Supabase service role key (never exposed to a client).

### `claim_batch(p_limit int, p_from_status text default 'raw') returns setof queue`

- Atomically selects up to `p_limit` rows where `status = p_from_status` and
  the associated task is `enabled`, ordered by `priority desc, id asc`
- Uses `FOR UPDATE SKIP LOCKED` so concurrent workers never claim the same row
- Sets `status = 'in_progress'`, `last_checked = now()`, `updated_at = now()`
- Returns the claimed rows; the orchestrator separately reads `tasks` (plain
  `select`, by `task_id`) to get scraping config for each row
- Used with `p_from_status = 'raw'` for the scraping phase and
  `p_from_status = 'ready'` for the LLM phase (see `04_orchestrator.md`)

### `mark_ready(p_id bigint, p_raw_data jsonb)`

- Sets `raw_data = p_raw_data`, `status = 'ready'`, `last_checked = now()`,
  `updated_at = now()`
- Called by the scraper layer after a successful fetch + validate

### `mark_rejected(p_id bigint, p_error text)`

- Increments `retry_count`
- If `retry_count >= max_retries`: `status = 'rejected'`, `error = p_error`
- Else: `status = 'raw'` (picked up again on the next run), `error = p_error`

### `finalize_analysis(p_id bigint, p_clean_data jsonb)`

- Looks up `task_id` and the task's `output_table` for queue row `p_id`
- Sets `queue.clean_data = p_clean_data`, `status = 'analyzed'`,
  `updated_at = now()`
- `p_clean_data` is either a single JSON object or a JSON array of objects (a
  listing page yields multiple items). For each object, inserts a row into
  `output_table` (`price_history` or `job_postings`) using `EXECUTE format(...)`
  with values pulled via jsonb operators
- `output_table` MUST be checked against an allow-list
  (`'price_history'`, `'job_postings'`) before being used in dynamic SQL
- If `output_table = 'job_postings'`, also sets `queue.raw_data = NULL` —
  the original scraped text (which may contain personal data such as
  recruiter names/emails) is discarded once the normalized record is stored
  (see `08_compliance.md`)

### `purge_old_data(p_days int default 90) returns int`

- Deletes rows from `price_history` and `job_postings` where `scraped_at <
  now() - p_days * interval '1 day'`
- Deletes `queue` rows with `status in ('analyzed', 'rejected')` and
  `updated_at < now() - p_days * interval '1 day'` — run *after* the deletes
  above (or via `ON DELETE CASCADE` on `price_history.queue_id` /
  `job_postings.queue_id`) so the FK from those tables to `queue` is never
  violated
- Returns the total number of rows deleted
- Called once by the orchestrator at the end of each run (cheap no-op when
  nothing is old enough); keeps the demo dataset small and avoids indefinite
  retention of scraped data

### `enqueue_due_tasks(p_default_max_retries int default 3) returns int`

- For each `enabled` task, checks the most recent `queue` row for that
  `task_id`
- A task is "due" if it has no queue rows at all, or its most recent row's
  `created_at < now() - schedule_interval_minutes * interval '1 minute'`
  AND that row is not currently `'raw'` or `'in_progress'` (avoid piling up
  duplicates while a previous run is still pending)
- For each due task, inserts a new `queue` row: `url = tasks.target_url`,
  `status = 'raw'`, `priority = 0`, `max_retries = p_default_max_retries`
- Returns the number of rows inserted
- Called once by the orchestrator at the start of each run, before
  `reset_stale_in_progress`

### `reset_stale_in_progress(p_minutes int default 10) returns int`

- Selects rows with `status = 'in_progress'` and `updated_at < now() - p_minutes
  * interval '1 minute'`
- For each, reverts to `'raw'` if `raw_data IS NULL` (was mid-scraping), or
  `'ready'` if `raw_data IS NOT NULL` (was mid-LLM-analysis) — avoids
  re-scraping rows that were already fetched
- Returns the number of rows reset
- Called once by the orchestrator at the start of each run, to recover from a
  worker that crashed mid-batch

## Read-only views (for dashboard)

Created with default view semantics (owned by the migration role, so they
read the base tables without going through RLS), then `GRANT SELECT` to the
`anon` role — safe to query with the Supabase anon key from the public
Streamlit dashboard (`07_dashboard.md`).

- `v_pipeline_status` — `select status, count(*) from queue group by status`
- `v_price_history` — `select product_name, brand, category, price, currency,
  in_stock, source_url, scraped_at from price_history`
- `v_job_postings` — `select job_title, company, seniority, tech_stack,
  salary_min, salary_max, currency, location, remote, source_url, scraped_at
  from job_postings`

None of these views expose `raw_data`, internal ids beyond what's listed, or
anything from `tasks` (which could reveal scraping configuration).

## Security notes

- Enable RLS on all tables
- No policies for `anon` / `authenticated` roles on base tables — only the
  service role (bypasses RLS) used by the worker
- The three views above are the only `anon`-readable surface, used by the
  read-only dashboard

## Deliverable

A single SQL migration file `supabase/migrations/0001_init.sql` containing all
table definitions, indexes, and functions above.
