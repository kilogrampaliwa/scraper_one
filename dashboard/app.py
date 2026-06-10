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


@st.cache_resource
def get_client():
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        st.error("SUPABASE_URL and SUPABASE_ANON_KEY must be set (see .env.example).")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_ANON_KEY)


@st.cache_data(ttl=60)
def load_view(view_name: str) -> pd.DataFrame:
    client = get_client()
    response = client.table(view_name).select("*").execute()
    return pd.DataFrame(response.data)


st.title("Cloud Scraper Pipeline — Demo Dashboard")

tab_status, tab_ecommerce, tab_jobs = st.tabs(
    ["Pipeline status", "E-commerce price monitoring", "Job listings analysis"]
)

# ----------------------------------------------------------------------------
# Pipeline status
# ----------------------------------------------------------------------------
with tab_status:
    st.header("Queue status")
    st.caption(
        "Counts per `queue.status`. Trigger the GitHub Actions workflow "
        "manually and refresh this page to watch the counts shift."
    )

    status_df = load_view("v_pipeline_status")
    if status_df.empty:
        st.info("No queue rows yet — trigger the pipeline workflow to populate the queue.")
    else:
        st.bar_chart(status_df.set_index("status")["count"])
        st.dataframe(status_df, use_container_width=True)

# ----------------------------------------------------------------------------
# E-commerce price monitoring
# ----------------------------------------------------------------------------
with tab_ecommerce:
    st.header("Price monitoring")

    price_df = load_view("v_price_history")
    if price_df.empty:
        st.info("No price history yet — run the pipeline a few times to accumulate data.")
    else:
        col1, col2 = st.columns(2)
        categories = sorted(price_df["category"].dropna().unique())
        brands = sorted(price_df["brand"].dropna().unique())

        selected_categories = col1.multiselect("Category", categories)
        selected_brands = col2.multiselect("Brand", brands)

        filtered = price_df.copy()
        if selected_categories:
            filtered = filtered[filtered["category"].isin(selected_categories)]
        if selected_brands:
            filtered = filtered[filtered["brand"].isin(selected_brands)]

        st.dataframe(filtered, use_container_width=True)

        st.subheader("Price over time")
        product_names = sorted(filtered["product_name"].dropna().unique())
        if product_names:
            selected_product = st.selectbox("Product", product_names)
            product_df = (
                filtered[filtered["product_name"] == selected_product]
                .sort_values("scraped_at")
                .set_index("scraped_at")
            )
            st.line_chart(product_df["price"])
        else:
            st.info("No products match the current filters.")

# ----------------------------------------------------------------------------
# Job listings analysis
# ----------------------------------------------------------------------------
with tab_jobs:
    st.header("Job listings")

    jobs_df = load_view("v_job_postings")
    if jobs_df.empty:
        st.info("No job postings yet — run the pipeline a few times to accumulate data.")
    else:
        col1, col2 = st.columns(2)
        seniorities = sorted(jobs_df["seniority"].dropna().unique())
        all_tech = sorted({tech for stack in jobs_df["tech_stack"].dropna() for tech in (stack or [])})

        selected_seniority = col1.multiselect("Seniority", seniorities)
        selected_tech = col2.multiselect("Tech stack", all_tech)

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

        st.subheader("Postings per seniority")
        st.bar_chart(filtered["seniority"].value_counts())

        st.subheader("Most frequent tech stack entries")
        tech_series = pd.Series(
            [tech for stack in filtered["tech_stack"].dropna() for tech in (stack or [])],
            dtype="object",
        )
        if not tech_series.empty:
            st.bar_chart(tech_series.value_counts())
        else:
            st.info("No tech stack data for the current filters.")

        st.subheader("Average salary by seniority")
        salary_df = filtered.groupby("seniority")[["salary_min", "salary_max"]].mean(numeric_only=True)
        if salary_df.dropna(how="all").empty:
            st.info("No salary data available for the current filters.")
        else:
            st.dataframe(salary_df, use_container_width=True)
