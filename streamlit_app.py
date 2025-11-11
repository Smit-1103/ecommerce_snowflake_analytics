import streamlit as st
import pandas as pd
import snowflake.connector

# -------------------------------------------------
# E-COMMERCE SALES INTELLIGENCE DASHBOARD
# Backend objects required in Snowflake:
#   SALES_CLEANED
#   CUSTOMER_SEGMENTS
#   COHORT_MONTHLY
#   PRODUCT_PAIRS
#   SALES_PROFIT
#   DATA_QUALITY_METRICS
#   CUSTOMER_VALUE
# -------------------------------------------------

st.title("E-Commerce Sales Intelligence Dashboard")

# =======================
# Snowflake connection helpers
# =======================

@st.cache_resource
def get_connection():
    cfg = st.secrets["snowflake"]
    conn = snowflake.connector.connect(
        user=cfg["user"],
        password=cfg["password"],
        account=cfg["account"],
        warehouse=cfg["warehouse"],
        database=cfg["database"],
        schema=cfg["schema"],
    )
    return conn

@st.cache_data(show_spinner=False)
def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return cur.fetch_pandas_all()
    finally:
        cur.close()

# =======================
# Sidebar filters
# =======================

meta = run_query("""
    SELECT MIN(INVOICE_DATE) AS MIN_DATE,
           MAX(INVOICE_DATE) AS MAX_DATE
    FROM SALES_CLEANED;
""").iloc[0]

st.sidebar.header("Filters")

# Date range filter
start_date, end_date = st.sidebar.date_input(
    "Invoice date range",
    value=(meta["MIN_DATE"].date(), meta["MAX_DATE"].date()),
    min_value=meta["MIN_DATE"].date(),
    max_value=meta["MAX_DATE"].date()
)

# Country filter
countries_df = run_query("""
    SELECT DISTINCT COUNTRY
    FROM SALES_CLEANED
    ORDER BY COUNTRY;
""")
all_countries = countries_df["COUNTRY"].tolist()

selected_countries = st.sidebar.multiselect(
    "Countries",
    options=all_countries,
    default=[]
)

# WHERE clause for filtered fact queries
where_clause = (
    f"WHERE INVOICE_DATE::DATE BETWEEN '{start_date}' AND '{end_date}'"
)
if selected_countries:
    countries_str = "', '".join(selected_countries)
    where_clause += f" AND COUNTRY IN ('{countries_str}')"

# =======================
# Tabs
# =======================

(
    tab_overview,
    tab_countries,
    tab_products,
    tab_customers,
    tab_rfm,
    tab_cohort,
    tab_pairs,
    tab_quality,
    tab_value
) = st.tabs(
    [
        "Overview",
        "Countries",
        "Products",
        "Customers",
        "RFM Segments",
        "Cohorts",
        "Product Pairs",
        "Data Quality",
        "Customer Value"
    ]
)

