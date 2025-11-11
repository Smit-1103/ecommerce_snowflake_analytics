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
        # add role here if you store it in secrets:
        # role=cfg["role"],
    )
    return conn


@st.cache_data(show_spinner=False, ttl=600)
def run_query(sql: str) -> pd.DataFrame:
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql)
        return cur.fetch_pandas_all()
    finally:
        cur.close()


def show_table(df: pd.DataFrame, label: str = "Show underlying data", max_rows: int = 200):
    """Show a dataframe only when user expands it."""
    if df is None or df.empty:
        return
    with st.expander(label):
        st.dataframe(df.head(max_rows))


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
    default=all_countries,   # all by default
)

# WHERE clause for filtered fact queries (date + country)
where_clause = (
    f"WHERE INVOICE_DATE::DATE BETWEEN '{start_date}' AND '{end_date}'"
)
if selected_countries:
    countries_str = "', '".join(selected_countries)
    where_clause += f" AND COUNTRY IN ('{countries_str}')"


# Helper to build country-only WHERE clause for aggregated tables/views
def country_where_clause(column_name: str = "COUNTRY") -> str:
    if not selected_countries:
        return ""
    countries_str = "', '".join(selected_countries)
    return f" WHERE {column_name} IN ('{countries_str}')"


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
        "Executive Dashboard",
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
# Executive Dashboard tab
# =======================
with tab_overview:
    st.markdown("### 📊 Executive Summary")

    # Core KPIs
    kpis = run_query(f"""
        SELECT
            ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE,
            COUNT(DISTINCT INVOICE_NO)  AS NUM_ORDERS,
            COUNT(DISTINCT CUSTOMER_ID) AS NUM_CUSTOMERS
        FROM SALES_CLEANED
        {where_clause};
    """).iloc[0]

    # Repeat purchase rate (customers with >= 2 orders in the filtered window)
    repeat_df = run_query(f"""
        SELECT CUSTOMER_ID,
               COUNT(DISTINCT INVOICE_NO) AS NUM_ORDERS
        FROM SALES_CLEANED
        {where_clause}
        GROUP BY CUSTOMER_ID;
    """)

    repeat_rate_display = "N/A"
    if not repeat_df.empty:
        total_customers_rep = len(repeat_df)
        repeat_customers = (repeat_df["NUM_ORDERS"] >= 2).sum()
        repeat_rate = (repeat_customers / total_customers_rep) * 100
        repeat_rate_display = f"{repeat_rate:.1f}%"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total revenue", f"{kpis['TOTAL_REVENUE']:,.2f}")
    col2.metric("Orders", int(kpis["NUM_ORDERS"]))
    col3.metric("Customers", int(kpis["NUM_CUSTOMERS"]))
    col4.metric("Repeat purchase rate", repeat_rate_display)

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
        # Decimal -> float for stats
        monthly["TOTAL_REVENUE"] = monthly["TOTAL_REVENUE"].astype("float64")
        monthly["MOVING_AVG"] = monthly["TOTAL_REVENUE"].rolling(3).mean()
        monthly["PCT_CHANGE"] = monthly["TOTAL_REVENUE"].pct_change() * 100

        # Z-score anomalies
        std_rev = monthly["TOTAL_REVENUE"].std(ddof=0)
        if pd.notna(std_rev) and std_rev != 0:
            mean_rev = monthly["TOTAL_REVENUE"].mean()
            monthly["Z_SCORE"] = (monthly["TOTAL_REVENUE"] - mean_rev) / std_rev
        else:
            monthly["Z_SCORE"] = 0.0

    if not monthly.empty and len(monthly) >= 2:
        latest = monthly.iloc[-1]["TOTAL_REVENUE"]
        prev = monthly.iloc[-2]["TOTAL_REVENUE"]
        growth = (latest - prev) / prev * 100 if prev != 0 else 0.0
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

        anomalies_z = monthly[monthly["Z_SCORE"].abs() > 2.5]
        if not anomalies_z.empty:
            st.warning(
                f"Revenue outliers detected in {len(anomalies_z)} month(s) "
                "(|z-score| > 2.5)."
            )
            show_table(
                anomalies_z[["MONTH", "TOTAL_REVENUE", "Z_SCORE"]],
                label="See anomaly details (z-score)"
            )
    else:
        st.info("No data for the selected filters.")

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
        show_table(weekday, label="Show weekday table")
    else:
        st.info("No weekday breakdown for the selected filters.")

    # Monthly new vs returning customers
    st.subheader("👥 Monthly New vs Returning Customers")

    country_filter_clause = country_where_clause("COUNTRY")

    monthly_customers = run_query(f"""
        WITH first_purchase AS (
            SELECT
                CUSTOMER_ID,
                MIN(INVOICE_DATE::DATE) AS FIRST_DATE
            FROM SALES_CLEANED
            {country_filter_clause}
            GROUP BY CUSTOMER_ID
        ),
        activity AS (
            SELECT
                DATE_TRUNC('month', s.INVOICE_DATE) AS MONTH,
                s.CUSTOMER_ID,
                CASE
                    WHEN s.INVOICE_DATE::DATE = f.FIRST_DATE THEN 1
                    ELSE 0
                END AS IS_NEW
            FROM SALES_CLEANED s
            JOIN first_purchase f
              ON s.CUSTOMER_ID = f.CUSTOMER_ID
            {where_clause}
        )
        SELECT
            MONTH,
            COUNT(DISTINCT CASE WHEN IS_NEW = 1 THEN CUSTOMER_ID END) AS NEW_CUSTOMERS,
            COUNT(DISTINCT CASE WHEN IS_NEW = 0 THEN CUSTOMER_ID END) AS RETURNING_CUSTOMERS
        FROM activity
        GROUP BY MONTH
        ORDER BY MONTH;
    """)

    if not monthly_customers.empty:
        st.area_chart(
            monthly_customers,
            x="MONTH",
            y=["NEW_CUSTOMERS", "RETURNING_CUSTOMERS"]
        )
        show_table(
            monthly_customers,
            label="Show new vs returning customers table"
        )
    else:
        st.info("No customer activity for the selected filters.")

    # Basket size trend (avg items per order)
    st.subheader("🧺 Average Items per Order (Basket Size)")

    basket = run_query(f"""
        WITH order_items AS (
            SELECT
                DATE_TRUNC('month', INVOICE_DATE) AS MONTH,
                INVOICE_NO,
                SUM(QUANTITY) AS ITEMS
            FROM SALES_CLEANED
            {where_clause}
            GROUP BY 1, 2
        )
        SELECT
            MONTH,
            AVG(ITEMS) AS AVG_ITEMS_PER_ORDER
        FROM order_items
        GROUP BY MONTH
        ORDER BY MONTH;
    """)

    if not basket.empty:
        st.line_chart(basket, x="MONTH", y="AVG_ITEMS_PER_ORDER")
        show_table(
            basket,
            label="Show basket size table"
        )
    else:
        st.info("No basket-size data for the selected filters.")

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
        show_table(country_rev, label="Show country table")
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
        show_table(top_products, label="Show product table")
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

        show_table(
            customers[["CUSTOMER_LABEL", "TOTAL_SPENT", "ORDERS"]]
            .rename(
                columns={
                    "CUSTOMER_LABEL": "Customer",
                    "TOTAL_SPENT": "Total spent",
                    "ORDERS": "Orders"
                }
            ),
            label="Show top customers table"
        )
    else:
        st.info("No customer data for the selected filters.")

