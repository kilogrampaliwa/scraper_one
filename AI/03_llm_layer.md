# 03 — LLM Layer

Implement the structured-extraction layer that turns `raw_data` (from
`02_scrapers.md`) into `clean_data` matching a task's `llm_schema`
(`01_database.md`).

## Provider: Groq (default)

- OpenAI-compatible endpoint: `https://api.groq.com/openai/v1/chat/completions`
- Model: a small/fast Llama 3.x model (e.g. `llama-3.1-8b-instant`) — free
  tier, low latency, good enough for normalization tasks
- Use `response_format={"type": "json_object"}` to force valid JSON output

## Processing loop (per `ready` queue row)

For each row claimed with `status = 'ready'`:

1. Build the **system prompt** from `task.llm_schema`: a textual description
   of the target JSON shape — "Return a JSON object with key `items`: an
   array where each element has these fields: ..." (one line per schema
   field with its type/description)
2. Build the **user prompt**: the row's `raw_data` (a JSON array, possibly
   length 1) serialized as JSON, with an instruction to normalize each
   element into the target schema, preserving array order/length
3. Call the Groq chat completion endpoint
4. Parse the response JSON, extract the `items` array
5. Validate:
   - `len(items) == len(raw_data)`
   - each item has all required keys from `llm_schema`
   - numeric fields parse as numbers, boolean fields are actual booleans
6. On success: call `db.finalize_analysis(queue_id, items)`
7. On any failure (HTTP error, invalid JSON, validation failure): call
   `db.mark_rejected(queue_id, error_message)`

## Rate limiting / availability

Groq's free tier enforces a requests-per-minute limit.

- Before each call, throttle to a configured `requests_per_minute` (simple
  sleep-based pacing is sufficient)
- On HTTP 429: respect `Retry-After` if present, otherwise reuse the same
  exponential backoff helper as `02_scrapers.md` (`base_delay`, doubling, up
  to `max_retries`)
- If retries are exhausted, call `mark_rejected` — the row reverts to `raw`
  (if `retry_count < max_retries`) and is retried on the next orchestrator run

## Schema-driven prompt construction

`task.llm_schema` is a flat dict mapping output field name → human-readable
type/description, used directly to build the system prompt. Example for the
e-commerce demo:

```json
{
  "product_name": "string, normalized product name without marketing fluff",
  "brand": "string, manufacturer/brand name, or null if unknown",
  "category": "string, one of: electronics, home, clothing, other",
  "price": "number, numeric price value only (no currency symbol)",
  "currency": "string, ISO 4217 currency code, e.g. PLN, EUR, USD",
  "in_stock": "boolean"
}
```

Example for the job-postings demo:

```json
{
  "job_title": "string, normalized job title",
  "company": "string, company name",
  "seniority": "string, one of: junior, mid, senior, lead, unknown",
  "tech_stack": "array of strings, normalized technology/tool names",
  "salary_min": "number or null",
  "salary_max": "number or null",
  "currency": "string, ISO 4217 currency code, or null if unspecified",
  "location": "string",
  "remote": "boolean"
}
```

## Alternative provider: OpenRouter

Same OpenAI-compatible chat-completions interface — swap base URL, model name,
and API key. Implemented behind a common interface so the provider is a config
choice, not a code change.

## Module: `llm.py`

- `class LLMClient(ABC)`: `async def extract(raw_data: list[dict], schema:
  dict) -> list[dict]`
- `class GroqClient(LLMClient)` — default
- `class OpenRouterClient(LLMClient)` — alternative
- `build_llm_client(config) -> LLMClient` — factory based on
  `config.llm_provider` (`"groq"` | `"openrouter"`)
