-- demo_tasks.sql
-- Seeds the two demo task packs (see AI/06_demo_tasks.md). Run once after
-- applying supabase/migrations/0001_init.sql. The first orchestrator run's
-- enqueue_due_tasks() picks these up immediately since they have no prior
-- queue rows.

-- ============================================================================
-- Pack A — E-commerce price monitoring (books.toscrape.com sandbox)
--
-- webscraper.io's /test-sites/e-commerce/ paths are disallowed by its
-- robots.txt, so the worker's robots.txt check (AI/08_compliance.md) blocks
-- them. books.toscrape.com is a scraping sandbox with no robots.txt
-- restrictions.
-- ============================================================================

insert into tasks (name, type, target_url, request_params, parse_config, llm_schema, output_table, schedule_interval_minutes)
values (
  'books_mystery',
  'html',
  'https://books.toscrape.com/catalogue/category/books/mystery_3/index.html',
  '{}',
  '{
    "item_selector": ".product_pod",
    "static": {"category_hint": "mystery"},
    "fields": {
      "name":         {"selector": "h3 a",                  "attr": "title"},
      "price_text":   {"selector": ".price_color",          "attr": "text"},
      "availability": {"selector": ".instock.availability", "attr": "text"}
    }
  }',
  '{
    "product_name": "string, normalized book title",
    "brand": "string, author or publisher guessed from product_name, or null if unknown",
    "category": "string, book genre - use the category_hint from the input if present, otherwise infer from product_name, e.g. mystery, travel, fiction, classics, romance, other",
    "price": "number, numeric price value only (no currency symbol)",
    "currency": "string, ISO 4217 currency code inferred from the price symbol, e.g. GBP for £, USD for $",
    "in_stock": "boolean, true if availability text contains \"In stock\", false otherwise"
  }',
  'price_history',
  60
);

insert into tasks (name, type, target_url, request_params, parse_config, llm_schema, output_table, schedule_interval_minutes)
values (
  'books_travel',
  'html',
  'https://books.toscrape.com/catalogue/category/books/travel_2/index.html',
  '{}',
  '{
    "item_selector": ".product_pod",
    "static": {"category_hint": "travel"},
    "fields": {
      "name":         {"selector": "h3 a",                  "attr": "title"},
      "price_text":   {"selector": ".price_color",          "attr": "text"},
      "availability": {"selector": ".instock.availability", "attr": "text"}
    }
  }',
  '{
    "product_name": "string, normalized book title",
    "brand": "string, author or publisher guessed from product_name, or null if unknown",
    "category": "string, book genre - use the category_hint from the input if present, otherwise infer from product_name, e.g. mystery, travel, fiction, classics, romance, other",
    "price": "number, numeric price value only (no currency symbol)",
    "currency": "string, ISO 4217 currency code inferred from the price symbol, e.g. GBP for £, USD for $",
    "in_stock": "boolean, true if availability text contains \"In stock\", false otherwise"
  }',
  'price_history',
  60
);

-- ============================================================================
-- Pack B — Job listings analysis (realpython.github.io/fake-jobs)
-- ============================================================================

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
