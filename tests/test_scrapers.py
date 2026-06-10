"""Sanity checks for parsing/extraction logic (AI/02_scrapers.md).

These tests exercise `validate()` / `emit()` directly with sample
HTML/JSON payloads — no network access involved.
"""

from scraper.api import APIScraper, _resolve_path
from scraper.base import build_scraper
from scraper.html import HTMLScraper

SAMPLE_HTML = """
<div class="thumbnail">
  <a href="/product/1" class="title" title="Asus VivoBook X441NA-GA190">Asus VivoBook...</a>
  <div class="caption">
    <p class="description">Asus VivoBook X441NA-GA190T Chocolate Black, 14", Celeron N3450, 4GB, 1TB, Endless OS</p>
    <h4 class="price">$295.99</h4>
  </div>
</div>
<div class="thumbnail">
  <a href="/product/2" class="title" title="Lenovo IdeaPad 3">Lenovo IdeaPad 3</a>
  <div class="caption">
    <p class="description">Lenovo IdeaPad 3, 15.6", Ryzen 5, 8GB, 256GB SSD, out of stock</p>
    <h4 class="price">$489.00</h4>
  </div>
</div>
"""

HTML_PARSE_CONFIG = {
    "item_selector": ".thumbnail",
    "static": {"category_hint": "laptops"},
    "fields": {
        "name": {"selector": ".title", "attr": "title"},
        "price_text": {"selector": ".price", "attr": "text"},
        "description": {"selector": ".description", "attr": "text"},
    },
}


def _make_html_scraper(parse_config=HTML_PARSE_CONFIG):
    return HTMLScraper(
        task_id=1,
        queue_id=1,
        name="ecommerce_laptops",
        url="https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops",
        params={},
        parse_config=parse_config,
        max_retries=3,
    )


def test_html_scraper_validate_true_when_items_present():
    scraper = _make_html_scraper()
    assert scraper.validate(SAMPLE_HTML) is True


def test_html_scraper_validate_false_when_selector_missing():
    scraper = _make_html_scraper({**HTML_PARSE_CONFIG, "item_selector": ".does-not-exist"})
    assert scraper.validate(SAMPLE_HTML) is False


def test_html_scraper_validate_false_on_empty_response():
    scraper = _make_html_scraper()
    assert scraper.validate("") is False


def test_html_scraper_emit_extracts_fields_and_static():
    scraper = _make_html_scraper()
    items = scraper.emit(SAMPLE_HTML)

    assert len(items) == 2
    assert items[0]["name"] == "Asus VivoBook X441NA-GA190"
    assert items[0]["price_text"] == "$295.99"
    assert "Celeron N3450" in items[0]["description"]
    assert items[0]["category_hint"] == "laptops"
    assert items[1]["name"] == "Lenovo IdeaPad 3"


def test_html_scraper_emit_handles_missing_field_as_none():
    parse_config = {
        "item_selector": ".thumbnail",
        "fields": {
            "name": {"selector": ".title", "attr": "title"},
            "missing": {"selector": ".does-not-exist", "attr": "text"},
        },
    }
    scraper = _make_html_scraper(parse_config)
    items = scraper.emit(SAMPLE_HTML)

    assert items[0]["missing"] is None


SAMPLE_API_JSON = {
    "data": {
        "items": [
            {"title": "Widget A", "price": {"amount": 9.99, "currency": "USD"}},
            {"title": "Widget B", "price": {"amount": 19.99, "currency": "USD"}},
        ]
    }
}

API_PARSE_CONFIG = {
    "root": "data.items",
    "fields": {
        "product_name": "title",
        "price": "price.amount",
        "currency": "price.currency",
    },
}


def _make_api_scraper(parse_config=API_PARSE_CONFIG):
    return APIScraper(
        task_id=2,
        queue_id=2,
        name="api_demo",
        url="https://example.com/api/products",
        params={},
        parse_config=parse_config,
        max_retries=3,
    )


def test_resolve_path_walks_nested_dicts():
    assert _resolve_path(SAMPLE_API_JSON, "data.items") == SAMPLE_API_JSON["data"]["items"]
    assert _resolve_path(SAMPLE_API_JSON, "data.missing") is None
    assert _resolve_path(SAMPLE_API_JSON, None) is SAMPLE_API_JSON


def test_api_scraper_validate_true_when_root_present():
    scraper = _make_api_scraper()
    assert scraper.validate(SAMPLE_API_JSON) is True


def test_api_scraper_validate_false_when_root_missing():
    scraper = _make_api_scraper({**API_PARSE_CONFIG, "root": "data.missing"})
    assert scraper.validate(SAMPLE_API_JSON) is False


def test_api_scraper_emit_resolves_field_paths():
    scraper = _make_api_scraper()
    items = scraper.emit(SAMPLE_API_JSON)

    assert items == [
        {"product_name": "Widget A", "price": 9.99, "currency": "USD"},
        {"product_name": "Widget B", "price": 19.99, "currency": "USD"},
    ]


def test_api_scraper_emit_wraps_single_object_in_list():
    scraper = _make_api_scraper({"root": None, "fields": {"product_name": "title"}})
    items = scraper.emit({"title": "Solo Widget"})

    assert items == [{"product_name": "Solo Widget"}]


def test_build_scraper_factory_selects_by_task_type():
    queue_row = {"id": 1, "url": None, "max_retries": 3}
    config = type("Cfg", (), {"base_delay": 1.0})()

    html_task = {"task_id": 1, "name": "html_task", "type": "html", "target_url": "https://example.com", "request_params": {}, "parse_config": {}}
    api_task = {"task_id": 2, "name": "api_task", "type": "api", "target_url": "https://example.com/api", "request_params": {}, "parse_config": {}}

    assert isinstance(build_scraper(queue_row, html_task, config), HTMLScraper)
    assert isinstance(build_scraper(queue_row, api_task, config), APIScraper)
