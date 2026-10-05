"""
E-commerce Sales & Customer Insights Dashboard (Streamlit)
Dataset: UCI Online Retail II  (https://archive.ics.uci.edu/dataset/502/online+retail+ii)

Run with:   streamlit run app.py
Put online_retail_II.xlsx in the same folder as this file (or upload it in the app).
"""
import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="E-commerce Sales & Customer Insights",
                   page_icon="🛒", layout="wide")

DATA_FILE = "online_retail_II.xlsx"
CACHE_FILE = ".online_retail_clean.pkl"   # speeds up every run after the first

COLS = {"Invoice": "invoice", "StockCode": "stock_code", "Description": "description",
        "Quantity": "quantity", "InvoiceDate": "order_date", "Price": "unit_price",
        "Customer ID": "customer_id", "Country": "country"}

NON_PRODUCT = ["POST", "D", "M", "DOT", "BANK CHARGES", "CRUK", "AMAZONFEE",
               "S", "B", "ADJUST", "TEST001", "TEST002"]
COUNTRY_FIX = {"EIRE": "Ireland", "RSA": "South Africa", "USA": "United States",
               "Unspecified": "Unknown"}

# First match wins, so the order matters
CATEGORY_KEYWORDS = {
    "Christmas & Seasonal":     ["CHRISTMAS", "XMAS", "EASTER", "ADVENT", "SANTA"],
    "Lighting & Candles":       ["CANDLE", "LIGHT", "LAMP", "LANTERN"],
    "Kitchen & Dining":         ["MUG", "CUP", "PLATE", "BOWL", "TEAPOT", "CAKE", "SPOON",
                                 "JUG", "GLASS", "BOTTLE", "KITCHEN"],
    "Bags & Storage":           ["BAG", "BOX", "TIN", "BASKET", "JAR", "CASE"],
    "Cards, Paper & Gift Wrap": ["CARD", "WRAP", "PAPER", "RIBBON", "NOTEBOOK", "STICKER", "GIFT"],
    "Home Decor":               ["FRAME", "CUSHION", "CLOCK", "SIGN", "MIRROR", "HOOK",
                                 "DOORMAT", "HANGING", "HEART", "WALL", "VASE"],
    "Toys & Games":             ["TOY", "GAME", "DOLL", "PUZZLE", "PLAYHOUSE", "SKIPPING"],
}
GUEST = "Guest (no customer ID)"


def money(x):
    return f"£{x:,.0f}"


def show(fig):
    st.plotly_chart(fig, width="stretch")


# ---------------------------------------------------------------------------
# 1. DATA: load -> combine -> clean -> categories -> RFM segments
# ---------------------------------------------------------------------------
def categorize(desc):
    for cat, words in CATEGORY_KEYWORDS.items():
        if any(w in desc for w in words):
            return cat
    return "Other"


