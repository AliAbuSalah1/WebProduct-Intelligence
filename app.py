import pandas as pd
import plotly.express as px
import streamlit as st

from src.quality import load_report
from src.storage import load_products, run_sql_file

SYMBOLS = {"GBP": "£", "USD": "$", "EUR": "€"}

st.set_page_config(page_title="Web Product Intelligence", page_icon="📊", layout="wide")
st.title("Web Product Intelligence")
st.caption("Multi-source product data pipeline • HTML scraper (Books to Scrape) + JSON API (DummyJSON) • practice data")

df = load_products()
if df.empty:
    st.info("No data found yet. Run the pipeline in the project folder, then refresh this page.")
    st.code("python -m src.pipeline\nstreamlit run app.py", language="powershell")
    st.stop()

df["price"] = pd.to_numeric(df["price"], errors="coerce")
df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
df["category"] = df["category"].fillna("").astype(str)
df = df.dropna(subset=["price"])

with st.sidebar:
    st.header("Filters")
    # Prices from different sources use different currencies, so analyse one source at a time.
    source = st.selectbox("Source", sorted(df["source"].unique()))
    part = df[df["source"] == source]
    currency = part["currency"].iloc[0] if not part.empty else ""
    symbol = SYMBOLS.get(currency, currency + " ")
    search = st.text_input("Search title")
    lo, hi = float(part["price"].min()), float(part["price"].max())
    price_range = (lo, hi) if lo == hi else st.slider(f"Price range ({currency})", lo, hi, (lo, hi))
    categories = sorted(c for c in part["category"].unique() if c)
    selected_categories = st.multiselect("Category", categories, default=categories) if categories else []
    availability = sorted(part["availability"].dropna().astype(str).unique())
    selected_availability = st.multiselect("Availability", availability, default=availability)

filtered = part[part["price"].between(*price_range)]
if search:
    filtered = filtered[filtered["title"].astype(str).str.contains(search, case=False, na=False)]
if selected_categories:
    filtered = filtered[filtered["category"].isin(selected_categories)]
if selected_availability:
    filtered = filtered[filtered["availability"].astype(str).isin(selected_availability)]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Products", f"{len(filtered):,}")
c2.metric("Average price", f"{symbol}{filtered['price'].mean():.2f}" if not filtered.empty else "—")
c3.metric("Median price", f"{symbol}{filtered['price'].median():.2f}" if not filtered.empty else "—")
c4.metric("Average rating", f"{filtered['rating'].mean():.2f}/5" if filtered["rating"].notna().any() else "—")

left, right = st.columns(2)
with left:
    st.subheader("Price distribution")
    if not filtered.empty:
        st.plotly_chart(px.histogram(filtered, x="price", nbins=20, labels={"price": f"Price ({currency})"}),
                        width="stretch")
with right:
    st.subheader("Average price by category" if categories else "Availability")
    if not filtered.empty:
        if categories:
            by_cat = (filtered[filtered["category"] != ""].groupby("category")["price"]
                      .agg(["mean", "count"]).round(2).reset_index().sort_values("mean", ascending=False))
            st.plotly_chart(px.bar(by_cat, x="category", y="mean", hover_data=["count"],
                                   labels={"mean": f"Average price ({currency})", "category": "Category"}),
                            width="stretch")
        else:
            counts = filtered["availability"].value_counts().rename_axis("availability").reset_index(name="count")
            st.plotly_chart(px.bar(counts, x="availability", y="count"), width="stretch")

st.subheader("Price changes between the last two runs")
changes = run_sql_file("price_changes.sql")
changes = changes[changes["source"] == source] if not changes.empty else changes
if changes.empty:
    st.caption("No price changes yet. Each pipeline run is appended to the price history; "
               "run it again later and any differences appear here.")
else:
    st.dataframe(changes.drop(columns=["source"]), width="stretch", hide_index=True)

st.subheader("Collected product records")
cols = [c for c in ["title", "category", "price", "currency", "rating", "availability", "product_url"]
        if c in filtered.columns]
st.dataframe(filtered[cols], width="stretch", hide_index=True)
st.download_button("Download filtered CSV", filtered.to_csv(index=False).encode("utf-8-sig"),
                   file_name="filtered_products.csv", mime="text/csv")

report = load_report()
if report:
    with st.expander("Data quality report (last run)"):
        q1, q2, q3 = st.columns(3)
        q1.metric("Raw rows", report["raw_rows"])
        q2.metric("Valid rows", report["valid_rows"])
        q3.metric("Rejected", f"{report['rejected_rows']} ({report['rejected_pct']}%)")
        st.dataframe(pd.DataFrame(report["by_source"]).T, width="stretch")
