# 🧊 E-Commerce Sales Intelligence Dashboard  
**Built with Snowflake + Streamlit | Advanced Data Analytics & Business Insights Project**

### 🔍 About This Project  
This project showcases a **complete cloud-based data analytics solution** built with **Snowflake** and **Streamlit**.  
It replicates an enterprise-grade e-commerce analytics environment with **SQL-based transformations**, **automated KPIs**, and **real-time dashboards**.  

The system uncovers **revenue trends**, **customer retention**, **basket size evolution**, **cohort behavior**, and **cross-sell product patterns**, demonstrating strong expertise in **data engineering**, **analytics modeling**, and **business intelligence visualization**.

## 📖 Overview  
This project highlights an **end-to-end data analytics workflow** — from raw data ingestion in **Snowflake** to interactive analysis via **Streamlit**.  
It focuses on **sales performance, customer behavior, retention analysis, and profitability** using a realistic e-commerce dataset.  

🔗 **Live App:** [E-Commerce Analytics Dashboard](https://ecommerceappanalytics-snowflekproject.streamlit.app)  
🔗 **Snowflake Warehouse:** Private deployment  


## 🧱 Tech Stack  

| Layer | Tools Used | Purpose |
|-------|-------------|----------|
| **Data Warehouse** | Snowflake | Data cleaning, modeling, and analytical SQL |
| **Backend Connector** | snowflake-connector-python | Secure data connectivity |
| **Data App Framework** | Streamlit | Live interactive dashboard |
| **Processing Library** | Pandas | Query results, aggregation, and analysis |

## 🗂️ Data Pipeline Overview  

1. **Raw Data Load** → Source CSV uploaded into Snowflake stage.  
2. **Transformation** → Cleaned into the `SALES_CLEANED` table by removing invalid records (negative quantities, zero prices, missing customer IDs).  
3. **Feature Engineering** → Analytical views created for advanced insights:  
   - `CUSTOMER_SEGMENTS` → RFM segmentation by recency, frequency, and value  
   - `PRODUCT_PAIRS` → Association analysis for frequently bought-together products  
   - `COHORT_MONTHLY` → Retention tracking by customer acquisition month  
   - `SALES_PROFIT` → Estimated profit trends by month  
   - `DATA_QUALITY_METRICS` → Data validation summary  
   - `CUSTOMER_VALUE` → Lifetime value and churn risk modeling  
4. **Visualization Layer** → Streamlit app queries Snowflake and renders interactive dashboards.

## 📊 Key Insights Shown  

### **Executive Dashboard (New)**  
- Combined KPIs: **Total Revenue, Orders, Customers, Repeat Purchase Rate**  
- Monthly revenue trends with **3-month moving average**  
- **Z-score anomaly detection** for outlier months (|z| > 2.5)  
- **Revenue growth** metrics and **profitability overview**  
- **Weekday performance** visualization  

### **Customer Analytics**  
- **New vs Returning Customers** (monthly trend)  
- **Basket Size Trend** → average quantity per order  
- **RFM Segments** → customer behavior grouping  
- **CLV & Churn Risk** → customer lifecycle insights  

### **Product & Market Insights**  
- Top 10 products by revenue  
- Country-level sales comparison  
- Frequently bought-together product pairs (support, lift, confidence)  

### **Data Quality Monitoring**  
- Validation for quantity, price, missing IDs, and invoices  
- Summary of data issues in `RAW_SALES` vs `SALES_CLEANED`  


## ⚙️ Setup Instructions  

### 1. Clone the repository  
```bash
git clone https://github.com/<your-username>/ecommerce_snowflake_analytics.git
cd ecommerce_snowflake_analytics
````

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Streamlit Secrets

In your **Streamlit Cloud** → `App Settings` → `Secrets`, paste:

```toml
[snowflake]
user = "<YOUR_USER>"
password = "<YOUR_PASSWORD>"
account = "<YOUR_ACCOUNT>"
warehouse = "COMPUTE_WH"
database = "SNOWFLAKE_LEARNING_DB"
schema = "SMITCP_LOAD_SAMPLE_DATA_FROM_S3"
```

### 4. Run locally

```bash
streamlit run streamlit_app.py
```

## 🧠 Business Questions Answered

* What are the top revenue-driving products and customers?
* How is monthly sales performance trending across markets?
* What are the **customer retention** and **repeat purchase** patterns?
* Which products tend to be purchased together?
* How reliable and clean is the source data?

## 💡 Learning Outcomes

* Cloud-based analytics and data modeling using **Snowflake**
* Real-world BI development in **Streamlit**
* Implementation of **cohort**, **RFM**, and **churn analysis**
* Data storytelling and dashboarding for business decision-making

## 📈 Future Enhancements

* Add **predictive forecasting** using Snowpark ML or Prophet
* Integrate **real-time refresh** with Snowflake Tasks
* Build an API for **external reporting** (Power BI / Tableau)
* Add user-based **authentication and access control**

## 👤 Author

**Smit Patel**
*Data Analyst | BI Engineer | M.S. Candidate, University of Windsor*

📫 **Connect:**

* [LinkedIn](https://www.linkedin.com/in/smit-patel-34848a210/)
* [Live App](https://ecommerceappanalytics-snowflekproject.streamlit.app)


## 📄 License

Open-source for educational and portfolio purposes. Attribution appreciated.




