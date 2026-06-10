# 08 — Compliance & Risk Mitigation

This file translates the legal/compliance questions in `risk.txt` (EU law,
GDPR, database rights, ToS/robots.txt) into concrete technical safeguards
applied across the pipeline. It is a design constraint document, not a legal
opinion — for a real commercial deployment, run `risk.txt` through proper
legal review per target site.

## robots.txt compliance

- `BaseScraper.fetch()` (`02_scrapers.md`) checks the target domain's
  `robots.txt` via `urllib.robotparser` (cached per domain, short TTL) before
  every request
- If the path is disallowed for a generic user-agent, the scraper sets
  `status = "blocked"` and the row is rejected — the task is never silently
  retried against a disallowed path

## Rate limiting / politeness

- Per-request exponential backoff on errors (`02_scrapers.md`)
- A minimum per-domain delay between requests (1-2s), independent of errors
- `tasks.schedule_interval_minutes` keeps total request volume low (e.g. one
  pass every 30-60 min, not continuous polling) — both lower legal exposure
  and a more realistic "monitoring" cadence

## Data minimization (GDPR)

- The `llm_schema` for job postings (`03_llm_layer.md`) deliberately excludes
  any field that could capture personal data about an individual (no
  recruiter names, emails, phone numbers, applicant info) — only
  job/role-level facts (title, seniority, tech stack, salary range, location,
  remote)
- After a job-posting row is analyzed, `finalize_analysis`
  (`01_database.md`) clears `queue.raw_data` for that row — the original
  scraped text (which may contain personal data embedded in a job
  description) is not retained once the normalized record exists
- `purge_old_data` (`01_database.md`) deletes `price_history` /
  `job_postings` rows and their source `queue` rows after `p_days` (default
  90), avoiding indefinite retention

## Storage scope (copyright / EU database right)

- Only normalized, factual data points are stored long-term (price, product
  name, job title, tech stack, etc.) — never full page HTML, images, or
  substantial verbatim extracts of the source content
- Combined with `raw_data` clearing above, this limits how much of any single
  source's content/database is reproduced or retained

## Demo data sources

`06_demo_tasks.md` targets `webscraper.io/test-sites` and
`realpython.github.io/fake-jobs` — both are publicly provided specifically for
scraping practice, with permissive `robots.txt` and no real personal data or
proprietary catalog content. This keeps the portfolio demo itself low-risk
regardless of the broader analysis in `risk.txt`.

## Before pointing this at a real/commercial site

1. Review that site's Terms of Service and `robots.txt`
2. Confirm the data being collected and retained doesn't include personal
   data beyond what's justified (GDPR Art. 5 data minimization)
3. Re-run the `risk.txt` assessment for that specific target
4. Consider whether commercial use of the resulting dataset requires a
   license from the source
