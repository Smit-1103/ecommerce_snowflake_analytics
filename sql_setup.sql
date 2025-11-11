-- ============================================================
-- Project setup script: E-commerce Analytics on Snowflake
-- Database: SNOWFLAKE_LEARNING_DB
-- Schema:   SMITCP_LOAD_SAMPLE_DATA_FROM_S3
-- Base table expected: RAW_SALES
-- ============================================================

USE DATABASE SNOWFLAKE_LEARNING_DB;
USE SCHEMA SMITCP_LOAD_SAMPLE_DATA_FROM_S3;

------------------------------------------------------------
-- 1) Cleaned fact table: SALES_CLEANED
------------------------------------------------------------
CREATE OR REPLACE TABLE SALES_CLEANED AS
SELECT
    TRY_TO_NUMBER(INVOICENO)                        AS INVOICE_NO,
    TRY_TO_TIMESTAMP(INVOICEDATE, 'MM/DD/YYYY HH24:MI') AS INVOICE_DATE,
    STOCKCODE,
    DESCRIPTION,
    QUANTITY,
    UNITPRICE,
    TRY_TO_NUMBER(CUSTOMERID)                       AS CUSTOMER_ID,
    COUNTRY,
    (QUANTITY * UNITPRICE)                          AS TOTAL_AMOUNT
FROM RAW_SALES
WHERE QUANTITY > 0
  AND UNITPRICE > 0
  AND CUSTOMERID IS NOT NULL
  AND COUNTRY IS NOT NULL;

------------------------------------------------------------
-- 2) Customer RFM table and segment view (country-aware)
------------------------------------------------------------
CREATE OR REPLACE TABLE CUSTOMER_RFM AS
WITH max_date AS (
    SELECT MAX(INVOICE_DATE) AS max_date
    FROM SALES_CLEANED
),
customer_agg AS (
    SELECT
        CUSTOMER_ID,
        COUNTRY,
        DATEDIFF(
            'day',
            MAX(INVOICE_DATE),
            (SELECT max_date FROM max_date)
        ) AS RECENCY_DAYS,
        COUNT(DISTINCT INVOICE_NO) AS FREQUENCY,
        SUM(TOTAL_AMOUNT) AS MONETARY
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID, COUNTRY
)
SELECT
    *,
    NTILE(5) OVER (ORDER BY -RECENCY_DAYS) AS R_SCORE,
    NTILE(5) OVER (ORDER BY FREQUENCY)      AS F_SCORE,
    NTILE(5) OVER (ORDER BY MONETARY)       AS M_SCORE
FROM customer_agg;

CREATE OR REPLACE VIEW CUSTOMER_SEGMENTS AS
SELECT
    CUSTOMER_ID,
    COUNTRY,
    RECENCY_DAYS,
    FREQUENCY,
    MONETARY,
    R_SCORE,
    F_SCORE,
    M_SCORE,
    CASE
        WHEN R_SCORE >= 4 AND F_SCORE >= 4 AND M_SCORE >= 4 THEN 'Champions'
        WHEN R_SCORE >= 4 AND F_SCORE >= 3 THEN 'Loyal'
        WHEN R_SCORE <= 2 AND M_SCORE <= 2 THEN 'At risk'
        ELSE 'Regular'
    END AS SEGMENT
FROM CUSTOMER_RFM;

------------------------------------------------------------
-- 3) Cohort retention table: COHORT_MONTHLY
--    (country, cohort size, retention rate)
------------------------------------------------------------
CREATE OR REPLACE TABLE COHORT_MONTHLY AS
WITH customer_first AS (
    SELECT
        CUSTOMER_ID,
        COUNTRY,
        DATE_TRUNC('month', MIN(INVOICE_DATE)) AS COHORT_MONTH
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID, COUNTRY
),
customer_month AS (
    SELECT
        s.CUSTOMER_ID,
        s.COUNTRY,
        DATE_TRUNC('month', s.INVOICE_DATE) AS ORDER_MONTH,
        cf.COHORT_MONTH
    FROM SALES_CLEANED s
    JOIN customer_first cf
      ON s.CUSTOMER_ID = cf.CUSTOMER_ID
     AND s.COUNTRY     = cf.COUNTRY
    WHERE DATE_TRUNC('month', s.INVOICE_DATE) >= cf.COHORT_MONTH
),
cohort_base AS (
    SELECT
        COUNTRY,
        COHORT_MONTH,
        DATEDIFF('month', COHORT_MONTH, ORDER_MONTH) AS MONTH_OFFSET,
        COUNT(DISTINCT CUSTOMER_ID) AS ACTIVE_CUSTOMERS
    FROM customer_month
    GROUP BY COUNTRY, COHORT_MONTH, MONTH_OFFSET
),
cohort_size AS (
    SELECT
        COUNTRY,
        COHORT_MONTH,
        ACTIVE_CUSTOMERS AS COHORT_SIZE
    FROM cohort_base
    WHERE MONTH_OFFSET = 0
)
SELECT
    b.COUNTRY,
    b.COHORT_MONTH,
    b.MONTH_OFFSET,
    b.ACTIVE_CUSTOMERS,
    s.COHORT_SIZE,
    ROUND(b.ACTIVE_CUSTOMERS / NULLIF(s.COHORT_SIZE, 0), 4) AS RETENTION_RATE