# =======================
# Overview tab
# =======================
with tab_overview:
    # Monthly revenue with moving average and anomalies
    monthly = run_query(f"""
        SELECT DATE_TRUNC('month', INVOICE_DATE) AS MONTH,
               ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY 1
        ORDER BY 1;
    """)

    if not monthly.empty:
        monthly = monthly.sort_values("MONTH")
        monthly["MOVING_AVG"] = monthly["TOTAL_REVENUE"].rolling(3).mean()
        monthly["PCT_CHANGE"] = monthly["TOTAL_REVENUE"].pct_change() * 100

    # KPI block
    kpis = run_query(f"""
        SELECT
            ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE,
            COUNT(DISTINCT INVOICE_NO)  AS NUM_ORDERS,
            COUNT(DISTINCT CUSTOMER_ID) AS NUM_CUSTOMERS
        FROM SALES_CLEANED
        {where_clause};
    """).iloc[0]

    st.markdown("### 📊 Executive Summary")

    col1, col2, col3 = st.columns(3)
    col1.metric("Total revenue", f"{kpis['TOTAL_REVENUE']:,.2f}")
    col2.metric("Orders", int(kpis["NUM_ORDERS"]))
    col3.metric("Customers", int(kpis["NUM_CUSTOMERS"]))

    if not monthly.empty and len(monthly) >= 2:
        latest = monthly.iloc[-1]["TOTAL_REVENUE"]
        prev = monthly.iloc[-2]["TOTAL_REVENUE"]
        if prev != 0:
            growth = (latest - prev) / prev * 100
        else:
            growth = 0.0
        st.markdown(
            f"- **Latest month revenue:** {latest:,.2f}  \n"
            f"- **Month-over-month growth:** {growth:.1f}%"
        )

    st.subheader("📈 Monthly Revenue vs 3-Month Moving Average")
    if not monthly.empty:
        st.line_chart(
            monthly,
            x="MONTH",
            y=["TOTAL_REVENUE", "MOVING_AVG"]
        )
    else:
        st.info("No data for the selected filters.")

    # Anomaly detection
    if not monthly.empty and "PCT_CHANGE" in monthly.columns:
        anomalies = monthly[monthly["PCT_CHANGE"] < -20]
        if not anomalies.empty:
            st.warning(
                f"Revenue dropped more than 20% in {len(anomalies)} month(s)."
            )
            st.dataframe(
                anomalies[["MONTH", "TOTAL_REVENUE", "PCT_CHANGE"]]
            )

    # Estimated profit chart using SALES_PROFIT
    st.subheader("💹 Estimated Monthly Profit (35% of revenue)")
    profit = run_query(f"""
        SELECT DATE_TRUNC('month', INVOICE_DATE) AS MONTH,
               SUM(EST_PROFIT) AS PROFIT
        FROM SALES_PROFIT
        {where_clause}
        GROUP BY 1
        ORDER BY 1;
    """)
    if not profit.empty:
        st.line_chart(profit, x="MONTH", y="PROFIT")
    else:
        st.info("No profit data for the selected filters.")

    # Revenue by weekday
    st.subheader("🗓️ Revenue by Weekday")
    weekday = run_query(f"""
        SELECT TO_VARCHAR(DAYNAME(INVOICE_DATE)) AS WEEKDAY,
               ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY WEEKDAY
        ORDER BY TOTAL_REVENUE DESC;
    """)
    if not weekday.empty:
        st.bar_chart(weekday, x="WEEKDAY", y="TOTAL_REVENUE")
    else:
        st.info("No weekday breakdown for the selected filters.")

# =======================
# Countries tab
# =======================
with tab_countries:
    st.subheader("🌍 Revenue by Country")

    country_rev = run_query(f"""
        SELECT COUNTRY,
               ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY COUNTRY
        ORDER BY TOTAL_REVENUE DESC
        LIMIT 25;
    """)
    if not country_rev.empty:
        st.bar_chart(country_rev, x="COUNTRY", y="TOTAL_REVENUE")
        st.dataframe(country_rev)
    else:
        st.info("No country-level data for the selected filters.")

# =======================
# Products tab
# =======================
with tab_products:
    st.subheader("🏆 Top 10 Products (by revenue)")

    top_products = run_query(f"""
        SELECT DESCRIPTION,
               ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY DESCRIPTION
        ORDER BY TOTAL_REVENUE DESC
        LIMIT 10;
    """)
    if not top_products.empty:
        st.bar_chart(top_products, x="DESCRIPTION", y="TOTAL_REVENUE")
        st.dataframe(top_products)
    else:
        st.info("No product data for the selected filters.")

# =======================
# Customers tab
# =======================
with tab_customers:
    st.subheader("💰 Top 10 Customers")

    customers = run_query(f"""
        SELECT CUSTOMER_ID,
               ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_SPENT,
               COUNT(DISTINCT INVOICE_NO) AS ORDERS
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY CUSTOMER_ID
        ORDER BY TOTAL_SPENT DESC
        LIMIT 10;
    """)

    if not customers.empty:
        customers["CUSTOMER_LABEL"] = (
            "Customer " + customers["CUSTOMER_ID"].astype(str)
        )

        st.bar_chart(
            customers,
            x="CUSTOMER_LABEL",
            y="TOTAL_SPENT"
        )

        st.dataframe(
            customers[["CUSTOMER_LABEL", "TOTAL_SPENT", "ORDERS"]]
            .rename(
                columns={
                    "CUSTOMER_LABEL": "Customer",
                    "TOTAL_SPENT": "Total spent",
                    "ORDERS": "Orders"
                }
            )
        )
    else:
        st.info("No customer data for the selected filters.")