def clean(raw):
    df = raw.rename(columns=COLS)
    missing = set(COLS.values()) - set(df.columns)
    if missing:
        raise ValueError(f"The file is missing these columns: {sorted(missing)}")
    df = df[list(COLS.values())]

    log = {"Raw rows (both years combined)": len(df)}

    df = df.drop_duplicates()
    log["After removing duplicate rows"] = len(df)

    df["invoice"] = df["invoice"].astype(str)
    is_refund = df["invoice"].str.startswith("C")
    refunds = df[is_refund].copy()
    df = df[~is_refund].copy()
    log["After removing refund invoices (start with 'C')"] = len(df)

    df = df[(df["quantity"] > 0) & (df["unit_price"] > 0)]
    log["After removing zero/negative quantity or price"] = len(df)

    df["stock_code"] = df["stock_code"].astype(str).str.upper()
    df = df[~df["stock_code"].isin(NON_PRODUCT)]
    log["After removing non-product codes (postage, fees...)"] = len(df)

    df = df.dropna(subset=["description"]).copy()
    df["description"] = df["description"].str.strip().str.upper()
    df["country"] = df["country"].replace(COUNTRY_FIX)
    log["Final clean rows"] = len(df)

    df["revenue"] = df["quantity"] * df["unit_price"]
    df["order_month"] = df["order_date"].dt.to_period("M").dt.to_timestamp()

    # categories (worked out once per unique product name, so it is fast)
    cat_map = {d: categorize(d) for d in df["description"].unique()}
    df["category"] = df["description"].map(cat_map)

    # ---- RFM segments (customers with an ID only) ----
    dc = df[df["customer_id"].notna()]
    snapshot = dc["order_date"].max() + pd.Timedelta(days=1)
    g = dc.groupby("customer_id")
    rfm = pd.DataFrame({
        "recency": (snapshot - g["order_date"].max()).dt.days,
        "frequency": g["invoice"].nunique(),
        "monetary": g["revenue"].sum(),
    })
    rfm["R"] = pd.qcut(rfm["recency"], 4, labels=[4, 3, 2, 1]).astype(int)
    rfm["F"] = pd.qcut(rfm["frequency"].rank(method="first"), 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["M"] = pd.qcut(rfm["monetary"], 4, labels=[1, 2, 3, 4]).astype(int)
    rfm["segment"] = np.select(
        [(rfm.R >= 3) & (rfm.F >= 3), (rfm.R <= 2) & (rfm.F >= 3), (rfm.R >= 3) & (rfm.F <= 2)],
        ["Champions", "At Risk (valuable, slipping)", "New / Promising"],
        default="Hibernating")

    df["segment"] = df["customer_id"].map(rfm["segment"]).fillna(GUEST)
    df["cohort_month"] = df["customer_id"].map(dc.groupby("customer_id")["order_month"].min())

    # ---- refunds table ----
    refunds["stock_code"] = refunds["stock_code"].astype(str).str.upper()
    refunds["is_product"] = ~refunds["stock_code"].isin(NON_PRODUCT)
    refunds["description"] = refunds["description"].fillna("UNKNOWN").str.strip().str.upper()
    refunds["country"] = refunds["country"].replace(COUNTRY_FIX)
    refunds["refund_value"] = refunds["quantity"].abs() * refunds["unit_price"]
    refunds["order_month"] = refunds["order_date"].dt.to_period("M").dt.to_timestamp()
    refunds["category"] = refunds["description"].map(
        {d: categorize(d) for d in refunds["description"].unique()})
    refunds["segment"] = refunds["customer_id"].map(rfm["segment"]).fillna(GUEST)

    # ---- explicit customer / product / location tables (the "data model") ----
    last = dc.sort_values("order_date").groupby("customer_id")
    customers = pd.DataFrame({
        "country": last["country"].last(),
        "first_order": g["order_date"].min(),
        "last_order": g["order_date"].max(),
        "orders": g["invoice"].nunique(),
        "revenue": g["revenue"].sum(),
    }).join(rfm["segment"]).reset_index()
    customers["customer_id"] = customers["customer_id"].astype(int)

    products = (df.groupby("stock_code")
                  .agg(description=("description", "first"), category=("category", "first"),
                       units_sold=("quantity", "sum"), revenue=("revenue", "sum"))
                  .reset_index())
    locations = (df.groupby("country")
                   .agg(orders=("invoice", "nunique"), customers=("customer_id", "nunique"),
                        revenue=("revenue", "sum")).reset_index())

    for col in ["country", "category", "description", "segment", "stock_code"]:
        df[col] = df[col].astype("category")
    for col in ["country", "category", "segment"]:
        refunds[col] = refunds[col].astype("category")

    return {"df": df, "refunds": refunds, "log": log, "rfm": rfm,
            "customers": customers, "products": products, "locations": locations}


@st.cache_resource(show_spinner="Loading and cleaning the data. The first run takes 1-3 minutes...")
def load_data(path):
    if os.path.exists(CACHE_FILE) and os.path.getmtime(CACHE_FILE) >= os.path.getmtime(path):
        try:
            return pd.read_pickle(CACHE_FILE)
        except Exception:
            pass  # cache from another pandas version -> rebuild
    if path.lower().endswith(".csv"):
        raw = pd.read_csv(path, parse_dates=["InvoiceDate"])
    else:
        raw = pd.concat(pd.read_excel(path, sheet_name=None).values(), ignore_index=True)
    result = clean(raw)
    pd.to_pickle(result, CACHE_FILE)
    return result


# ---------------------------------------------------------------------------
# 2. Get the file (local file, or upload box)
# ---------------------------------------------------------------------------
data_path = next((p for p in [DATA_FILE, "online_retail_II.csv"] if os.path.exists(p)), None)
if data_path is None:
    st.title("🛒 E-commerce Sales & Customer Insights")
    st.warning(f"`{DATA_FILE}` was not found next to app.py. Upload it below "
               "(download: https://archive.ics.uci.edu/dataset/502/online+retail+ii).")
    up = st.file_uploader("Upload online_retail_II.xlsx", type=["xlsx"])
    if up is not None:
        with open(DATA_FILE, "wb") as f:
            f.write(up.getbuffer())
        st.rerun()
    st.stop()

try:
    D = load_data(data_path)
except Exception as e:
    st.error(f"Could not load the data: {e}")
    st.stop()

df, refunds, rfm = D["df"], D["refunds"], D["rfm"]

# ---------------------------------------------------------------------------
# 3. Sidebar filters
# ---------------------------------------------------------------------------
st.sidebar.header("🎛️ Filters")
min_d, max_d = df["order_date"].min().date(), df["order_date"].max().date()
dates = st.sidebar.date_input("Date range", value=(min_d, max_d), min_value=min_d, max_value=max_d)
if not isinstance(dates, (tuple, list)) or len(dates) != 2:
    st.info("Pick both a start and an end date in the sidebar.")
    st.stop()

region = st.sidebar.radio("Market", ["All markets", "UK only", "Export markets only (non-UK)"])
all_countries = sorted(df["country"].cat.categories)
sel_countries = st.sidebar.multiselect("Specific countries (empty = all)", all_countries)
all_cats = sorted(df["category"].cat.categories)
sel_cats = st.sidebar.multiselect("Product categories (empty = all)", all_cats)
all_segs = [s for s in ["Champions", "At Risk (valuable, slipping)", "New / Promising",
                        "Hibernating", GUEST] if s in df["segment"].cat.categories]
sel_segs = st.sidebar.multiselect("Customer segments (empty = all)", all_segs)


def apply_filters(d):
    m = (d["order_date"].dt.date >= dates[0]) & (d["order_date"].dt.date <= dates[1])
    if region == "UK only":
        m &= d["country"] == "United Kingdom"
    elif region.startswith("Export"):
        m &= d["country"] != "United Kingdom"
    if sel_countries:
        m &= d["country"].isin(sel_countries)
    if sel_cats:
        m &= d["category"].isin(sel_cats)
    if sel_segs:
        m &= d["segment"].isin(sel_segs)
    return d[m]


f = apply_filters(df)
fr = apply_filters(refunds)

st.title("🛒 E-commerce Sales & Customer Insights")
st.caption(f"UCI Online Retail II · {dates[0]:%d %b %Y} to {dates[1]:%d %b %Y} · "
           f"{len(f):,} order lines after filters (of {len(df):,} clean lines)")
if f.empty:
    st.warning("No data matches these filters. Widen the filters in the sidebar.")
    st.stop()

# ---------------------------------------------------------------------------
# 4. KPIs and helper tables
# ---------------------------------------------------------------------------
revenue = f["revenue"].sum()
orders = f["invoice"].nunique()
fc = f[f["customer_id"].notna()]
customers = fc["customer_id"].nunique()
aov = revenue / orders
orders_per_cust = fc.groupby("customer_id", observed=True)["invoice"].nunique()
repeat_rate = (orders_per_cust > 1).mean() if len(orders_per_cust) else np.nan
refund_value = fr["refund_value"].sum()
refund_rate = refund_value / revenue

monthly = (f.groupby("order_month").agg(revenue=("revenue", "sum"), orders=("invoice", "nunique"))
             .reset_index())


def cohort_retention(d):
    dc = d[d["customer_id"].notna()]
    if dc.empty:
        return None
    idx = ((dc["order_month"].dt.year - dc["cohort_month"].dt.year) * 12
           + dc["order_month"].dt.month - dc["cohort_month"].dt.month)
    t = pd.DataFrame({"cohort": dc["cohort_month"], "idx": idx, "cid": dc["customer_id"]})
    counts = t.groupby(["cohort", "idx"])["cid"].nunique().unstack()
    if 0 not in counts.columns:
        return None
    counts = counts[counts[0].notna()]
    ret = counts.div(counts[0], axis=0) * 100
    ret.index = ret.index.strftime("%Y-%m")
    return ret


def segment_table(d):
    dc = d[d["customer_id"].notna()]
    s = (dc.groupby("segment", observed=True)
           .agg(customers=("customer_id", "nunique"), revenue=("revenue", "sum")).reset_index())
    if s.empty:
        return s
    s["revenue_share_%"] = s["revenue"] / s["revenue"].sum() * 100
    s["avg_recency_days"] = s["segment"].map(
        rfm.groupby("segment")["recency"].mean()).astype(float)
    return s.sort_values("revenue", ascending=False)


def category_table(d):
    c = (d.groupby("category", observed=True)
           .agg(revenue=("revenue", "sum"), units=("quantity", "sum"),
                products=("stock_code", "nunique")).reset_index())
    c["revenue_per_product"] = c["revenue"] / c["products"]
    c["share_%"] = c["revenue"] / c["revenue"].sum() * 100
    return c


def country_table(d):
    c = (d.groupby("country", observed=True)
           .agg(revenue=("revenue", "sum"), orders=("invoice", "nunique"),
                customers=("customer_id", "nunique")).reset_index())
    c["aov"] = c["revenue"] / c["orders"]
    return c[c["orders"] > 0]


ret = cohort_retention(f)
seg = segment_table(f)
cat = category_table(f)
cty = country_table(f)


# ---------------------------------------------------------------------------
# 5. Recommendations (built from the filtered numbers)
# ---------------------------------------------------------------------------
def recommendations():
    recs = []
    if not seg.empty:
        ch = seg[seg["segment"] == "Champions"]
        if len(ch):
            r = ch.iloc[0]
            recs.append(f"**Protect Champions.** {int(r['customers']):,} customers produce "
                        f"{r['revenue_share_%']:.0f}% of the revenue from identified customers. "
                        "Launch a loyalty / trade-account programme with early access to new stock.")
        ar = seg[seg["segment"].str.startswith("At Risk")]
        if len(ar):
            r = ar.iloc[0]
            recs.append(f"**Win back at-risk customers.** {int(r['customers']):,} previously frequent "
                        f"buyers have gone quiet (about {r['avg_recency_days']:.0f} days since their "
                        f"last order) and represent {money(r['revenue'])} of revenue. "
                        "Send a targeted win-back offer.")
    if ret is not None and 1 in ret.columns and ret[1].notna().any():
        recs.append(f"**Fix early retention.** Only about {ret[1].mean():.0f}% of new customers buy "
                    "again the next month. Add a follow-up email or discount in the first 30 days.")
    if len(monthly) >= 12:
        share = monthly[monthly["order_month"].dt.month.isin([9, 10, 11])]["revenue"].sum() / revenue
        peak = monthly.loc[monthly["revenue"].idxmax()]
        recs.append(f"**Plan for peak season.** September to November brings {share:.0%} of revenue "
                    f"(best month: {peak['order_month']:%b %Y}, {money(peak['revenue'])}). "
                    "Secure stock and marketing budget before September.")
    named = cat[cat["category"] != "Other"]
    if len(named) >= 2:
        worst = named.sort_values("revenue_per_product").iloc[0]
        best = named.sort_values("revenue", ascending=False).iloc[0]
        recs.append(f"**Review the weakest category.** '{worst['category']}' earns the least per "
                    f"product ({money(worst['revenue_per_product'])}). Cut slow items or bundle them "
                    f"with '{best['category']}' best-sellers.")
    uk_rev = cty.loc[cty["country"] == "United Kingdom", "revenue"].sum()
    exp = cty[cty["country"] != "United Kingdom"].sort_values("revenue", ascending=False)
    if uk_rev > 0 and len(exp):
        recs.append(f"**Grow exports.** The UK is {uk_rev / cty['revenue'].sum():.0%} of revenue. "
                    f"{exp.iloc[0]['country']} is the largest export market "
                    f"({money(exp.iloc[0]['revenue'])}), so test targeted campaigns there first.")
    if refund_value > 0:
        pr = fr[fr["is_product"]].groupby("description", observed=True)["refund_value"].sum()
        extra = f" The most returned product is '{pr.idxmax()}'." if len(pr) else ""
        recs.append(f"**Reduce returns.** Refunds equal {refund_rate:.1%} of revenue.{extra} "
                    "Check descriptions, packaging and quality for the top returned items.")
    return recs


# ---------------------------------------------------------------------------
# 6. Tabs
# ---------------------------------------------------------------------------
tab_over, tab_cust, tab_prod, tab_geo, tab_ret, tab_data = st.tabs(
    ["📊 Overview", "👥 Customers", "🛍️ Products & Categories", "🌍 Geography",
     "↩️ Returns", "🧹 Data & Method"])

with tab_over:
    c = st.columns(6)
    c[0].metric("Revenue", money(revenue))
    c[1].metric("Orders", f"{orders:,}")
    c[2].metric("Customers (with ID)", f"{customers:,}")
    c[3].metric("Avg order value", f"£{aov:,.2f}")
    c[4].metric("Repeat-customer rate", f"{repeat_rate:.1%}" if pd.notna(repeat_rate) else "n/a")
    c[5].metric("Refunds / revenue", f"{refund_rate:.1%}")
    st.caption("Margin is not shown because the dataset has no cost data. Repeat-customer rate = share "
               "of identified customers with 2+ orders in the selected period.")

    a, b = st.columns(2)
    with a:
        show(px.bar(monthly, x="order_month", y="revenue", title="Monthly revenue (£)",
                    labels={"order_month": "Month", "revenue": "Revenue (£)"}))
    with b:
        show(px.line(monthly, x="order_month", y="orders", markers=True, title="Monthly orders",
                     labels={"order_month": "Month", "orders": "Orders"}))
    st.caption("The last month in the data (Dec 2011) is incomplete: the data stops on 9 December.")

    st.subheader("💡 Data-backed recommendations")
    st.caption("These update automatically when you change the filters.")
    for i, r in enumerate(recommendations(), 1):
        st.markdown(f"{i}. {r}")

with tab_cust:
    st.subheader("Customer segments (RFM)")
    st.caption("Recency, Frequency and Monetary scores (1-4) are calculated once on all customers, so a "
               "customer keeps the same segment whatever filters you choose.")
    if seg.empty:
        st.info("No identified customers in this selection.")
    else:
        a, b = st.columns([3, 2])
        with a:
            st.dataframe(seg.rename(columns={"revenue": "revenue (£)"}).style.format(
                {"customers": "{:,.0f}", "revenue (£)": "£{:,.0f}", "revenue_share_%": "{:.1f}",
                 "avg_recency_days": "{:.0f}"}), width="stretch", hide_index=True)
        with b:
            show(px.bar(seg, x="segment", y="revenue", color="segment",
                        title="Revenue by segment (£)").update_layout(showlegend=False))

    st.subheader("Cohort retention")
    st.caption("Customers grouped by month of first purchase. Each row shows the % of that group who "
               "bought again N months later. Column 0 is always 100%.")
    if ret is None:
        st.info("Not enough customer data for a cohort view with these filters.")
    else:
        fig = px.imshow(ret.iloc[:, :13], text_auto=".0f", aspect="auto",
                        color_continuous_scale="Blues",
                        labels=dict(x="Months since first purchase", y="Cohort", color="% active"))
        show(fig)
        if 1 in ret.columns:
            st.metric("Average month-1 retention", f"{ret[1].mean():.1f}%")

    st.subheader("High-value customers")
    cust_rev = fc.groupby("customer_id", observed=True)["revenue"].sum().sort_values(ascending=False)
    if len(cust_rev):
        top_n = max(int(len(cust_rev) * 0.10), 1)
        st.metric("Revenue share of the top 10% of customers",
                  f"{cust_rev.head(top_n).sum() / cust_rev.sum():.1%}")
        top = cust_rev.head(10).reset_index()
        top["customer_id"] = top["customer_id"].astype(int)
        top = top.merge(D["customers"][["customer_id", "country", "orders", "segment"]],
                        on="customer_id", how="left")
        top = top.rename(columns={"revenue": "revenue (£)"})
        st.dataframe(top.style.format({"revenue (£)": "£{:,.0f}"}), width="stretch", hide_index=True)
        st.download_button("⬇️ Download all customer segments (CSV)",
                           rfm.reset_index().to_csv(index=False), "customer_segments.csv", "text/csv")

with tab_prod:
    n = st.slider("How many top products to show", 5, 25, 10)
    top_p = (f.groupby("description", observed=True)["revenue"].sum()
               .sort_values(ascending=False).head(n).reset_index().sort_values("revenue"))
    show(px.bar(top_p, x="revenue", y="description", orientation="h",
                title=f"Top {n} products by revenue (£)", height=max(350, 28 * n)))

    st.subheader("Category performance")
    a, b = st.columns(2)
    with a:
        show(px.bar(cat.sort_values("revenue"), x="revenue", y="category", orientation="h",
                    title="Revenue by category (£)"))
    with b:
        show(px.bar(cat.sort_values("revenue_per_product"), x="revenue_per_product", y="category",
                    orientation="h", title="Revenue per product (£): lowest = underperforming"))
    st.caption("'Other' is a catch-all for products that match no keyword, so ignore it when judging "
               "underperformers. Categories are keyword-based approximations.")
    st.dataframe(cat.sort_values("revenue_per_product").rename(
        columns={"revenue": "revenue (£)", "revenue_per_product": "revenue per product (£)"}
    ).style.format({"revenue (£)": "£{:,.0f}", "units": "{:,.0f}", "products": "{:,.0f}",
                    "revenue per product (£)": "£{:,.0f}", "share_%": "{:.1f}"}),
        width="stretch", hide_index=True)

with tab_geo:
    uk_rev = cty.loc[cty["country"] == "United Kingdom", "revenue"].sum()
    st.metric("United Kingdom share of revenue", f"{uk_rev / cty['revenue'].sum():.1%}")
    hide_uk = st.checkbox("Hide the UK on the map (so other countries are visible)", value=True)
    mp = cty[~cty["country"].isin(["Unknown", "European Community", "Channel Islands"])]
    if hide_uk:
        mp = mp[mp["country"] != "United Kingdom"]
    if len(mp):
        show(px.choropleth(mp, locations="country", locationmode="country names", color="revenue",
                           hover_data={"orders": True, "aov": ":.0f"},
                           color_continuous_scale="Blues", title="Revenue by country (£)"))
    a, b = st.columns(2)
    with a:
        top_c = cty[cty["country"] != "United Kingdom"].sort_values("revenue", ascending=False).head(10)
        show(px.bar(top_c.sort_values("revenue"), x="revenue", y="country", orientation="h",
                    title="Top 10 export markets (£, excl. UK)"))
    with b:
        min_orders = st.slider("Minimum orders for the AOV chart", 5, 200, 20)
        big = cty[cty["orders"] >= min_orders].sort_values("aov", ascending=False).head(10)
        show(px.bar(big, x="country", y="aov", title=f"Highest average order value (min {min_orders} orders)"))
    st.dataframe(cty.sort_values("revenue", ascending=False).rename(
        columns={"revenue": "revenue (£)", "aov": "avg order value (£)"}).style.format(
        {"revenue (£)": "£{:,.0f}", "orders": "{:,.0f}", "customers": "{:,.0f}",
         "avg order value (£)": "£{:,.0f}"}), width="stretch", hide_index=True)

with tab_ret:
    st.caption("Returns are invoices that start with 'C' in the raw data. They are filtered by the same "
               "date, market, category and segment choices as the rest of the dashboard.")
    if fr.empty:
        st.info("No refunds in this selection.")
    else:
        c = st.columns(3)
        c[0].metric("Refund value", money(refund_value))
        c[1].metric("Refund lines", f"{len(fr):,}")
        c[2].metric("Refunds / revenue", f"{refund_rate:.1%}")
        a, b = st.columns(2)
        with a:
            rm = fr.groupby("order_month")["refund_value"].sum().reset_index()
            show(px.bar(rm, x="order_month", y="refund_value", title="Refund value by month (£)"))
        with b:
            rp = (fr[fr["is_product"]].groupby("description", observed=True)["refund_value"].sum()
                    .sort_values(ascending=False).head(10).reset_index().sort_values("refund_value"))
            show(px.bar(rp, x="refund_value", y="description", orientation="h",
                        title="Top 10 returned products (£)"))

with tab_data:
    st.subheader("Cleaning log")
    st.caption("Applied once to the full dataset (not affected by the sidebar filters).")
    log = pd.DataFrame({"rows": D["log"]})
    log["rows removed"] = (-log["rows"].diff()).fillna(0).astype(int)
    log.loc["Final clean rows", "rows removed"] = 0
    st.dataframe(log.style.format("{:,.0f}"), width="stretch")
    st.markdown(
        "- Duplicate rows dropped; refund invoices (start with `C`) moved to their own table.\n"
        "- Rows with zero/negative price or quantity, and non-product codes (postage, bank charges, "
        "fees, test items), removed.\n"
        "- Rows with no product description dropped; text trimmed and upper-cased.\n"
        "- Country names standardised (EIRE → Ireland, USA → United States, RSA → South Africa, "
        "Unspecified → Unknown).\n"
        "- Rows with no Customer ID are kept for revenue/product/country figures but are excluded from "
        "customer metrics (repeat rate, cohorts, RFM).")

    st.subheader("Combined data model")
    st.caption("The raw file is one flat table, so these customer, product and location tables are built "
               "from it and joined back by customer ID, stock code and country.")
    t1, t2, t3, t4 = st.tabs(["Orders (fact)", "Customers", "Products", "Locations"])
    with t1:
        st.dataframe(df.drop(columns=["cohort_month"]).head(200), width="stretch", hide_index=True)
        st.caption(f"{len(df):,} order lines. Showing the first 200.")
    with t2:
        st.dataframe(D["customers"].head(200), width="stretch", hide_index=True)
        st.caption(f"{len(D['customers']):,} customers. Showing the first 200.")
    with t3:
        st.dataframe(D["products"].head(200), width="stretch", hide_index=True)
        st.caption(f"{len(D['products']):,} products. Showing the first 200.")
    with t4:
        st.dataframe(D["locations"], width="stretch", hide_index=True)

    st.subheader("Limitations")
    st.markdown(
        "- **No margin:** the dataset has no cost data, so revenue is the money measure.\n"
        "- **Categories are approximate:** built from keywords in product names; about a quarter of "
        "revenue falls into 'Other'.\n"
        "- **Customer metrics cover about 77% of order lines:** the rest are guest orders with no ID.\n"
        "- **Dec 2011 is a partial month.**\n"
        "- Many buyers are wholesalers, so order values are higher than a typical retail shop.")
