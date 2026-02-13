# Olist NLP – Bad Review Detection in E-Commerce

This project applies Natural Language Processing (NLP) and Machine Learning techniques to detect bad reviews in the Olist Brazilian E-Commerce dataset.

The goal is to build a reproducible ML pipeline capable of identifying negative customer experiences using textual data.

---

# Project Objectives

- Perform structured EDA on transactional data
- Clean and analyze customer review text
- Engineer text-based features (TF-IDF, n-grams)
- Compare text vs non-text baselines
- Evaluate models using ROC-AUC, PR-AUC, F1
- Explore threshold trade-offs for business decision-making

---

# Dataset

Source: Olist Brazilian E-Commerce Public Dataset  
Available at Kaggle:

https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce

The dataset includes:
- Orders
- Customers
- Products
- Payments
- Reviews
- Sellers
- Geolocation

Reviews are written in Portuguese.

The target variable constructed in this project:
    bad_review = 1 if review_score <= 2
    bad_review = 0 otherwise

# Methodology

## 1️⃣ Data Engineering
- Merging transactional tables
- Handling duplicates and missing values
- Feature engineering

## 2️⃣ Text Processing
- Lowercasing
- Accent normalization
- Stopword removal (Portuguese)
- Preservation of negation terms (e.g., "não")
- TF-IDF vectorization (word, char n-grams, char words boundaries)

## 3️⃣ Models Evaluated
- Logistic Regression
- LinearSVM
- CalibratedClassifierCV
- TF-IDF (word-level)
- TF-IDF (character-level)


# 📈 Main Results (Baseline)

Example results (Logistic Regression + Word TF-IDF):

- ROC-AUC ≈ 0.95
- PR-AUC ≈ 0.81
- F1 (bad reviews) ≈ 0.79
- Recall (bad reviews) ≈ 0.90+

The model shows strong performance in detecting negative reviews while handling class imbalance.

Confusion matrix (example):
[[5609 696]
[ 170 1654]]

---

# Project Structure
OLIST_NLP/
│
├── data/
│ ├── raw/
│ ├── processed/
│ └── README.md
│
├── notebooks/
│ ├── 1_eda_python.ipynb
│ ├── 2_build_dataset.ipynb
│ ├── 3_eda_text_quality.ipynb
│ └── 4_baseline_text_vs_nontext.ipynb
│
├── src/
│ ├── elt/
│ │ └── load_data.py
│ ├── nlp/
│ └── utils/
│
├── docker-compose.yml
└── .env (not versioned)

# ⚙️ Installation

## 1️⃣ Clone repository

git clone https://github.com/your-username/olist-nlp.git

cd olist-nlp

## 2️⃣ Environment (Conda)

### Create environment

-terminal/command interpreter

conda env create -f environment.yml

Activate environment
conda activate olist_nlp

Update environment (if dependencies change)

conda env update -f environment.yml --prune


## 3️⃣ If you don't already have a specific environment , do it:

Example creating a new one:

```bash
conda create -n olist_nlp python=3.11 -y
conda activate olist_nlp
---

# Business Perspective

Two possible optimization strategies:

1. High Recall Strategy  
   Prioritize detecting most bad reviews (minimize false negatives).

2. High Precision Strategy  
   Avoid flagging good reviews incorrectly (minimize false positives).

Threshold tuning allows adapting the model to different business objectives.


---

# 📌 Future Improvements

- Add model comparison dashboard
- Deploy model as API
- Add recommendation system module
- Experiment with transformer-based models
- Implement experiment tracking (MLflow)