# =======================
# RFM Segments tab
# =======================
with tab_rfm:
    st.subheader("📊 RFM Customer Segments")
    st.caption(
        "RFM scores are computed on full order history and filtered by country only."
    )

    seg_query = "SELECT * FROM CUSTOMER_SEGMENTS"
    seg_query += country_where_clause("COUNTRY")
    seg = run_query(seg_query)

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
        show_table(
            seg[seg["SEGMENT"] == selected_segment],
            label=f"Show customers in segment: {selected_segment}"
        )
    else:
        st.info("No RFM segment data for the selected filters.")

# =======================
# Cohorts tab
# =======================
with tab_cohort:
    st.subheader("🧩 Cohort Retention")
    st.caption(
        "Retention rate = % of customers who purchased again in later months "
        "after their first purchase."
    )

    cohort_query = "SELECT * FROM COHORT_MONTHLY"
    cohort_query += country_where_clause("COUNTRY")
    cohort = run_query(cohort_query)

    if not cohort.empty:
        index_cols = ["COHORT_MONTH"]
        if selected_countries:
            index_cols = ["COUNTRY", "COHORT_MONTH"]

        pivot = cohort.pivot_table(
            index=index_cols,
            columns="MONTH_OFFSET",
            values="RETENTION_RATE",
            fill_value=0.0
        )
        with st.expander("Show cohort retention table"):
            st.dataframe(pivot.style.format("{:.2%}"))
    else:
        st.info("No cohort data for the selected filters.")

