# Data Directory

This directory contains all datasets used in the Olist NLP project.

IMPORTANT:
Raw and processed datasets are NOT versioned in this repository for size and reproducibility reasons.

---

## 📂 Folder Structure

data/
│
├── raw/        # Original raw CSV files (do not modify)
├── processed/  # Cleaned / feature-engineered datasets
└── README.md

---

## 📥 Required Dataset

This project uses the **Olist Brazilian E-Commerce Public Dataset**, available on Kaggle:

https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

Download the dataset manually and place the CSV files inside:

## data/raw/

Expected files include:

- olist_orders_dataset.csv
- olist_order_items_dataset.csv
- olist_order_reviews_dataset.csv
- olist_customers_dataset.csv
- olist_products_dataset.csv
- olist_order_payments_dataset.csv
- olist_sellers_dataset.csv
- olist_geolocation_dataset.csv
- product_category_name_translation.csv


## data/processed

After running the data preparation notebooks or scripts, processed datasets will be stored in:

These files may include:
- Cleaned review datasets
- Feature-engineered datasets
- Model-ready training data

## 🧠 Reproducibility

To reproduce the processed datasets:

1. Place raw files in `data/raw/`
2. Run:
   - `notebooks/1_eda_python.ipynb`
   - `notebooks/2_build_dataset.ipynb`