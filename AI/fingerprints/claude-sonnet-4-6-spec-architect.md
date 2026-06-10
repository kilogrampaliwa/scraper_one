# Fingerprint: claude-sonnet-4-6 (spec / architecture design)

## What I did

Designed the full `AI/` prompt set for the cloud/API variant of the
local-first scraper (`promt_form_chat.txt`), as a portfolio/interview
project. No implementation code written.

- `00_overview.md`–`08_compliance.md`: cloud architecture (Supabase Postgres
  queue + RPCs, Groq/OpenRouter LLM extraction, GitHub Actions cron
  orchestrator, Streamlit dashboard), as a generic task-driven framework
  demoed via two packs — e-commerce price monitoring and job listings
  analysis, sharing one pipeline.
- Folded `risk.txt`'s legal/GDPR analysis into `08_compliance.md` as concrete
  safeguards: robots.txt checks, rate limiting, data minimization (clearing
  `raw_data` for job postings), `purge_old_data` retention.
- Reviewed all files for consistency (removed stray Render mention, fixed
  `purge_old_data` FK-ordering, generalized `claim_batch`).
- Wrote `start_prompt.md` (implementation kickoff prompt, deliberately kept
  outside the numeric sequence).
- Added `09_aws_gateway.md`: Route 53 + ACM + CloudFront + S3 + CloudFront
  Function design to expose the dashboard at `moja_domena/scraper` behind
  basic auth, with the domain root reserved as a future portfolio
  placeholder. Updated `05_deployment.md`/`07_dashboard.md` to host the
  dashboard on Render (not Streamlit Community Cloud) so
  `--server.baseUrlPath` can be set.

## What's left to reach the main goal

Implementation itself was completed in a separate session — see
`claude-sonnet-4-6.md` for what was built. Outstanding items from that
fingerprint still apply:

- `git init` + first commit (repo not yet initialized)
- Create a real Supabase project, apply `supabase/migrations/0001_init.sql`,
  run `seed/demo_tasks.sql`
- Configure a real Groq (or OpenRouter) API key; run the pipeline end-to-end
  against live targets (only unit-tested so far)
- Add GitHub Actions secrets and trigger `run_pipeline.yml`
- Deploy `dashboard/app.py` to Render and view it in a browser
- `09_aws_gateway.md` (custom domain + basic auth via CloudFront) — optional
  stretch goal, not started