# =======================
# Product pairs tab
# =======================
with tab_pairs:
    st.subheader("🔗 Frequently Bought Together (top pairs)")
    st.caption(
        "Association metrics are computed on full history; "
        "country/date filters do not apply."
    )

    pairs = run_query("""
        SELECT
            PRODUCT_A_NAME,
            PRODUCT_B_NAME,
            NUM_ORDERS,
            SUPPORT,
            CONFIDENCE,
            LIFT
        FROM PRODUCT_PAIRS
        ORDER BY LIFT DESC
        LIMIT 100;
    """)

    if not pairs.empty:
        pairs_display = pairs.rename(
            columns={
                "PRODUCT_A_NAME": "Product A",
                "PRODUCT_B_NAME": "Product B",
                "NUM_ORDERS": "Orders together",
                "SUPPORT": "Support",
                "CONFIDENCE": "Confidence",
                "LIFT": "Lift"
            }
        )
        show_table(pairs_display, label="Show product pair details")
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

        issues_df = pd.DataFrame(
            [
                {
                    "Issue": "Bad quantity rows",
                    "Count": int(row["BAD_QUANTITY"]),
                    "Percent of RAW_SALES": float(row["BAD_QUANTITY_PCT"]),
                },
                {
                    "Issue": "Bad price rows",
                    "Count": int(row["BAD_PRICE"]),
                    "Percent of RAW_SALES": float(row["BAD_PRICE_PCT"]),
                },
                {
                    "Issue": "Missing customer ID",
                    "Count": int(row["MISSING_CUSTOMER"]),
                    "Percent of RAW_SALES": float(row["MISSING_CUSTOMER_PCT"]),
                },
                {
                    "Issue": "Missing invoice number",
                    "Count": int(row["MISSING_INVOICE"]),
                    "Percent of RAW_SALES": float(row["MISSING_INVOICE_PCT"]),
                },
            ]
        )
        issues_df["Percent of RAW_SALES"] = issues_df[
            "Percent of RAW_SALES"
        ].map(lambda x: f"{x*100:.2f}%")

        show_table(issues_df, label="Show detailed issue counts")
    else:
        st.info("DATA_QUALITY_METRICS view is empty or missing.")

# =======================
# Customer Value tab
# =======================
with tab_value:
    st.subheader("💎 Customer Lifetime Value and Churn Risk")
    st.caption(
        "Customer value metrics are computed on full history, "
        "filtered by country if selected."
    )

    val_query = "SELECT * FROM CUSTOMER_VALUE"
    val_query += country_where_clause("COUNTRY")
    val = run_query(val_query)

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

        st.markdown("#### Top high value customers (by CLV)")
        top_val = (
            val.sort_values("ESTIMATED_CLV", ascending=False)
            .head(50)
            .copy()
        )
        top_val["CUSTOMER_LABEL"] = (
            "Customer " + top_val["CUSTOMER_ID"].astype(str)
        )
        show_table(
            top_val[
                [
                    "CUSTOMER_LABEL",
                    "TOTAL_REVENUE",
                    "TOTAL_ORDERS",
                    "REVENUE_PER_MONTH",
                    "ESTIMATED_CLV",
                    "RECENCY_DAYS",
                    "LIFECYCLE_STAGE"
                ]
            ].rename(
                columns={
                    "CUSTOMER_LABEL": "Customer",
                    "TOTAL_REVENUE": "Total revenue",
                    "TOTAL_ORDERS": "Orders",
                    "REVENUE_PER_MONTH": "Revenue per month",
                    "ESTIMATED_CLV": "Estimated CLV (1 year)",
                    "RECENCY_DAYS": "Recency (days)"
                }
            ),
            label="Show high value customer table"
        )
    else:
        st.info("CUSTOMER_VALUE view is empty or missing.")

st.caption(
    "Backend: Snowflake | Frontend: Streamlit | "
    "Dataset: Online Retail transactions (demo project)"
)
