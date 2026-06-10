"""Streamlit demo dashboard, reading the read-only views defined in
supabase/migrations/0001_init.sql via the Supabase anon key (AI/07_dashboard.md).
"""

from __future__ import annotations

import os

import pandas as pd
import streamlit as st
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

st.set_page_config(page_title="Cloud Scraper Pipeline — Demo", layout="wide")

TEXT = {
    "en": {
        "title": "Cloud Scraper Pipeline — Demo Dashboard",
        "lead": (
            "This dashboard demonstrates a **task-driven scraping + LLM-normalization "
            "pipeline**: scraping targets are defined as rows in a database table, so "
            "adding a new source needs no code changes. A scheduled job (every 30 "
            "minutes) scrapes the configured pages, an LLM normalizes the raw data "
            "into a consistent schema, and the results are stored here.\n\n"
            "Two demo task packs are included, both using **sandbox sites with sample "
            "data** (not real market data): price monitoring on "
            "[books.toscrape.com](https://books.toscrape.com) and job listings "
            "analysis on [realpython.github.io/fake-jobs]"
            "(https://realpython.github.io/fake-jobs/)."
        ),
        "tab_status": "Pipeline status",
        "tab_ecommerce": "E-commerce price monitoring",
        "tab_jobs": "Job listings analysis",
        "status_header": "Queue status",
        "status_caption": (
            "Counts per `queue.status`. Trigger the GitHub Actions workflow "
            "manually and refresh this page to watch the counts shift."
        ),
        "status_empty": "No queue rows yet — trigger the pipeline workflow to populate the queue.",
        "price_header": "Price monitoring",
        "price_empty": "No price history yet — run the pipeline a few times to accumulate data.",
        "category_label": "Category",
        "brand_label": "Brand",
        "price_over_time": "Price over time",
        "product_label": "Product",
        "no_products": "No products match the current filters.",
        "jobs_header": "Job listings",
        "jobs_empty": "No job postings yet — run the pipeline a few times to accumulate data.",
        "seniority_label": "Seniority",
        "tech_stack_label": "Tech stack",
        "postings_per_seniority": "Postings per seniority",
        "frequent_tech": "Most frequent tech stack entries",
        "no_tech_data": "No tech stack data for the current filters.",
        "avg_salary": "Average salary by seniority",
        "no_salary_data": "No salary data available for the current filters.",
        "config_error": "SUPABASE_URL and SUPABASE_ANON_KEY must be set (see .env.example).",
    },
    "pl": {
        "title": "Cloud Scraper Pipeline — Dashboard demo",
        "lead": (
            "Ten dashboard prezentuje **pipeline do scrapowania danych z normalizacją "
            "przez LLM, sterowany zadaniami**: cele scrapowania są zdefiniowane jako "
            "wiersze w tabeli bazy danych, więc dodanie nowego źródła nie wymaga zmian "
            "w kodzie. Zaplanowane zadanie (co 30 minut) scrapuje skonfigurowane "
            "strony, LLM normalizuje surowe dane do spójnego schematu, a wyniki są "
            "zapisywane i prezentowane tutaj.\n\n"
            "Dołączone są dwie przykładowe paczki zadań, obie korzystające ze "
            "**stron testowych z przykładowymi danymi** (nie są to realne dane "
            "rynkowe): monitoring cen na [books.toscrape.com]"
            "(https://books.toscrape.com) oraz analiza ofert pracy na "
            "[realpython.github.io/fake-jobs]"
            "(https://realpython.github.io/fake-jobs/)."
        ),
        "tab_status": "Status pipeline'u",
        "tab_ecommerce": "Monitoring cen e-commerce",
        "tab_jobs": "Analiza ofert pracy",
        "status_header": "Status kolejki",
        "status_caption": (
            "Liczba wpisów wg `queue.status`. Uruchom workflow w GitHub Actions "
            "ręcznie i odśwież tę stronę, by zobaczyć zmianę liczników."
        ),
        "status_empty": "Brak jeszcze wpisów w kolejce — uruchom workflow pipeline'u, aby ją zapełnić.",
        "price_header": "Monitoring cen",
        "price_empty": "Brak jeszcze historii cen — uruchom pipeline kilka razy, aby zgromadzić dane.",
        "category_label": "Kategoria",
        "brand_label": "Marka",
        "price_over_time": "Cena w czasie",
        "product_label": "Produkt",
        "no_products": "Żaden produkt nie pasuje do wybranych filtrów.",
        "jobs_header": "Oferty pracy",
        "jobs_empty": "Brak jeszcze ofert pracy — uruchom pipeline kilka razy, aby zgromadzić dane.",
        "seniority_label": "Poziom doświadczenia",
        "tech_stack_label": "Stos technologiczny",
        "postings_per_seniority": "Liczba ofert wg poziomu doświadczenia",
        "frequent_tech": "Najczęstsze technologie",
        "no_tech_data": "Brak danych o technologiach dla wybranych filtrów.",
        "avg_salary": "Średnie wynagrodzenie wg poziomu doświadczenia",
        "no_salary_data": "Brak danych o wynagrodzeniach dla wybranych filtrów.",
        "config_error": "Zmienne SUPABASE_URL i SUPABASE_ANON_KEY muszą być ustawione (zobacz .env.example).",
    },
}

