-- ============================================================
-- Project setup script: E-commerce Analytics on Snowflake
-- Database: SNOWFLAKE_LEARNING_DB
-- Schema:   SMITCP_LOAD_SAMPLE_DATA_FROM_S3
-- ============================================================

USE DATABASE SNOWFLAKE_LEARNING_DB;
USE SCHEMA SMITCP_LOAD_SAMPLE_DATA_FROM_S3;

------------------------------------------------------------
-- 1) Cleaned fact table: SALES_CLEANED
------------------------------------------------------------
CREATE OR REPLACE TABLE SALES_CLEANED AS
SELECT
    TRY_TO_NUMBER(INVOICENO) AS INVOICE_NO,
    TRY_TO_TIMESTAMP(INVOICEDATE, 'MM/DD/YYYY HH24:MI') AS INVOICE_DATE,
    STOCKCODE,
    DESCRIPTION,
    QUANTITY,
    UNITPRICE,
    TRY_TO_NUMBER(CUSTOMERID) AS CUSTOMER_ID,
    COUNTRY,
    (QUANTITY * UNITPRICE) AS TOTAL_AMOUNT
FROM RAW_SALES
WHERE QUANTITY > 0
  AND UNITPRICE > 0
  AND CUSTOMERID IS NOT NULL
  AND COUNTRY IS NOT NULL;

------------------------------------------------------------
-- 2) Customer RFM table and segment view
------------------------------------------------------------
CREATE OR REPLACE TABLE CUSTOMER_RFM AS
WITH max_date AS (
    SELECT MAX(INVOICE_DATE) AS max_date
    FROM SALES_CLEANED
),
customer_agg AS (
    SELECT
        CUSTOMER_ID,
        DATEDIFF(
            'day',
            MAX(INVOICE_DATE),
            (SELECT max_date FROM max_date)
        ) AS RECENCY_DAYS,                -- days since last order
        COUNT(DISTINCT INVOICE_NO) AS FREQUENCY,
        SUM(TOTAL_AMOUNT) AS MONETARY
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID
)
SELECT
    *,
    NTILE(5) OVER (ORDER BY -RECENCY_DAYS) AS R_SCORE,  -- recent = high score
    NTILE(5) OVER (ORDER BY FREQUENCY)      AS F_SCORE,
    NTILE(5) OVER (ORDER BY MONETARY)       AS M_SCORE
FROM customer_agg;

CREATE OR REPLACE VIEW CUSTOMER_SEGMENTS AS
SELECT
    CUSTOMER_ID,
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
------------------------------------------------------------
CREATE OR REPLACE TABLE COHORT_MONTHLY AS
WITH customer_first AS (
    SELECT
        CUSTOMER_ID,
        DATE_TRUNC('month', MIN(INVOICE_DATE)) AS COHORT_MONTH
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID
),
customer_month AS (
    SELECT
        s.CUSTOMER_ID,
        DATE_TRUNC('month', s.INVOICE_DATE) AS ORDER_MONTH,
        cf.COHORT_MONTH
    FROM SALES_CLEANED s
    JOIN customer_first cf
      ON s.CUSTOMER_ID = cf.CUSTOMER_ID
),
cohort_retention AS (
    SELECT
        COHORT_MONTH,
        DATEDIFF('month', COHORT_MONTH, ORDER_MONTH) AS MONTH_OFFSET,
        COUNT(DISTINCT CUSTOMER_ID) AS ACTIVE_CUSTOMERS
    FROM customer_month
    GROUP BY COHORT_MONTH, MONTH_OFFSET
)
SELECT * FROM cohort_retention;