# =======================
# RFM Segments tab
# =======================
with tab_rfm:
    st.subheader("📊 RFM Customer Segments")

    seg = run_query("SELECT * FROM CUSTOMER_SEGMENTS;")

    if not seg.empty:
        seg_counts = (
            seg.groupby("SEGMENT")["CUSTOMER_ID"]
            .count()
            .reset_index(name="CUSTOMERS")
        )
        st.bar_chart(seg_counts, x="SEGMENT", y="CUSTOMERS")

        selected_segment = st.selectbox(
            "Inspect segment",
            sorted(seg["SEGMENT"].unique())
        )
        st.dataframe(
            seg[seg["SEGMENT"] == selected_segment].head(100)
        )
    else:
        st.info("No RFM segment data. Check CUSTOMER_SEGMENTS view.")

# =======================
# Cohorts tab
# =======================
with tab_cohort:
    st.subheader("🧩 Cohort Retention (customers by month offset)")

    cohort = run_query("SELECT * FROM COHORT_MONTHLY;")
    if not cohort.empty:
        pivot = cohort.pivot_table(
            index="COHORT_MONTH",
            columns="MONTH_OFFSET",
            values="ACTIVE_CUSTOMERS",
            fill_value=0
        )
        st.dataframe(pivot)
    else:
        st.info("COHORT_MONTHLY table is empty or not created.")

# =======================
# Product pairs tab
# =======================
with tab_pairs:
    st.subheader("🔗 Frequently Bought Together (top pairs)")

    pairs = run_query("""
        SELECT PRODUCT_A_NAME, PRODUCT_B_NAME, NUM_ORDERS
        FROM PRODUCT_PAIRS
        ORDER BY NUM_ORDERS DESC
        LIMIT 100;
    """)

    if not pairs.empty:
        pairs_display = pairs.rename(
            columns={
                "PRODUCT_A_NAME": "Product A",
                "PRODUCT_B_NAME": "Product B",
                "NUM_ORDERS": "Orders together"
            }
        )
        st.dataframe(pairs_display)
    else:
        st.info("No product pair data. Check PRODUCT_PAIRS table.")

# =======================
# Data Quality tab
# =======================
with tab_quality:
    st.subheader("🧪 Data Quality Metrics")

    dq = run_query("SELECT * FROM DATA_QUALITY_METRICS;")
    if not dq.empty:
        row = dq.iloc[0]
        col1, col2 = st.columns(2)
        col1.metric("Rows in RAW_SALES", int(row["ROWS_RAW"]))
        col2.metric("Rows in SALES_CLEANED", int(row["ROWS_CLEAN"]))

        st.markdown("#### Issues in RAW_SALES")
        st.write(
            {
                "Bad quantity rows": int(row["BAD_QUANTITY"]),
                "Bad price rows": int(row["BAD_PRICE"]),
                "Missing customer ID": int(row["MISSING_CUSTOMER"]),
                "Missing invoice number": int(row["MISSING_INVOICE"]),
            }
        )
    else:
        st.info("DATA_QUALITY_METRICS view is empty or missing.")

# =======================
# Customer Value tab
# =======================
with tab_value:
    st.subheader("💎 Customer Lifetime Value and Churn Risk")

    val = run_query("SELECT * FROM CUSTOMER_VALUE;")

    if not val.empty:
        # distribution by lifecycle stage
        stage_counts = (
            val.groupby("LIFECYCLE_STAGE")["CUSTOMER_ID"]
            .count()
            .reset_index(name="CUSTOMERS")
        )
        st.bar_chart(
            stage_counts,
            x="LIFECYCLE_STAGE",
            y="CUSTOMERS"
        )

        # top high value customers
        st.markdown("#### Top high value customers")
        top_val = (
            val.sort_values("TOTAL_REVENUE", ascending=False)
            .head(50)
            .copy()
        )
        top_val["CUSTOMER_LABEL"] = (
            "Customer " + top_val["CUSTOMER_ID"].astype(str)
        )
        st.dataframe(
            top_val[
                [
                    "CUSTOMER_LABEL",
                    "TOTAL_REVENUE",
                    "TOTAL_ORDERS",
                    "REVENUE_PER_MONTH",
                    "LIFECYCLE_STAGE"
                ]
            ].rename(
                columns={
                    "CUSTOMER_LABEL": "Customer",
                    "TOTAL_REVENUE": "Total revenue",
                    "TOTAL_ORDERS": "Orders",
                    "REVENUE_PER_MONTH": "Revenue per month"
                }
            )
        )
    else:
        st.info("CUSTOMER_VALUE view is empty or missing.")

st.caption(
    "Backend: Snowflake | Frontend: Streamlit Community Cloud | "
    "Dataset: Online Retail transactions (demo project)"
)
