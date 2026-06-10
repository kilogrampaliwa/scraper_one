# 04 — Orchestrator

A single-pass batch worker, invoked by an external scheduler (cron-style —
GitHub Actions schedule or Render scheduled job, see `05_deployment.md`).
Unlike the local design's infinite `asyncio` loop, each invocation processes
one batch end-to-end and exits.

## Run sequence (`run_once`)

1. **Connect** to Supabase using the service role key
2. **Phase 0 — Schedule**: call `db.enqueue_due_tasks()` to insert new `queue`
   rows for any task whose `schedule_interval_minutes` has elapsed
3. **Recovery**: call `db.reset_stale_in_progress(10)` to revert rows left
   `in_progress` by a crashed previous run
4. **Phase A — Scraping**:
   - `db.claim_batch(batch_size, "raw")`
   - For each claimed row, look up its `tasks` row, build a scraper via
     `build_scraper()` (`02_scrapers.md`)
   - Run scrapers concurrently, bounded by an `asyncio.Semaphore(
     max_concurrent_scrapers)`
   - On `status == "ready"`: `db.mark_ready(queue_id, raw_data)`
   - On `status == "blocked"` / error: `db.mark_rejected(queue_id, error)`
5. **Phase B — LLM analysis**:
   - `db.claim_batch(batch_size, "ready")`
   - For each claimed row, look up its `tasks.llm_schema`, call
     `llm_client.extract(raw_data, schema)` (`03_llm_layer.md`)
   - On success: `db.finalize_analysis(queue_id, items)`
   - On failure: `db.mark_rejected(queue_id, error)`
6. **Cleanup**: call `db.purge_old_data(90)` to drop stale analyzed/rejected
   rows and old `price_history`/`job_postings` records (`08_compliance.md`)
7. **Summary**: log counts of rows processed per outcome (ready, rejected,
   analyzed, blocked, purged) and exit with status code 0

## Configuration

Loaded from environment variables (see `05_deployment.md` for secrets):

- `BATCH_SIZE` (default `20`)
- `MAX_CONCURRENT_SCRAPERS` (default `5`)
- `BASE_DELAY` (default `1.0` seconds)
- `LLM_PROVIDER` (`groq` | `openrouter`, default `groq`)
- `LLM_REQUESTS_PER_MINUTE` (default per provider's free-tier limit)
- `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
- `GROQ_API_KEY` / `OPENROUTER_API_KEY`

## Module: `orchestrator.py`

- `async def run_once(config: Config) -> RunSummary`
- `RunSummary`: dataclass with counts per outcome, total duration
- `if __name__ == "__main__":` entry point: load config from env,
  `asyncio.run(run_once(config))`, print summary as JSON to stdout (useful for
  capturing in CI logs)
