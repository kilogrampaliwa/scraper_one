"""LLM structured-extraction layer: turns `raw_data` into `clean_data` matching
a task's `llm_schema` (see AI/03_llm_layer.md).

Both providers (Groq, OpenRouter) speak the OpenAI-compatible chat-completions
API, so they share `_ChatCompletionClient` and differ only in base URL,
default model, and default rate limit.
"""

from __future__ import annotations

import abc
import asyncio
import json
import time
from typing import Any

import aiohttp


class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def extract(self, raw_data: list[dict], schema: dict[str, str]) -> list[dict]:
        """Normalize each element of `raw_data` into `schema`, preserving
        order and length. Raises on any failure (HTTP error, invalid JSON,
        validation failure) — the caller is responsible for `mark_rejected`."""


def build_system_prompt(schema: dict[str, str]) -> str:
    lines = [
        "You are a data normalization assistant for a web scraping pipeline.",
        "Return a JSON object with a single key `items`: an array where each "
        "element has exactly these fields:",
        "",
    ]
    for field_name, description in schema.items():
        lines.append(f"- {field_name}: {description}")
    lines += [
        "",
        "The `items` array must have the same length and order as the input "
        "array of raw records. Output only valid JSON — no commentary, no "
        "markdown code fences.",
    ]
    return "\n".join(lines)


def build_user_prompt(raw_data: list[dict]) -> str:
    return (
        "Normalize each element of the following JSON array into the target "
        "schema described in the system prompt, preserving order and length. "
        f"Input array:\n{json.dumps(raw_data, ensure_ascii=False)}"
    )


def _looks_numeric(description: str) -> bool:
    return description.strip().lower().startswith("number")


def _looks_boolean(description: str) -> bool:
    return description.strip().lower().startswith("boolean")


def _looks_array(description: str) -> bool:
    return description.strip().lower().startswith("array")


def _allows_null(description: str) -> bool:
    return "null" in description.lower()


def validate_items(items: Any, raw_data: list[dict], schema: dict[str, str]) -> list[dict]:
    """Validate the LLM's `items` array against `raw_data` length and `schema`
    types. Raises ValueError on any mismatch."""
    if not isinstance(items, list):
        raise ValueError("LLM response 'items' is not a list")

    if len(items) != len(raw_data):
        raise ValueError(f"expected {len(raw_data)} items, got {len(items)}")

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item {index} is not a JSON object")

        for field_name, description in schema.items():
            if field_name not in item:
                raise ValueError(f"item {index} is missing required field '{field_name}'")

            value = item[field_name]

            if value is None:
                if not _allows_null(description):
                    raise ValueError(f"item {index} field '{field_name}' is null but schema doesn't allow null")
                continue

            if _looks_numeric(description) and not isinstance(value, (int, float)):
                raise ValueError(f"item {index} field '{field_name}' should be numeric, got {type(value).__name__}")

            if _looks_boolean(description) and not isinstance(value, bool):
                raise ValueError(f"item {index} field '{field_name}' should be boolean, got {type(value).__name__}")

            if _looks_array(description) and not isinstance(value, list):
                raise ValueError(f"item {index} field '{field_name}' should be an array, got {type(value).__name__}")

    return items


class _RateLimiter:
    """Simple sleep-based pacing to stay under a requests-per-minute limit."""

    def __init__(self, requests_per_minute: int) -> None:
        self._min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0.0
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_call = time.monotonic()


