"""Environment-driven configuration for the orchestrator (see AI/04_orchestrator.md)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Default Groq/OpenRouter free-tier requests-per-minute caps. These are
# conservative starting points; tune via LLM_REQUESTS_PER_MINUTE if the
# provider's current limits differ (see AI/05_deployment.md).
_DEFAULT_RPM = {
    "groq": 30,
    "openrouter": 20,
}


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value else default


@dataclass
class Config:
    supabase_url: str
    supabase_service_role_key: str

    batch_size: int = 20
    max_concurrent_scrapers: int = 5
    base_delay: float = 1.0
    max_retries: int = 3

    llm_provider: str = "groq"
    llm_requests_per_minute: int = 30
    llm_items_per_request: int = 10

    groq_api_key: str | None = None
    groq_model: str | None = None
    openrouter_api_key: str | None = None
    openrouter_model: str | None = None

    purge_after_days: int = 90
    stale_in_progress_minutes: int = 10

    @classmethod
    def from_env(cls) -> "Config":
        provider = os.environ.get("LLM_PROVIDER", "groq").lower()
        default_rpm = _DEFAULT_RPM.get(provider, 20)

        return cls(
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_service_role_key=os.environ["SUPABASE_SERVICE_ROLE_KEY"],
            batch_size=_env_int("BATCH_SIZE", 20),
            max_concurrent_scrapers=_env_int("MAX_CONCURRENT_SCRAPERS", 5),
            base_delay=_env_float("BASE_DELAY", 1.0),
            llm_provider=provider,
            llm_requests_per_minute=_env_int("LLM_REQUESTS_PER_MINUTE", default_rpm),
            llm_items_per_request=_env_int("LLM_ITEMS_PER_REQUEST", 10),
            groq_api_key=os.environ.get("GROQ_API_KEY"),
            groq_model=os.environ.get("GROQ_MODEL"),
            openrouter_api_key=os.environ.get("OPENROUTER_API_KEY"),
            openrouter_model=os.environ.get("OPENROUTER_MODEL"),
        )
