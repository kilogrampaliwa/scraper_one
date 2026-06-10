"""BaseScraper ABC: task-driven scraping with robots.txt checks, per-domain
politeness delay, and shared retry/backoff (see AI/02_scrapers.md and
AI/08_compliance.md).
"""

from __future__ import annotations

import abc
import asyncio
import time
import urllib.robotparser
from dataclasses import dataclass, field
from typing import Any, Callable, Literal
from urllib.parse import urlparse

import aiohttp

USER_AGENT = "ScraperDemoBot/1.0 (+https://github.com/; portfolio demo project)"

# How long a robots.txt parse result stays cached, per domain.
_ROBOTS_CACHE_TTL = 3600.0

# Module-level state shared across scrapers within a single orchestrator run.
_robots_cache: dict[str, tuple[urllib.robotparser.RobotFileParser | None, float]] = {}
_domain_last_request: dict[str, float] = {}
_domain_locks: dict[str, asyncio.Lock] = {}


def _domain_lock(domain: str) -> asyncio.Lock:
    lock = _domain_locks.get(domain)
    if lock is None:
        lock = asyncio.Lock()
        _domain_locks[domain] = lock
    return lock


async def _robots_allows(url: str) -> bool:
    """Check robots.txt for `url` against USER_AGENT, caching per domain."""
    parsed = urlparse(url)
    domain = f"{parsed.scheme}://{parsed.netloc}"

    cached = _robots_cache.get(domain)
    now = time.monotonic()
    if cached is None or (now - cached[1]) > _ROBOTS_CACHE_TTL:
        rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{domain}/robots.txt")
        try:
            await asyncio.to_thread(rp.read)
        except Exception:
            # If robots.txt can't be fetched, don't block the demo on it.
            rp = None
        _robots_cache[domain] = (rp, now)
        cached = _robots_cache[domain]

    rp = cached[0]
    if rp is None:
        return True
    return rp.can_fetch(USER_AGENT, url)


async def _enforce_domain_delay(url: str, min_delay: float) -> None:
    """Sleep if needed so consecutive requests to the same domain are spaced
    at least `min_delay` seconds apart."""
    domain = urlparse(url).netloc
    lock = _domain_lock(domain)
    async with lock:
        last = _domain_last_request.get(domain, 0.0)
        now = time.monotonic()
        wait = min_delay - (now - last)
        if wait > 0:
            await asyncio.sleep(wait)
        _domain_last_request[domain] = time.monotonic()


@dataclass
class BaseScraper(abc.ABC):
    """Constructed from one claimed `queue` row joined with its `tasks` row."""

    task_id: int
    queue_id: int
    name: str
    url: str
    params: dict
    parse_config: dict
    max_retries: int
    base_delay: float = 1.0
    min_domain_delay: float = 1.5

    raw_data: list[dict] = field(default_factory=list)
    status: Literal["ready", "blocked", "error"] = "error"
    error: str | None = None

    @classmethod
    def from_rows(cls, queue_row: dict, task_row: dict, config: Any) -> "BaseScraper":
        return cls(
            task_id=task_row["task_id"],
            queue_id=queue_row["id"],
            name=task_row["name"],
            url=queue_row.get("url") or task_row["target_url"],
            params=task_row.get("request_params") or {},
            parse_config=task_row.get("parse_config") or {},
            max_retries=queue_row.get("max_retries", 3),
            base_delay=getattr(config, "base_delay", 1.0),
        )

    # -- abstract interface --------------------------------------------------

    @abc.abstractmethod
    async def fetch(self) -> Any:
        """Perform the HTTP request and return the raw response (parsed JSON
        for API tasks, HTML text for HTML tasks). Implements retry/backoff
        via `_fetch_with_retry`. On failure sets `self.status = "blocked"`
        and `self.error`, and returns None."""

    @abc.abstractmethod
    def validate(self, raw: Any) -> bool:
        """Sanity check the raw response (non-empty, expected shape)."""

    @abc.abstractmethod
    def emit(self, raw: Any) -> list[dict]:
        """Extract structured records from `raw` per `parse_config`. Always
        returns a list (length 1 for a single-item page, length N for a
        listing page)."""

    # -- shared driver ---------------------------------------------------

    async def run(self) -> None:
        """Fetch, validate and emit. Sets `self.status` and `self.raw_data`."""
        raw = await self.fetch()
        if self.status == "blocked":
            return

        if raw is None or not self.validate(raw):
            self.status = "blocked"
            self.error = self.error or "validation failed: unexpected response shape"
            return

        self.raw_data = self.emit(raw)
        self.status = "ready"

    async def _fetch_with_retry(
        self, session: aiohttp.ClientSession, read_response: Callable[[aiohttp.ClientResponse], Any]
    ) -> Any:
        """Shared fetch logic for API/HTML scrapers:

        - robots.txt check (sets status="blocked" and returns None if disallowed)
        - per-domain politeness delay
        - retry with exponential backoff on 429 / 5xx / timeout, up to max_retries

        `read_response` extracts the payload from a successful response
        (e.g. `resp.json()` or `resp.text()`).
        """
        if not await _robots_allows(self.url):
            self.status = "blocked"
            self.error = "robots.txt disallows this path"
            return None

        delay = self.base_delay
        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            await _enforce_domain_delay(self.url, self.min_domain_delay)

            try:
                async with session.get(
                    self.url,
                    params=self.params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        last_error = f"HTTP {resp.status} from {self.url}"
                    else:
                        resp.raise_for_status()
                        return await read_response(resp)
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            if attempt < self.max_retries:
                await asyncio.sleep(delay)
                delay *= 2

        self.status = "blocked"
        self.error = last_error or "fetch failed after retries"
        return None


def build_scraper(queue_row: dict, task_row: dict, config: Any) -> BaseScraper:
    """Factory: select APIScraper or HTMLScraper based on `task_row["type"]`.

    Imports are deferred to avoid a circular import between this module and
    `api`/`html` (both subclass `BaseScraper`).
    """
    from .api import APIScraper
    from .html import HTMLScraper

    scraper_type = task_row["type"]
    if scraper_type == "api":
        return APIScraper.from_rows(queue_row, task_row, config)
    if scraper_type == "html":
        return HTMLScraper.from_rows(queue_row, task_row, config)

    raise ValueError(f"Unknown task type: {scraper_type!r}")
