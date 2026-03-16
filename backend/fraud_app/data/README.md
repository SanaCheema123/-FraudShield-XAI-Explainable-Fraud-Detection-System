# fraud_app/data/ — Data Folder

## Structure

```
data/
├── raw/                          # Original unprocessed data
│   ├── transactions_raw.csv      # 5,000 synthetic transactions (5% fraud rate)
│   ├── card_profiles.csv         # 500 card holder profiles
│   └── merchant_profiles.csv     # 200 merchant profiles with risk scores
│
├── processed/                    # Cleaned, encoded, feature-engineered data
│   ├── transactions_processed.csv # 18-feature processed dataset ready for ML
│   └── split_info.json           # Train/test split sizes and fraud rates
│
├── features/                     # Feature metadata and configs
│   ├── feature_definitions.json  # All 12 features: type, range, description, importance rank
│   ├── merchant_category_lookup.json  # 10 categories with risk levels and fraud rates
│   └── risk_threshold_config.json    # Risk bands, alert rules, model hyperparameters
│
├── samples/                      # Ready-to-use test transaction examples
│   ├── demo_transactions.json    # 4 samples: low/medium/high/critical risk
│   └── batch_test_transactions.csv  # 20-row batch for API testing
│
├── exports/                      # Model outputs and evaluation results
│   ├── model_evaluation_report.json  # Accuracy, precision, recall, ROC-AUC, confusion matrix
│   └── shap_feature_summary.csv      # Per-feature SHAP statistics across all predictions
│
└── logs/                         # Runtime prediction logs
    └── prediction_log.csv        # 50-row sample: score, risk level, processing time
```

## Key Files

| File | Rows | Columns | Purpose |
|------|------|---------|---------|
| raw/transactions_raw.csv | 5,000 | 18 | Training dataset |
| processed/transactions_processed.csv | 5,000 | 19 | ML-ready features |
| samples/demo_transactions.json | 4 | 12 | API demo inputs |
| exports/model_evaluation_report.json | — | — | Model performance metrics |

## Replacing Synthetic Data

To train on real data:
1. Replace `raw/transactions_raw.csv` with your actual fraud dataset
2. Ensure columns match the schema in `feature_definitions.json`
3. Delete `fraud_app/ml/fraud_model.joblib` and `scaler.joblib`
4. Restart the server — it will auto-retrain on the new data
