"""Single-pass batch worker (see AI/04_orchestrator.md).

Each invocation: schedules due tasks, recovers stale rows, scrapes a batch of
'raw' rows, runs LLM extraction on a batch of 'ready' rows, purges old data,
and exits with a JSON summary.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import asdict, dataclass

from .base import build_scraper
from .config import Config
from .db import Database
from .llm import build_llm_client


@dataclass
class RunSummary:
    enqueued: int = 0
    reset_stale: int = 0
    scraped_ready: int = 0
    scraped_rejected: int = 0
    analyzed: int = 0
    analysis_rejected: int = 0
    purged: int = 0
    duration_seconds: float = 0.0


async def _run_scraping_phase(db: Database, config: Config, summary: RunSummary) -> None:
    rows = await db.claim_batch(config.batch_size, "raw")
    if not rows:
        return

    tasks_by_id = {}
    for row in rows:
        task_id = row["task_id"]
        if task_id not in tasks_by_id:
            tasks_by_id[task_id] = await db.get_task(task_id)

    semaphore = asyncio.Semaphore(config.max_concurrent_scrapers)

    async def process(row: dict) -> None:
        scraper = build_scraper(row, tasks_by_id[row["task_id"]], config)
        async with semaphore:
            await scraper.run()

        if scraper.status == "ready":
            await db.mark_ready(scraper.queue_id, scraper.raw_data)
            summary.scraped_ready += 1
        else:
            await db.mark_rejected(scraper.queue_id, scraper.error or "scraping failed")
            summary.scraped_rejected += 1

    await asyncio.gather(*(process(row) for row in rows))


async def _run_llm_phase(db: Database, config: Config, summary: RunSummary) -> None:
    rows = await db.claim_batch(config.batch_size, "ready")
    if not rows:
        return

    tasks_by_id = {}
    for row in rows:
        task_id = row["task_id"]
        if task_id not in tasks_by_id:
            tasks_by_id[task_id] = await db.get_task(task_id)

    llm_client = build_llm_client(config)

    for row in rows:
        task_row = tasks_by_id[row["task_id"]]
        try:
            items = await llm_client.extract(row["raw_data"], task_row["llm_schema"])
            await db.finalize_analysis(row["id"], items)
            summary.analyzed += 1
        except Exception as exc:
            await db.mark_rejected(row["id"], str(exc))
            summary.analysis_rejected += 1


async def run_once(config: Config) -> RunSummary:
    start = time.monotonic()
    db = Database(config.supabase_url, config.supabase_service_role_key)
    summary = RunSummary()

    summary.enqueued = await db.enqueue_due_tasks()
    summary.reset_stale = await db.reset_stale_in_progress(config.stale_in_progress_minutes)

    await _run_scraping_phase(db, config, summary)
    await _run_llm_phase(db, config, summary)

    summary.purged = await db.purge_old_data(config.purge_after_days)
    summary.duration_seconds = round(time.monotonic() - start, 2)

    return summary


def main() -> None:
    config = Config.from_env()
    summary = asyncio.run(run_once(config))
    print(json.dumps(asdict(summary), indent=2))


if __name__ == "__main__":
    main()
