"""Supabase client wrapper calling the RPC functions defined in
supabase/migrations/0001_init.sql (see AI/01_database.md).

`supabase-py`'s client is synchronous, so each call is run in a worker thread
via `asyncio.to_thread` to keep the orchestrator's async flow non-blocking.
"""

from __future__ import annotations

import asyncio
from typing import Any

from supabase import Client, create_client


class Database:
    def __init__(self, url: str, service_role_key: str) -> None:
        self.client: Client = create_client(url, service_role_key)

    async def enqueue_due_tasks(self, default_max_retries: int = 3) -> int:
        result = await asyncio.to_thread(
            lambda: self.client.rpc(
                "enqueue_due_tasks", {"p_default_max_retries": default_max_retries}
            ).execute()
        )
        return result.data or 0

    async def reset_stale_in_progress(self, minutes: int = 10) -> int:
        result = await asyncio.to_thread(
            lambda: self.client.rpc("reset_stale_in_progress", {"p_minutes": minutes}).execute()
        )
        return result.data or 0

    async def claim_batch(self, limit: int, from_status: str = "raw") -> list[dict[str, Any]]:
        result = await asyncio.to_thread(
            lambda: self.client.rpc(
                "claim_batch", {"p_limit": limit, "p_from_status": from_status}
            ).execute()
        )
        return result.data or []

    async def get_task(self, task_id: int) -> dict[str, Any]:
        result = await asyncio.to_thread(
            lambda: self.client.table("tasks").select("*").eq("task_id", task_id).single().execute()
        )
        return result.data

    async def mark_ready(self, queue_id: int, raw_data: list[dict[str, Any]]) -> None:
        await asyncio.to_thread(
            lambda: self.client.rpc(
                "mark_ready", {"p_id": queue_id, "p_raw_data": raw_data}
            ).execute()
        )

    async def mark_rejected(self, queue_id: int, error: str) -> None:
        await asyncio.to_thread(
            lambda: self.client.rpc(
                "mark_rejected", {"p_id": queue_id, "p_error": error}
            ).execute()
        )

    async def finalize_analysis(self, queue_id: int, clean_data: list[dict[str, Any]] | dict[str, Any]) -> None:
        await asyncio.to_thread(
            lambda: self.client.rpc(
                "finalize_analysis", {"p_id": queue_id, "p_clean_data": clean_data}
            ).execute()
        )

    async def purge_old_data(self, days: int = 90) -> int:
        result = await asyncio.to_thread(
            lambda: self.client.rpc("purge_old_data", {"p_days": days}).execute()
        )
        return result.data or 0
