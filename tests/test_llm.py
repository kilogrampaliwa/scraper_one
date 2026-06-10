"""Sanity checks for prompt construction and response validation (AI/03_llm_layer.md).

No network access — only the pure prompt/validation helpers are exercised.
"""

import pytest

from scraper.llm import build_system_prompt, build_user_prompt, validate_items

ECOMMERCE_SCHEMA = {
    "product_name": "string, normalized product name without marketing fluff",
    "brand": "string, manufacturer/brand name, or null if unknown",
    "category": "string, one of: electronics, home, clothing, other",
    "price": "number, numeric price value only (no currency symbol)",
    "currency": "string, ISO 4217 currency code, e.g. PLN, EUR, USD",
    "in_stock": "boolean",
}

JOB_SCHEMA = {
    "job_title": "string, normalized job title",
    "tech_stack": "array of strings, normalized technology/tool names",
    "salary_min": "number or null",
    "remote": "boolean",
}


def test_build_system_prompt_lists_every_schema_field():
    prompt = build_system_prompt(ECOMMERCE_SCHEMA)

    for field_name, description in ECOMMERCE_SCHEMA.items():
        assert field_name in prompt
        assert description in prompt
    assert "items" in prompt


def test_build_user_prompt_embeds_raw_data_as_json():
    raw_data = [{"name": "Widget", "price_text": "$9.99"}]
    prompt = build_user_prompt(raw_data)

    assert '"name": "Widget"' in prompt
    assert '"$9.99"' in prompt


def test_validate_items_accepts_well_formed_response():
    raw_data = [{}, {}]
    items = [
        {
            "product_name": "Widget",
            "brand": None,
            "category": "electronics",
            "price": 9.99,
            "currency": "USD",
            "in_stock": True,
        },
        {
            "product_name": "Gadget",
            "brand": "Acme",
            "category": "electronics",
            "price": 19.99,
            "currency": "USD",
            "in_stock": False,
        },
    ]

    assert validate_items(items, raw_data, ECOMMERCE_SCHEMA) == items


def test_validate_items_rejects_length_mismatch():
    with pytest.raises(ValueError, match="expected 2 items"):
        validate_items([{}], [{}, {}], ECOMMERCE_SCHEMA)


def test_validate_items_rejects_missing_field():
    raw_data = [{}]
    items = [{k: v for k, v in {
        "product_name": "Widget",
        "brand": None,
        "category": "electronics",
        "price": 9.99,
        "currency": "USD",
        # "in_stock" missing
    }.items()}]

    with pytest.raises(ValueError, match="missing required field 'in_stock'"):
        validate_items(items, raw_data, ECOMMERCE_SCHEMA)


def test_validate_items_rejects_wrong_numeric_type():
    raw_data = [{}]
    items = [{
        "product_name": "Widget",
        "brand": None,
        "category": "electronics",
        "price": "9.99",  # should be a number, not a string
        "currency": "USD",
        "in_stock": True,
    }]

    with pytest.raises(ValueError, match="should be numeric"):
        validate_items(items, raw_data, ECOMMERCE_SCHEMA)


def test_validate_items_rejects_null_when_not_allowed():
    raw_data = [{}]
    items = [{
        "product_name": "Widget",
        "brand": None,
        "category": "electronics",
        "price": 9.99,
        "currency": "USD",
        "in_stock": None,  # schema says "boolean", no "or null"
    }]

    with pytest.raises(ValueError, match="null but schema doesn't allow null"):
        validate_items(items, raw_data, ECOMMERCE_SCHEMA)


def test_validate_items_allows_null_salary_for_jobs_schema():
    raw_data = [{}]
    items = [{
        "job_title": "Backend Engineer",
        "tech_stack": ["Python", "PostgreSQL"],
        "salary_min": None,
        "remote": True,
    }]

    assert validate_items(items, raw_data, JOB_SCHEMA) == items


def test_validate_items_rejects_non_array_tech_stack():
    raw_data = [{}]
    items = [{
        "job_title": "Backend Engineer",
        "tech_stack": "Python, PostgreSQL",
        "salary_min": None,
        "remote": True,
    }]

    with pytest.raises(ValueError, match="should be an array"):
        validate_items(items, raw_data, JOB_SCHEMA)