lang = st.sidebar.selectbox(
    "Language / Język",
    options=["en", "pl"],
    format_func=lambda code: "English" if code == "en" else "Polski",
)
T = TEXT[lang]


@st.cache_resource
def get_client():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error(T["config_error"])
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@st.cache_data(ttl=60)
def load_view(view_name: str) -> pd.DataFrame:
    client = get_client()
    response = client.table(view_name).select("*").execute()
    return pd.DataFrame(response.data)


st.title(T["title"])
st.markdown(T["lead"])

tab_status, tab_ecommerce, tab_jobs = st.tabs(
    [T["tab_status"], T["tab_ecommerce"], T["tab_jobs"]]
)

# ----------------------------------------------------------------------------
# Pipeline status
# ----------------------------------------------------------------------------
with tab_status:
    st.header(T["status_header"])
    st.caption(T["status_caption"])

    status_df = load_view("v_pipeline_status")
    if status_df.empty:
        st.info(T["status_empty"])
    else:
        st.bar_chart(status_df.set_index("status")["count"])
        st.dataframe(status_df, use_container_width=True)

# ----------------------------------------------------------------------------
# E-commerce price monitoring
# ----------------------------------------------------------------------------
with tab_ecommerce:
    st.header(T["price_header"])

    price_df = load_view("v_price_history")
    if price_df.empty:
        st.info(T["price_empty"])
    else:
        col1, col2 = st.columns(2)
        categories = sorted(price_df["category"].dropna().unique())
        brands = sorted(price_df["brand"].dropna().unique())

        selected_categories = col1.multiselect(T["category_label"], categories)
        selected_brands = col2.multiselect(T["brand_label"], brands)

        filtered = price_df.copy()
        if selected_categories:
            filtered = filtered[filtered["category"].isin(selected_categories)]
        if selected_brands:
            filtered = filtered[filtered["brand"].isin(selected_brands)]

        st.dataframe(filtered, use_container_width=True)

        st.subheader(T["price_over_time"])
        product_names = sorted(filtered["product_name"].dropna().unique())
        if product_names:
            selected_product = st.selectbox(T["product_label"], product_names)
            product_df = (
                filtered[filtered["product_name"] == selected_product]
                .sort_values("scraped_at")
                .set_index("scraped_at")
            )
            st.line_chart(product_df["price"])
        else:
            st.info(T["no_products"])

# ----------------------------------------------------------------------------
# Job listings analysis
# ----------------------------------------------------------------------------
with tab_jobs:
    st.header(T["jobs_header"])

    jobs_df = load_view("v_job_postings")
    if jobs_df.empty:
        st.info(T["jobs_empty"])
    else:
        col1, col2 = st.columns(2)
        seniorities = sorted(jobs_df["seniority"].dropna().unique())
        all_tech = sorted({tech for stack in jobs_df["tech_stack"].dropna() for tech in (stack or [])})

        selected_seniority = col1.multiselect(T["seniority_label"], seniorities)
        selected_tech = col2.multiselect(T["tech_stack_label"], all_tech)

        filtered = jobs_df.copy()
        if selected_seniority:
            filtered = filtered[filtered["seniority"].isin(selected_seniority)]
        if selected_tech:
            filtered = filtered[
                filtered["tech_stack"].apply(
                    lambda stack: isinstance(stack, list) and any(tech in stack for tech in selected_tech)
                )
            ]

        st.dataframe(filtered, use_container_width=True)

        st.subheader(T["postings_per_seniority"])
        st.bar_chart(filtered["seniority"].value_counts())

        st.subheader(T["frequent_tech"])
        tech_series = pd.Series(
            [tech for stack in filtered["tech_stack"].dropna() for tech in (stack or [])],
            dtype="object",
        )
        if not tech_series.empty:
            st.bar_chart(tech_series.value_counts())
        else:
            st.info(T["no_tech_data"])

        st.subheader(T["avg_salary"])
        salary_df = filtered.groupby("seniority")[["salary_min", "salary_max"]].mean(numeric_only=True)
        if salary_df.dropna(how="all").empty:
            st.info(T["no_salary_data"])
        else:
            st.dataframe(salary_df, use_container_width=True)
