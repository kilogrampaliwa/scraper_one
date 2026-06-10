# 07 — Dashboard

A small Streamlit app for live demos, reading directly from the Supabase
read-only views (`01_database.md`) via the **anon key** (safe — those views
expose no secrets, raw scraped text, or pipeline configuration).

## Pages

### Pipeline status

- Bar chart of `v_pipeline_status` (counts per `queue.status`:
  `raw`, `in_progress`, `ready`, `analyzed`, `rejected`)
- Useful as the "here's the system actually running" view — re-running the
  GitHub Actions workflow live and refreshing this page shows counts shift

### E-commerce price monitoring

- Table of `v_price_history`, filterable by `category`/`brand`
- For a selected `product_name`, a line chart of `price` over `scraped_at`
  (price-over-time) — works once the workflow has run a few times and
  accumulated history

### Job listings analysis

- Table of `v_job_postings`, filterable by `seniority` and `tech_stack`
  (multiselect — `tech_stack` is an array column)
- Aggregations:
  - Count of postings per `seniority`
  - Most frequent values in `tech_stack` (flatten array, count occurrences)
  - Average `salary_min`/`salary_max` per `seniority` (where not null)

## Implementation notes

- Single `app.py`, `st.tabs()` for the three pages above
- Supabase client: `supabase-py`, initialized with `SUPABASE_URL` and
  `SUPABASE_ANON_KEY` (public, safe for a client-side app)
- Cache query results with `st.cache_data(ttl=...)` (e.g. 60s) to avoid
  hammering Supabase while the dashboard is open during a demo

## Deployment

- Render free web service (free tier), deployed from the same repo, started
  with `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`
- App secrets (`SUPABASE_URL`, `SUPABASE_ANON_KEY`) set as Render environment
  variables — these are public-safe values but kept out of source control for
  hygiene
- Optionally exposed on a custom domain under `/scraper`, with a basic-auth
  gate, via the AWS CloudFront setup in `09_aws_gateway.md` — when deployed
  that way, the start command additionally needs
  `--server.baseUrlPath=scraper` (and the CORS/XSRF flags described there)
