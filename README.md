# 🧊 E-Commerce Sales Intelligence Dashboard  
**Built with Snowflake + Streamlit | Data Analytics & Business Insights Project**

### 🔍 About This Project  
This project was developed at a **master’s level** to demonstrate full-stack data analytics capability — from cloud data warehousing and SQL modeling in **Snowflake**, to business intelligence and interactive visualization in **Streamlit**.  
It replicates a **real-world e-commerce analytics workflow**, integrating advanced analytical techniques such as **RFM segmentation**, **cohort retention analysis**, and **cross-sell pattern mining**.  
The project reflects graduate-level expertise in **data engineering, business analytics, and cloud-based BI deployment**.

## 📖 Overview  
This project demonstrates a full end-to-end data analytics workflow — from data cleaning in **Snowflake** to interactive dashboarding in **Streamlit**.  
It focuses on understanding **sales performance, customer behavior, and product trends** using real-world e-commerce data.
The goal is to show how data analysts and business intelligence professionals can use modern cloud tools to uncover insights and support decision-making.

🔗 **Live App:** [E-Commerce Analytics Dashboard](https://ecommerceappanalytics-snowflekproject.streamlit.app)  
🔗 **Snowflake Project:** Internal (private data warehouse)  


## 🧱 Tech Stack  
| Layer | Tools Used | Purpose |
|-------|-------------|----------|
| Data Warehouse | **Snowflake** | Data cleaning, transformation, and SQL analytics |
| Backend Connector | **snowflake-connector-python** | Secure connection to Snowflake from Streamlit |
| Data App | **Streamlit** | Interactive visual dashboard |
| Data Processing | **Pandas** | Data wrangling and summarization |


## 🗂️ Data Pipeline Overview  
1. **Raw Data Load** → CSV uploaded to Snowflake stage.  
2. **Transformation** → Cleaned into `SALES_CLEANED` table using SQL (filtering invalid quantities, prices, missing customers).  
3. **Feature Engineering** → Created analytical views and tables:
   - `CUSTOMER_SEGMENTS` (RFM segmentation)
   - `PRODUCT_PAIRS` (frequently co-purchased items)
   - `COHORT_MONTHLY` (retention trends)
   - `SALES_PROFIT` (profitability estimates)
   - `DATA_QUALITY_METRICS` (data validation summary)
4. **Analytics Visualization** → Streamlit connects to Snowflake and renders results live.


## 📊 Key Insights Shown
- **Executive Summary:** Total sales, orders, and active customers.  
- **Monthly Revenue Trend:** Seasonality and growth patterns.  
- **Top Products & Customers:** Identifies most valuable SKUs and loyal buyers.  
- **Customer Segmentation (RFM):** Behavioral grouping for retention strategy.  
- **Cohort Retention:** Visualizes customer stickiness month-over-month.  
- **Product Pairing:** Shows commonly bought-together products.  
- **Data Quality Report:** Detects issues in the raw dataset.  

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
[connections.snowflake]
account = "<ACCOUNT NAME>"
user = "<USER NAME>"
password = "<YOUR_PASSWORD>"
role = "ACCOUNTADMIN"
warehouse = "COMPUTE_WH"
database = "SNOWFLAKE_LEARNING_DB"
schema = "SMITCP_LOAD_SAMPLE_DATA_FROM_S3"
```

### 4. Run locally

```bash
streamlit run streamlit_app.py
```

---

## 🧠 Business Questions Answered

* Which products and customers drive the most revenue?
* How does revenue vary across time, country, and weekdays?
* What are the customer retention and lifecycle patterns?
* Which product bundles are most frequently sold together?
* What’s the overall data quality health of the sales dataset?


## 💡 Learning Objectives

* Cloud-based SQL analytics with **Snowflake**
* Business insights via **RFM segmentation** and **cohort analysis**
* End-to-end dashboard development in **Streamlit**
* Data storytelling for business stakeholders


## 📈 Future Enhancements

* Add predictive sales forecasting (using Snowpark or Python ML models)
* Integrate real-time data refresh using Snowflake Tasks
* Build an API for product recommendation


## 👤 Author

**Smit Patel**
*Data Analyst | Business Intelligence Enthusiast | M.S. Graduate in Computer Engineering*

📫 **Connect:**

* [LinkedIn](https://www.linkedin.com/in/smit-patel-34848a210/)
* [Streamlit App](https://ecommerceappanalytics-snowflekproject.streamlit.app)

## 📄 License

This project is open-source for educational and portfolio use. Attribution is appreciated.
