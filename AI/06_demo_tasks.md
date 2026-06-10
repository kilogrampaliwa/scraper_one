# 06 — Demo Tasks

Concrete `tasks` rows seeding both demo packs (`00_overview.md`). Targets are
public scraping-practice sites (low legal risk, see `08_compliance.md`,
stable HTML structure for a reliable live demo). **Verify selectors against
the live site's current HTML before relying on them** — practice sites
occasionally change markup.

## Pack A — E-commerce price monitoring

Two tasks against `webscraper.io/test-sites/e-commerce/allinone`, different
categories, same `output_table`.

```sql
insert into tasks (name, type, target_url, request_params, parse_config, llm_schema, output_table, schedule_interval_minutes)
values (
  'ecommerce_laptops',
  'html',
  'https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops',
  '{}',
  '{
    "item_selector": ".thumbnail",
    "static": {"category_hint": "laptops"},
    "fields": {
      "name":        {"selector": ".title",       "attr": "title"},
      "price_text":  {"selector": ".price",       "attr": "text"},
      "description": {"selector": ".description", "attr": "text"}
    }
  }',
  '{
    "product_name": "string, normalized product name",
    "brand": "string, manufacturer/brand guessed from product_name, or null if unknown",
    "category": "string, one of: electronics, home, clothing, other",
    "price": "number, numeric price value only (no currency symbol)",
    "currency": "string, ISO 4217 currency code, e.g. USD",
    "in_stock": "boolean, true unless description clearly indicates otherwise"
  }',
  'price_history',
  60
);

insert into tasks (name, type, target_url, request_params, parse_config, llm_schema, output_table, schedule_interval_minutes)
values (
  'ecommerce_phones',
  'html',
  'https://webscraper.io/test-sites/e-commerce/allinone/phones/touch',
  '{}',
  '{
    "item_selector": ".thumbnail",
    "static": {"category_hint": "phones"},
    "fields": {
      "name":        {"selector": ".title",       "attr": "title"},
      "price_text":  {"selector": ".price",       "attr": "text"},
      "description": {"selector": ".description", "attr": "text"}
    }
  }',
  '{
    "product_name": "string, normalized product name",
    "brand": "string, manufacturer/brand guessed from product_name, or null if unknown",
    "category": "string, one of: electronics, home, clothing, other",
    "price": "number, numeric price value only (no currency symbol)",
    "currency": "string, ISO 4217 currency code, e.g. USD",
    "in_stock": "boolean, true unless description clearly indicates otherwise"
  }',
  'price_history',
  60
);
```

`category_hint` (from `parse_config.static`) gives the LLM a strong signal for
the `category` field without hardcoding it in the schema.

## Pack B — Job listings analysis

One task against `realpython.github.io/fake-jobs` (a single page lists all
postings, no pagination needed for a demo).

```sql
insert into tasks (name, type, target_url, request_params, parse_config, llm_schema, output_table, schedule_interval_minutes)
values (
  'fake_jobs_listing',
  'html',
  'https://realpython.github.io/fake-jobs/',
  '{}',
  '{
    "item_selector": ".card-content",
    "fields": {
      "title":   {"selector": ".title.is-5",            "attr": "text"},
      "company": {"selector": ".subtitle.is-6.company", "attr": "text"},
      "location":{"selector": ".location",              "attr": "text"}
    }
  }',
  '{
    "job_title": "string, normalized job title",
    "company": "string, company name",
    "seniority": "string, one of: junior, mid, senior, lead, unknown - infer from job_title",
    "tech_stack": "array of strings, technology/tool names mentioned in job_title, empty array if none",
    "salary_min": "number or null - not present in source data, always null here",
    "salary_max": "number or null - not present in source data, always null here",
    "currency": "string ISO 4217 or null - not present in source data, always null here",
    "location": "string",
    "remote": "boolean, true if location or title mentions remote"
  }',
  'job_postings',
  60
);
```

A second task could target a real job board's public listing page (with a
`detail_url` follow-up for description text) once `08_compliance.md`'s
checklist has been run for that specific site — left as a stretch goal, not
required for the core demo.

## Seeding

These `INSERT` statements run once after applying
`supabase/migrations/0001_init.sql` (`05_deployment.md`). The first
orchestrator run's `enqueue_due_tasks()` (`01_database.md`) picks them up
immediately since they have no prior `queue` rows.
