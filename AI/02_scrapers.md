# 02 — Scrapers

Implement the scraping layer, driven entirely by `tasks` rows (see
`01_database.md`) — no scraper subclass is tied to a specific website.

## BaseScraper (ABC)

Constructed from one claimed `queue` row joined with its `tasks` row.

Attributes:
- `task_id: int`, `queue_id: int`, `name: str` (from `tasks.name`)
- `url: str` (`queue.url`, falls back to `tasks.target_url`)
- `params: dict` (`tasks.request_params`)
- `parse_config: dict` (`tasks.parse_config`)
- `max_retries: int` (`queue.max_retries`)
- `base_delay: float` (orchestrator config, e.g. 1.0s)
- `raw_data: list[dict]` — populated by `emit()`
- `status: Literal["ready", "blocked", "error"]`

Abstract methods:
- `async fetch() -> Any` — performs the HTTP request, returns raw response
  (parsed JSON for API, HTML text for HTML). Implements retry/backoff (below).
- `validate(raw: Any) -> bool` — sanity check on the raw response (non-empty,
  expected top-level keys/selectors present)
- `emit(raw: Any) -> list[dict]` — extracts structured records from `raw`
  according to `parse_config`. Always returns a list: length 1 for a
  single-item page, length N for a listing page with N items.

## Pre-fetch checks (see `08_compliance.md`)

Before issuing any request, `BaseScraper.fetch()`:

- Checks the target domain's `robots.txt` (via `urllib.robotparser`, cached
  per domain with a TTL) for the request path and a generic user-agent. If
  disallowed, sets `self.status = "blocked"` and returns immediately —
  the orchestrator calls `mark_rejected` with `error = "robots.txt
  disallows this path"`
- Enforces a minimum per-domain delay between requests (e.g. 1-2s),
  independent of the retry/backoff below — basic politeness even when
  responses are successful

## Retry / backoff

Shared logic in `BaseScraper.fetch()` (or a helper used by both subclasses):

- On HTTP 429 or 5xx or timeout: wait `base_delay` seconds, retry, doubling
  the delay each attempt, up to `max_retries`
- After `max_retries` exhausted: set `self.status = "blocked"` and return
  without raising — the orchestrator checks `status` and calls
  `mark_rejected` with the error message

## APIScraper(BaseScraper)

- `fetch()`: `aiohttp` GET `self.url` with `self.params`, expects a JSON body
- `validate(raw)`: `raw` is a dict/list and contains the top-level key(s)
  declared in `parse_config` (e.g. `"root": "data.items"`)
- `emit(raw)`: `parse_config` maps output field names to dot-paths into `raw`
  (e.g. `{"product_name": "title", "price": "price.amount"}`); resolves the
  `root` path to a list of items (or wraps a single object in a list), then
  applies the field map to each item

## HTMLScraper(BaseScraper)

- `fetch()`: `aiohttp` GET `self.url` with `self.params`, returns response
  text (HTML)
- `validate(raw)`: `BeautifulSoup` parses successfully and the selector
  declared as `parse_config["item_selector"]` matches at least one element
- `emit(raw)`:
  - Selects all elements matching `parse_config["item_selector"]`
    (e.g. one element per product card / job listing)
  - For each element, applies `parse_config["fields"]` — a map of output field
    name → `{"selector": "...", "attr": "text" | "<attribute name>"}`
  - If `parse_config["static"]` is present (a flat dict of field name →
    constant value), merges those constants into every emitted item — e.g. a
    `category_hint` derived from the task's URL/category
  - Returns one dict per matched element

## Scraper factory

A small factory function `build_scraper(queue_row, task_row, config) ->
BaseScraper` selects `APIScraper` or `HTMLScraper` based on `task_row.type`.
Used by the orchestrator so it never branches on scraper type directly.

## Output

After a successful run, `scraper.raw_data` is a `list[dict]` ready to be
passed to `db.mark_ready(queue_id, raw_data)` (stored as a JSON array even for
a single item, for consistency with `finalize_analysis` in `01_database.md`).