FROM cohort_base b
JOIN cohort_size s
  ON b.COUNTRY      = s.COUNTRY
 AND b.COHORT_MONTH = s.COHORT_MONTH
ORDER BY b.COUNTRY, b.COHORT_MONTH, b.MONTH_OFFSET;

------------------------------------------------------------
-- 4) Product pairs table with association metrics
--    (support, confidence, lift)
------------------------------------------------------------
CREATE OR REPLACE TABLE PRODUCT_PAIRS AS
WITH invoice_stats AS (
    SELECT COUNT(DISTINCT INVOICE_NO) AS TOTAL_INVOICES
    FROM SALES_CLEANED
),
product_orders AS (
    SELECT
        STOCKCODE,
        COUNT(DISTINCT INVOICE_NO) AS ORDERS_OF_PRODUCT
    FROM SALES_CLEANED
    GROUP BY STOCKCODE
),
base AS (
    SELECT
        a.STOCKCODE AS PRODUCT_A,
        b.STOCKCODE AS PRODUCT_B,
        COUNT(DISTINCT a.INVOICE_NO) AS NUM_ORDERS
    FROM SALES_CLEANED a
    JOIN SALES_CLEANED b
      ON a.INVOICE_NO = b.INVOICE_NO
     AND a.STOCKCODE < b.STOCKCODE
    GROUP BY a.STOCKCODE, b.STOCKCODE
    HAVING COUNT(DISTINCT a.INVOICE_NO) >= 50
),
prod_dim AS (
    SELECT
        STOCKCODE,
        ANY_VALUE(DESCRIPTION) AS DESCRIPTION
    FROM SALES_CLEANED
    GROUP BY STOCKCODE
)
SELECT
    b.PRODUCT_A,
    pa.DESCRIPTION AS PRODUCT_A_NAME,
    b.PRODUCT_B,
    pb.DESCRIPTION AS PRODUCT_B_NAME,
    b.NUM_ORDERS,
    ROUND(b.NUM_ORDERS::FLOAT / i.TOTAL_INVOICES, 4) AS SUPPORT,
    ROUND(b.NUM_ORDERS::FLOAT / ao.ORDERS_OF_PRODUCT, 4) AS CONFIDENCE,
    ROUND(
        (b.NUM_ORDERS::FLOAT / ao.ORDERS_OF_PRODUCT) /
        (bo.ORDERS_OF_PRODUCT::FLOAT / i.TOTAL_INVOICES),
        4
    ) AS LIFT
FROM base b
JOIN invoice_stats i ON 1=1
JOIN product_orders ao ON ao.STOCKCODE = b.PRODUCT_A
JOIN product_orders bo ON bo.STOCKCODE = b.PRODUCT_B
LEFT JOIN prod_dim pa ON b.PRODUCT_A = pa.STOCKCODE
LEFT JOIN prod_dim pb ON b.PRODUCT_B = pb.STOCKCODE;

------------------------------------------------------------
-- 5) Monthly revenue view with moving average and pct change
------------------------------------------------------------
CREATE OR REPLACE VIEW MONTHLY_REVENUE AS
WITH base AS (
    SELECT
        DATE_TRUNC('month', INVOICE_DATE) AS MONTH,
        SUM(TOTAL_AMOUNT) AS TOTAL_REVENUE
    FROM SALES_CLEANED
    GROUP BY 1
),
with_changes AS (
    SELECT
        MONTH,
        TOTAL_REVENUE,
        LAG(TOTAL_REVENUE) OVER (ORDER BY MONTH) AS PREV_REVENUE,
        AVG(TOTAL_REVENUE) OVER (
            ORDER BY MONTH
            ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
        ) AS MOVING_AVG
    FROM base
)
SELECT
    MONTH,
    ROUND(TOTAL_REVENUE, 2) AS TOTAL_REVENUE,
    ROUND(MOVING_AVG, 2)    AS MOVING_AVG,
    ROUND(
        CASE
            WHEN PREV_REVENUE IS NULL OR PREV_REVENUE = 0
                THEN NULL
            ELSE (TOTAL_REVENUE - PREV_REVENUE) / PREV_REVENUE * 100
        END,
        2
    ) AS PCT_CHANGE
