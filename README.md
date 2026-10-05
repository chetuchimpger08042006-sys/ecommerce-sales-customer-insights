# E-commerce Sales & Customer Insights Dashboard

## Project Overview

This project analyzes e-commerce transaction data to understand sales performance, customer behavior, product performance, and regional patterns.

The project includes data cleaning, exploratory data analysis, customer segmentation, cohort analysis, and an interactive Streamlit dashboard.

## Objectives

* Analyze e-commerce sales performance
* Calculate important business KPIs
* Understand customer purchasing behavior
* Identify high-value and at-risk customers
* Analyze product and category performance
* Identify regional sales patterns
* Build an interactive dashboard
* Provide data-driven business recommendations

## Key KPIs

The project calculates:

* Total Revenue
* Total Orders
* Average Order Value (AOV)
* Repeat Customer Rate
* Refund Value / Revenue
* Customer Count
* Monthly Revenue Trends

## Data Analysis

The project performs the following analysis:

### Data Cleaning

* Removes duplicate transactions
* Handles cancelled/refunded orders
* Removes invalid quantities and prices
* Standardizes product descriptions and countries
* Handles missing customer information
* Creates revenue and monthly time features

### Customer Analysis

Customer behavior is analyzed using:

* Monthly customer trends
* Cohort analysis
* RFM segmentation

### RFM Segmentation

RFM stands for:

* **Recency** – how recently a customer purchased
* **Frequency** – how often a customer purchased
* **Monetary** – how much a customer spent

The project identifies customer segments such as:

* Champions
* At Risk
* New / Promising
* Hibernating

### Product & Category Analysis

The project identifies:

* Top-performing products
* High-revenue products
* Underperforming categories
* Category-level revenue patterns

Product categories are derived from product descriptions because the source dataset does not contain a dedicated category column.

### Geographic Analysis

Sales performance is analyzed by country to identify:

* Major revenue-generating regions
* Important export markets
* Regional sales patterns

## Streamlit Dashboard

The project includes an interactive Streamlit dashboard with:

* KPI cards
* Revenue trends
* Product analysis
* Category analysis
* Customer insights
* RFM customer segments
* Geographic analysis
* Interactive filters
* Business recommendations

## Technologies Used

* Python
* Pandas
* NumPy
* Plotly
* Scikit-learn
* Streamlit
* Google Colab
* Jupyter Notebook

## Project Structure

```text
ecommerce-sales-customer-insights/
│
├── app.py
├── ecommerce_sales_customer_insights.ipynb
├── requirements.txt
├── README.md
└── .gitignore
```

## Dataset

The project uses the **Online Retail II** dataset.

The dataset is not included in this GitHub repository because the Excel file is large and is excluded using `.gitignore`.

Required dataset:

```text
online_retail_II.xlsx
```

## How to Run the Project

### 1. Clone the repository

```bash
git clone https://github.com/chetuchimpger08042006-sys/ecommerce-sales-customer-insights.git
cd ecommerce-sales-customer-insights
```

### 2. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 3. Run the Streamlit dashboard

```bash
python -m streamlit run app.py
```

The dashboard will open at:

```text
http://localhost:8501
```

## Google Colab

The Jupyter Notebook can be opened in Google Colab for the complete data analysis.

Upload the required dataset:

```text
online_retail_II.xlsx
```

before running the analysis.

## Important Notes

* Transactions without Customer ID are retained for overall sales analysis.
* Customer-level metrics exclude transactions where Customer ID is unavailable.
* Profit or margin is not calculated because cost information is not available in the source dataset.
* Product categories are approximate because they are derived from product descriptions.
* The source dataset is a flat transaction dataset; analytical customer, product, and location tables are derived from it for analysis.

## Key Insights

The analysis identifies:

* Strong contribution from repeat customers
* High revenue concentration among high-value customers
* Important product and category performance patterns
* Significant contribution from the UK market
* Customer groups requiring retention attention

## Future Improvements

* Add profit and margin analysis when cost data becomes available
* Improve product categorization using NLP
* Add customer churn prediction
* Add real-time data updates
* Deploy the Streamlit dashboard online
* Add automated data pipelines

## Author

**C Chetan**