class _ChatCompletionClient(LLMClient):
    """Shared OpenAI-compatible chat-completions implementation."""

    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str,
        requests_per_minute: int,
        base_delay: float = 1.0,
        max_retries: int = 3,
        items_per_request: int = 10,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.base_delay = base_delay
        self.max_retries = max_retries
        self.items_per_request = items_per_request
        self._rate_limiter = _RateLimiter(requests_per_minute)

    async def extract(self, raw_data: list[dict], schema: dict[str, str]) -> list[dict]:
        if not self.api_key:
            raise RuntimeError(f"missing API key for {type(self).__name__}")

        if not raw_data:
            return []

        chunk_size = self.items_per_request
        chunks = [raw_data[i : i + chunk_size] for i in range(0, len(raw_data), chunk_size)]

        results: list[dict] = []
        async with aiohttp.ClientSession() as session:
            for chunk in chunks:
                results.extend(await self._extract_chunk(session, chunk, schema))
        return results

    async def _extract_chunk(
        self, session: aiohttp.ClientSession, raw_chunk: list[dict], schema: dict[str, str]
    ) -> list[dict]:
        """Run one chat-completion request for a chunk of `raw_chunk`,
        retrying on transient errors. Small chunks keep the LLM's JSON
        response within its output token limit (see AI/03_llm_layer.md)."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": build_system_prompt(schema)},
                {"role": "user", "content": build_user_prompt(raw_chunk)},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        delay = self.base_delay
        last_error: str | None = None

        for attempt in range(self.max_retries + 1):
            await self._rate_limiter.wait()

            try:
                async with session.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        wait_seconds = float(retry_after) if retry_after else delay
                        last_error = f"HTTP 429 from {self.base_url}"
                        if attempt < self.max_retries:
                            await asyncio.sleep(wait_seconds)
                            delay *= 2
                        continue

                    if resp.status >= 500:
                        last_error = f"HTTP {resp.status} from {self.base_url}"
                        if attempt < self.max_retries:
                            await asyncio.sleep(delay)
                            delay *= 2
                        continue

                    resp.raise_for_status()
                    body = await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                if attempt < self.max_retries:
                    await asyncio.sleep(delay)
                    delay *= 2
                continue

            content = body["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError as exc:
                raise ValueError(f"LLM did not return valid JSON: {exc}") from exc

            items = parsed.get("items") if isinstance(parsed, dict) else None
            return validate_items(items, raw_chunk, schema)

        raise RuntimeError(last_error or f"{type(self).__name__}: request failed after retries")


class GroqClient(_ChatCompletionClient):
    """Default provider: Groq's free tier, OpenAI-compatible endpoint."""

    BASE_URL = "https://api.groq.com/openai/v1/chat/completions"
    DEFAULT_MODEL = "llama-3.1-8b-instant"

    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        requests_per_minute: int = 30,
        base_delay: float = 1.0,
        max_retries: int = 3,
        items_per_request: int = 10,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=self.BASE_URL,
            requests_per_minute=requests_per_minute,
            base_delay=base_delay,
            max_retries=max_retries,
            items_per_request=items_per_request,
        )


class OpenRouterClient(_ChatCompletionClient):
    """Alternative provider: OpenRouter, same chat-completions interface."""

    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    DEFAULT_MODEL = "meta-llama/llama-3.1-8b-instruct:free"

    def __init__(
        self,
        api_key: str | None,
        model: str | None = None,
        requests_per_minute: int = 20,
        base_delay: float = 1.0,
        max_retries: int = 3,
        items_per_request: int = 10,
    ) -> None:
        super().__init__(
            api_key=api_key,
            model=model or self.DEFAULT_MODEL,
            base_url=self.BASE_URL,
            requests_per_minute=requests_per_minute,
            base_delay=base_delay,
            max_retries=max_retries,
            items_per_request=items_per_request,
        )


def build_llm_client(config: Any) -> LLMClient:
    """Factory based on `config.llm_provider` ("groq" | "openrouter")."""
    if config.llm_provider == "groq":
        return GroqClient(
            api_key=config.groq_api_key,
            model=config.groq_model,
            requests_per_minute=config.llm_requests_per_minute,
            base_delay=config.base_delay,
            max_retries=config.max_retries,
            items_per_request=config.llm_items_per_request,
        )

    if config.llm_provider == "openrouter":
        return OpenRouterClient(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
            requests_per_minute=config.llm_requests_per_minute,
            base_delay=config.base_delay,
            max_retries=config.max_retries,
            items_per_request=config.llm_items_per_request,
        )

    raise ValueError(f"Unknown LLM provider: {config.llm_provider!r}")
