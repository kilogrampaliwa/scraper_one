"""APIScraper: JSON API scraping driven by `tasks.parse_config` (AI/02_scrapers.md).

`parse_config` shape:
    {
      "root": "data.items",            # optional dot-path to a list (or single object)
      "fields": {                      # output field name -> dot-path into each item
        "product_name": "title",
        "price": "price.amount"
      },
      "static": {"category_hint": "laptops"}  # optional constants merged into every item
    }
"""

from __future__ import annotations

from typing import Any

import aiohttp

from .base import USER_AGENT, BaseScraper


def _resolve_path(data: Any, path: str | None) -> Any:
    """Resolve a dot-separated path (e.g. "price.amount") into nested dicts.
    Returns None if any segment is missing or `data` isn't a dict at that point."""
    if not path:
        return data

    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


class APIScraper(BaseScraper):
    async def fetch(self) -> Any:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            return await self._fetch_with_retry(session, lambda resp: resp.json())

    def validate(self, raw: Any) -> bool:
        if not isinstance(raw, (dict, list)):
            return False

        root = self.parse_config.get("root")
        if root:
            return _resolve_path(raw, root) is not None

        return True

    def emit(self, raw: Any) -> list[dict]:
        root = self.parse_config.get("root")
        items = _resolve_path(raw, root) if root else raw

        if isinstance(items, dict):
            items = [items]
        if not isinstance(items, list):
            items = []

        fields: dict[str, str] = self.parse_config.get("fields", {})
        static: dict[str, Any] = self.parse_config.get("static", {})

        results = []
        for item in items:
            record: dict[str, Any] = {}
            for out_field, path in fields.items():
                record[out_field] = _resolve_path(item, path)
            record.update(static)
            results.append(record)

        return results
