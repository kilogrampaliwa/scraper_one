# 10 — AWS Gateway & Public Access

This file specifies how the dashboard (`07_dashboard.md`) is exposed on the
user's own domain (`moja_domena`, already registered/managed in AWS), while
keeping the scraping engine, database, and dashboard hosting on free/cheap
tiers (`05_deployment.md`). AWS usage is limited to a thin routing/auth layer.

## Goal

- `moja_domena/scraper` — password-gated dashboard, covering both demo packs
  (e-commerce price monitoring + job listings analysis), reusing the tabs
  defined in `07_dashboard.md`
- `moja_domena/` (root) — placeholder page reserved for a future portfolio
  site (full design out of scope here)
- Engine (Supabase, GitHub Actions, Groq) and dashboard hosting (Render)
  remain unchanged and free, per `05_deployment.md` / `07_dashboard.md`

## Components

### Route 53

- Existing hosted zone for `moja_domena`
- A/ALIAS record (apex, optionally `www`) pointing to the CloudFront
  distribution below

### ACM certificate

- Public certificate for `moja_domena` (and `www.moja_domena` if used),
  requested in `us-east-1` (required for CloudFront), DNS-validated via
  Route 53

### CloudFront distribution

- Single distribution, custom domain `moja_domena`, using the ACM cert above
- **Default behavior (`/*`)**: origin = S3 bucket (placeholder site, see below)
- **Behavior `/scraper*`**: origin = the Render-hosted dashboard (custom HTTP
  origin, HTTPS only)
  - Forward headers required for Streamlit's websocket connection
    (`Origin`, `Upgrade`, `Connection`, cookies)
  - Allowed methods: GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE
  - Cache policy: CachingDisabled (dynamic app, not cacheable)
- CloudFront Function (viewer-request) attached to the `/scraper*` behavior
  for basic auth (below)

### CloudFront Function — basic auth

- CloudFront Functions runtime (JS), viewer-request, free tier covers demo
  traffic (2M invocations/month)
- Reads the `Authorization` request header and compares it against a
  base64-encoded `user:pass` string baked into the function code at deploy
  time (not committed to source control — set via deploy script/secret)
- Missing or mismatched credentials → return `401` with
  `WWW-Authenticate: Basic realm="scraper"` (triggers the browser's native
  login prompt)
- Valid credentials → request passes through unchanged to the `/scraper*`
  origin

### S3 bucket — placeholder site

- Single static `index.html` ("portfolio coming soon", with a link to
  `/scraper`)
- Read-only access via CloudFront Origin Access Control; bucket itself not
  publicly accessible
- Full portfolio design is out of scope for this prompt set — future work

## Backend changes (dashboard on Render)

- Start command updated to serve the app under the `/scraper` base path:

  ```
  streamlit run app.py \
    --server.baseUrlPath=scraper \
    --server.port $PORT \
    --server.address 0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false
  ```

  - `--server.baseUrlPath=scraper` makes Streamlit emit asset/websocket URLs
    prefixed with `/scraper`, matching the CloudFront behavior path
  - `enableCORS` / `enableXsrfProtection` are relaxed because the app is now
    accessed through CloudFront on a different origin than Render's own
    `*.onrender.com` domain
- Supabase calls (`07_dashboard.md`, anon key) happen server-side inside the
  Streamlit process — no browser/Supabase CORS issue is introduced by this
  change
- The Render app remains reachable directly on its `*.onrender.com` URL; that
  URL is **not** covered by the CloudFront basic-auth gate (see Known
  limitations)

## Cost summary

| Component | Cost |
|---|---|
| Route 53 hosted zone | ~$0.50/month (likely already paid) |
| ACM certificate | free |
| CloudFront distribution + traffic | free tier covers demo traffic |
| CloudFront Function | free tier (2M invocations/month) |
| S3 (placeholder page) | pennies |
| Render (dashboard) | free tier, unchanged |

## Setup checklist

1. Request ACM certificate for `moja_domena` in `us-east-1`, validate via
   Route 53 DNS record
2. Create S3 bucket, upload placeholder `index.html`, configure Origin Access
   Control
3. Create CloudFront distribution: default behavior → S3, `/scraper*`
   behavior → Render origin
4. Write and attach the basic-auth CloudFront Function to the `/scraper*`
   behavior; set credentials at deploy time (not in source control)
5. Update the Render start command with `--server.baseUrlPath=scraper`
   (and the CORS/XSRF flags above)
6. Point the Route 53 record(s) at the CloudFront distribution
7. Verify: `moja_domena/` → placeholder page; `moja_domena/scraper` →
   browser login prompt → dashboard with both demo packs

## Known limitations

- Basic auth is a single shared credential, not per-user accounts — adequate
  for gating a portfolio demo, not a real access-control system
- The Render origin's own URL bypasses the CloudFront basic-auth gate; this
  is an accepted risk since it exposes only the read-only dashboard (anon-key
  Supabase views, no secrets)
- This file describes manual AWS console setup; expressing it as IaC
  (CDK/Terraform) is a possible stretch goal, not required for the demo