------------------------------------------------------------
-- 4) Product pairs table with readable product names
------------------------------------------------------------
CREATE OR REPLACE TABLE PRODUCT_PAIRS AS
WITH base AS (
    SELECT
        a.STOCKCODE AS PRODUCT_A,
        b.STOCKCODE AS PRODUCT_B,
        COUNT(DISTINCT a.INVOICE_NO) AS NUM_ORDERS
    FROM SALES_CLEANED a
    JOIN SALES_CLEANED b
      ON a.INVOICE_NO = b.INVOICE_NO
     AND a.STOCKCODE < b.STOCKCODE         -- avoid duplicate pairs
    GROUP BY PRODUCT_A, PRODUCT_B
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
    base.PRODUCT_A,
    pa.DESCRIPTION AS PRODUCT_A_NAME,
    base.PRODUCT_B,
    pb.DESCRIPTION AS PRODUCT_B_NAME,
    base.NUM_ORDERS
FROM base
LEFT JOIN prod_dim pa ON base.PRODUCT_A = pa.STOCKCODE
LEFT JOIN prod_dim pb ON base.PRODUCT_B = pb.STOCKCODE;

------------------------------------------------------------
-- 5) Monthly revenue view (unfiltered, reference)
------------------------------------------------------------
CREATE OR REPLACE VIEW MONTHLY_REVENUE AS
SELECT
    DATE_TRUNC('month', INVOICE_DATE) AS MONTH,
    ROUND(SUM(TOTAL_AMOUNT), 2) AS TOTAL_REVENUE
FROM SALES_CLEANED
GROUP BY 1
ORDER BY 1;

------------------------------------------------------------
-- 6) Profit estimation view
-- Assumes 35% of revenue is profit (simple model)
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
-- 7) Data quality metrics view
------------------------------------------------------------
CREATE OR REPLACE VIEW DATA_QUALITY_METRICS AS
SELECT
    (SELECT COUNT(*) FROM RAW_SALES)          AS ROWS_RAW,
    (SELECT COUNT(*) FROM SALES_CLEANED)      AS ROWS_CLEAN,
    SUM(CASE WHEN QUANTITY <= 0 THEN 1 ELSE 0 END)          AS BAD_QUANTITY,
    SUM(CASE WHEN UNITPRICE <= 0 THEN 1 ELSE 0 END)         AS BAD_PRICE,
    SUM(CASE WHEN CUSTOMERID IS NULL THEN 1 ELSE 0 END)     AS MISSING_CUSTOMER,
    SUM(CASE WHEN INVOICENO IS NULL THEN 1 ELSE 0 END)      AS MISSING_INVOICE
FROM RAW_SALES;

------------------------------------------------------------
-- 8) Customer value / churn risk view
------------------------------------------------------------
CREATE OR REPLACE VIEW CUSTOMER_VALUE AS
WITH base AS (
    SELECT
        CUSTOMER_ID,
        MIN(INVOICE_DATE) AS FIRST_PURCHASE,
        MAX(INVOICE_DATE) AS LAST_PURCHASE,
        DATEDIFF('day', MIN(INVOICE_DATE), MAX(INVOICE_DATE)) AS ACTIVE_DAYS,
        COUNT(DISTINCT INVOICE_NO) AS TOTAL_ORDERS,
        SUM(TOTAL_AMOUNT) AS TOTAL_REVENUE,
        AVG(TOTAL_AMOUNT) AS AVG_ORDER_VALUE
    FROM SALES_CLEANED
    GROUP BY CUSTOMER_ID
),
scored AS (
    SELECT
        *,
        -- If TOTAL_ORDERS = 0, result is NULL
        ROUND(TOTAL_REVENUE / NULLIF(TOTAL_ORDERS, 0), 2) AS AVG_SPEND_PER_ORDER,
        -- If ACTIVE_DAYS <= 0, treat all revenue as one month
        ROUND(
            CASE
                WHEN ACTIVE_DAYS <= 0 THEN TOTAL_REVENUE
                ELSE (TOTAL_REVENUE / ACTIVE_DAYS) * 30
            END,
            2
        ) AS REVENUE_PER_MONTH,
        CASE
            WHEN ACTIVE_DAYS < 30 THEN 'New'
            WHEN ACTIVE_DAYS BETWEEN 30 AND 180 THEN 'Active'
            WHEN ACTIVE_DAYS BETWEEN 181 AND 365 THEN 'At Risk'
            ELSE 'Dormant'
        END AS LIFECYCLE_STAGE
    FROM base
)
SELECT * FROM scored;
