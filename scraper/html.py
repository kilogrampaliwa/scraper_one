"""HTMLScraper: HTML page scraping driven by `tasks.parse_config` (AI/02_scrapers.md).

`parse_config` shape:
    {
      "item_selector": ".thumbnail",      # CSS selector, one match per record
      "fields": {                         # output field name -> {selector, attr}
        "name":       {"selector": ".title", "attr": "title"},
        "price_text": {"selector": ".price", "attr": "text"}
      },
      "static": {"category_hint": "laptops"}  # optional constants merged into every item
    }
"""

from __future__ import annotations

from typing import Any

import aiohttp
from bs4 import BeautifulSoup

from .base import USER_AGENT, BaseScraper


class HTMLScraper(BaseScraper):
    async def fetch(self) -> Any:
        async with aiohttp.ClientSession(headers={"User-Agent": USER_AGENT}) as session:
            return await self._fetch_with_retry(session, lambda resp: resp.text())

    def validate(self, raw: Any) -> bool:
        if not isinstance(raw, str) or not raw.strip():
            return False

        selector = self.parse_config.get("item_selector")
        if not selector:
            return False

        soup = BeautifulSoup(raw, "html.parser")
        return len(soup.select(selector)) > 0

    def emit(self, raw: Any) -> list[dict]:
        soup = BeautifulSoup(raw, "html.parser")
        selector = self.parse_config["item_selector"]
        fields: dict[str, dict[str, str]] = self.parse_config.get("fields", {})
        static: dict[str, Any] = self.parse_config.get("static", {})

        results = []
        for element in soup.select(selector):
            record: dict[str, Any] = {}
            for out_field, spec in fields.items():
                target = element.select_one(spec["selector"])
                attr = spec.get("attr", "text")

                if target is None:
                    record[out_field] = None
                elif attr == "text":
                    record[out_field] = target.get_text(strip=True)
                else:
                    record[out_field] = target.get(attr)

            record.update(static)
            results.append(record)

        return results