FROM with_changes
ORDER BY MONTH;

------------------------------------------------------------
-- 6) Profit estimation view
------------------------------------------------------------
CREATE OR REPLACE VIEW SALES_PROFIT AS
SELECT
    INVOICE_NO,
    INVOICE_DATE,
    STOCKCODE,
    DESCRIPTION,
    QUANTITY,
    UNITPRICE,
    CUSTOMER_ID,
    COUNTRY,
    TOTAL_AMOUNT,
    TOTAL_AMOUNT * 0.35 AS EST_PROFIT
FROM SALES_CLEANED;

------------------------------------------------------------
-- 7) Data quality metrics view (counts + percentages)
------------------------------------------------------------
CREATE OR REPLACE VIEW DATA_QUALITY_METRICS AS
WITH raw AS (
    SELECT COUNT(*) AS ROWS_RAW
    FROM RAW_SALES
),
clean AS (
    SELECT COUNT(*) AS ROWS_CLEAN
    FROM SALES_CLEANED
),
issues AS (
    SELECT
        SUM(CASE WHEN QUANTITY <= 0 THEN 1 ELSE 0 END)      AS BAD_QUANTITY,
        SUM(CASE WHEN UNITPRICE <= 0 THEN 1 ELSE 0 END)     AS BAD_PRICE,
        SUM(CASE WHEN CUSTOMERID IS NULL THEN 1 ELSE 0 END) AS MISSING_CUSTOMER,
        SUM(CASE WHEN INVOICENO IS NULL THEN 1 ELSE 0 END)  AS MISSING_INVOICE
    FROM RAW_SALES
)
SELECT
    r.ROWS_RAW,
    c.ROWS_CLEAN,
    i.BAD_QUANTITY,
    i.BAD_PRICE,
    i.MISSING_CUSTOMER,
    i.MISSING_INVOICE,
    ROUND(i.BAD_QUANTITY::FLOAT      / r.ROWS_RAW, 4) AS BAD_QUANTITY_PCT,
    ROUND(i.BAD_PRICE::FLOAT         / r.ROWS_RAW, 4) AS BAD_PRICE_PCT,
    ROUND(i.MISSING_CUSTOMER::FLOAT  / r.ROWS_RAW, 4) AS MISSING_CUSTOMER_PCT,
    ROUND(i.MISSING_INVOICE::FLOAT   / r.ROWS_RAW, 4) AS MISSING_INVOICE_PCT
FROM raw r, clean c, issues i;

------------------------------------------------------------
-- 8) Customer value / churn risk view
------------------------------------------------------------
CREATE OR REPLACE VIEW CUSTOMER_VALUE AS
WITH max_date AS (
    SELECT MAX(INVOICE_DATE) AS MAX_INVOICE_DATE
    FROM SALES_CLEANED
),
base AS (
    SELECT
        CUSTOMER_ID,
        COUNTRY,
        MIN(INVOICE_DATE) AS FIRST_PURCHASE,
        MAX(INVOICE_DATE) AS LAST_PURCHASE,
        DATEDIFF('day', MIN(INVOICE_DATE), MAX(INVOICE_DATE)) AS ACTIVE_DAYS,
        COUNT(DISTINCT INVOICE_NO) AS TOTAL_ORDERS,
        SUM(TOTAL_AMOUNT) AS TOTAL_REVENUE
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID, COUNTRY
),
scored AS (
    SELECT
        b.*,
        DATEDIFF(
            'day',
            b.LAST_PURCHASE,
            (SELECT MAX_INVOICE_DATE FROM max_date)
        ) AS RECENCY_DAYS,
        ROUND(TOTAL_REVENUE / NULLIF(TOTAL_ORDERS, 0), 2) AS AVG_SPEND_PER_ORDER,
        ROUND(
            CASE
                WHEN ACTIVE_DAYS <= 0 THEN TOTAL_REVENUE
                ELSE (TOTAL_REVENUE / ACTIVE_DAYS) * 30
            END,
            2
        ) AS REVENUE_PER_MONTH,
        ROUND(
            CASE
                WHEN ACTIVE_DAYS <= 0 THEN TOTAL_REVENUE
                ELSE (TOTAL_REVENUE / ACTIVE_DAYS) * 365
            END,
            2
        ) AS ESTIMATED_CLV,
        CASE
            WHEN RECENCY_DAYS <= 30 THEN 'Active'
            WHEN RECENCY_DAYS BETWEEN 31 AND 90 THEN 'At Risk'
            WHEN RECENCY_DAYS > 90 THEN 'Dormant'
        END AS LIFECYCLE_STAGE
    FROM base b
)
SELECT * FROM scored;
