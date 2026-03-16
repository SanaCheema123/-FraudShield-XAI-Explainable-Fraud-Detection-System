"""
ML Service — Fraud Detection with SHAP Explainability
------------------------------------------------------
Uses an Isolation Forest (unsupervised) + Random Forest classifier (supervised)
with SHAP TreeExplainer for per-prediction feature attribution.

On first run, a model is trained on synthetic data and saved to disk.
In production, replace `_generate_synthetic_data()` with your real dataset.
"""
import os
import logging
import numpy as np
import pandas as pd
import joblib
import shap
from pathlib import Path
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

logger = logging.getLogger("fraud_app")

MODEL_DIR = Path(__file__).parent / "ml"
MODEL_PATH = MODEL_DIR / "fraud_model.joblib"
SCALER_PATH = MODEL_DIR / "scaler.joblib"

FEATURE_NAMES = [
    "amount",
    "hour_of_day",
    "day_of_week",
    "merchant_category_encoded",
    "transaction_velocity_1h",
    "transaction_velocity_24h",
    "avg_transaction_amount",
    "amount_deviation",
    "is_international",
    "is_online",
    "card_age_days",
    "account_balance_ratio",
]

FEATURE_DESCRIPTIONS = {
    "amount": "Transaction Amount ($)",
    "hour_of_day": "Hour of Day (0–23)",
    "day_of_week": "Day of Week (0=Mon)",
    "merchant_category_encoded": "Merchant Category",
    "transaction_velocity_1h": "Transactions in Last Hour",
    "transaction_velocity_24h": "Transactions in Last 24h",
    "avg_transaction_amount": "Avg Historical Amount ($)",
    "amount_deviation": "Amount vs. Avg Deviation",
    "is_international": "International Transaction",
    "is_online": "Online Transaction",
    "card_age_days": "Card Age (Days)",
    "account_balance_ratio": "Balance-to-Limit Ratio",
}

RISK_THRESHOLDS = {
    "low": 0.3,
    "medium": 0.6,
    "high": 0.85,
}


def _generate_synthetic_data(n_samples: int = 5000):
    """Generate synthetic transaction data for demo training."""
    np.random.seed(42)
    n_legit = int(n_samples * 0.95)
    n_fraud = n_samples - n_legit

    # Legitimate transactions
    legit = pd.DataFrame({
        "amount": np.random.lognormal(4.0, 1.0, n_legit),
        "hour_of_day": np.random.choice(range(8, 22), n_legit),
        "day_of_week": np.random.choice(range(7), n_legit),
        "merchant_category_encoded": np.random.choice(range(10), n_legit),
        "transaction_velocity_1h": np.random.poisson(1, n_legit),
        "transaction_velocity_24h": np.random.poisson(5, n_legit),
        "avg_transaction_amount": np.random.lognormal(4.0, 0.8, n_legit),
        "amount_deviation": np.random.normal(0, 1, n_legit),
        "is_international": np.random.binomial(1, 0.1, n_legit),
        "is_online": np.random.binomial(1, 0.3, n_legit),
        "card_age_days": np.random.randint(30, 3650, n_legit),
        "account_balance_ratio": np.random.uniform(0.0, 0.7, n_legit),
        "label": 0,
    })

    # Fraudulent transactions (unusual patterns)
    fraud = pd.DataFrame({
        "amount": np.random.lognormal(6.5, 1.5, n_fraud),
        "hour_of_day": np.random.choice([0, 1, 2, 3, 23], n_fraud),
        "day_of_week": np.random.choice(range(7), n_fraud),
        "merchant_category_encoded": np.random.choice([7, 8, 9], n_fraud),
        "transaction_velocity_1h": np.random.poisson(8, n_fraud),
        "transaction_velocity_24h": np.random.poisson(20, n_fraud),
        "avg_transaction_amount": np.random.lognormal(3.5, 1.2, n_fraud),
        "amount_deviation": np.random.normal(4, 2, n_fraud),
        "is_international": np.random.binomial(1, 0.7, n_fraud),
        "is_online": np.random.binomial(1, 0.9, n_fraud),
        "card_age_days": np.random.randint(1, 90, n_fraud),
        "account_balance_ratio": np.random.uniform(0.85, 1.0, n_fraud),
        "label": 1,
    })

    return pd.concat([legit, fraud], ignore_index=True).sample(frac=1, random_state=42)


def train_and_save_model():
    """Train the fraud detection model and persist it."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Training fraud detection model on synthetic data...")

    df = _generate_synthetic_data()
    X = df[FEATURE_NAMES].values
    y = df["label"].values

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        class_weight={0: 1, 1: 10},
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train_scaled, y_train)

    y_pred = model.predict(X_test_scaled)
    logger.info("\n" + classification_report(y_test, y_pred, target_names=["Legit", "Fraud"]))

    joblib.dump(model, MODEL_PATH)
    joblib.dump(scaler, SCALER_PATH)
    logger.info(f"Model saved → {MODEL_PATH}")
    return model, scaler


class FraudDetectionService:
    """
    Singleton service for fraud detection + SHAP explanation.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._model = None
        self._scaler = None
        self._explainer = None
        self._load_or_train()
        self._initialized = True

    def _load_or_train(self):
        if MODEL_PATH.exists() and SCALER_PATH.exists():
            logger.info("Loading existing model from disk...")
            self._model = joblib.load(MODEL_PATH)
            self._scaler = joblib.load(SCALER_PATH)
        else:
            self._model, self._scaler = train_and_save_model()

        self._explainer = shap.TreeExplainer(self._model)
        logger.info("SHAP TreeExplainer initialized.")

    def analyze(self, transaction: dict) -> dict:
        """
        Analyze a transaction and return risk score + SHAP explanations.

        Parameters
        ----------
        transaction : dict with keys matching FEATURE_NAMES

        Returns
        -------
        dict with:
            risk_score      float [0, 1]
            risk_level      str   "low" | "medium" | "high" | "critical"
            is_fraud        bool
            confidence      float
            shap_values     list of {feature, value, shap_value, direction}
            explanation     str   human-readable summary
            top_factors     list of str
        """
        try:
            features = np.array([[transaction.get(f, 0.0) for f in FEATURE_NAMES]])
            features_scaled = self._scaler.transform(features)

            # Probabilities
            proba = self._model.predict_proba(features_scaled)[0]
            fraud_prob = float(proba[1])

            # SHAP values (for class 1 = fraud)
            shap_vals = self._explainer.shap_values(features_scaled)
            if isinstance(shap_vals, list):
                shap_for_fraud = shap_vals[1][0]
            else:
                shap_for_fraud = shap_vals[0]

            # Build SHAP breakdown
            shap_breakdown = []
            for i, feat in enumerate(FEATURE_NAMES):
                sv = float(shap_for_fraud[i])
                shap_breakdown.append({
                    "feature": feat,
                    "label": FEATURE_DESCRIPTIONS[feat],
                    "value": float(features[0][i]),
                    "shap_value": round(sv, 4),
                    "direction": "increases_risk" if sv > 0 else "decreases_risk",
                    "magnitude": round(abs(sv), 4),
                })

            # Sort by absolute magnitude
            shap_breakdown.sort(key=lambda x: x["magnitude"], reverse=True)
            top_5 = shap_breakdown[:5]

            # Determine risk level
            if fraud_prob < RISK_THRESHOLDS["low"]:
                risk_level = "low"
            elif fraud_prob < RISK_THRESHOLDS["medium"]:
                risk_level = "medium"
            elif fraud_prob < RISK_THRESHOLDS["high"]:
                risk_level = "high"
            else:
                risk_level = "critical"

            # Human-readable explanation
            risk_factors = [x["label"] for x in top_5 if x["direction"] == "increases_risk"]
            protective_factors = [x["label"] for x in top_5 if x["direction"] == "decreases_risk"]

            explanation = _build_explanation(
                fraud_prob, risk_level, risk_factors, protective_factors, transaction
            )

            return {
                "risk_score": round(fraud_prob, 4),
                "risk_level": risk_level,
                "is_fraud": fraud_prob >= 0.5,
                "confidence": round(max(proba), 4),
                "shap_values": shap_breakdown,
                "top_factors": [x["label"] for x in top_5],
                "explanation": explanation,
                "feature_values": {f: float(features[0][i]) for i, f in enumerate(FEATURE_NAMES)},
            }

        except Exception as e:
            logger.exception(f"Analysis error: {e}")
            raise


def _build_explanation(fraud_prob, risk_level, risk_factors, protective_factors, txn):
    amount = txn.get("amount", 0)
    velocity = txn.get("transaction_velocity_1h", 0)

    lines = []

    if risk_level == "low":
        lines.append(
            f"✅ This transaction appears LEGITIMATE with {round((1 - fraud_prob) * 100, 1)}% confidence."
        )
    elif risk_level == "medium":
        lines.append(
            f"⚠️ This transaction has MODERATE risk ({round(fraud_prob * 100, 1)}% fraud probability)."
        )
    elif risk_level == "high":
        lines.append(
            f"🔴 This transaction is HIGH RISK ({round(fraud_prob * 100, 1)}% fraud probability). Review recommended."
        )
    else:
        lines.append(
            f"🚨 CRITICAL ALERT — This transaction is almost certainly fraudulent ({round(fraud_prob * 100, 1)}% confidence). Block immediately."
        )

    if risk_factors:
        lines.append(f"\n**Key risk drivers:** {', '.join(risk_factors[:3])}.")

    if protective_factors:
        lines.append(f"**Mitigating factors:** {', '.join(protective_factors[:2])}.")

    if amount > 5000:
        lines.append(f"• High transaction value (${amount:,.2f}) is a significant signal.")
    if velocity >= 5:
        lines.append(f"• {int(velocity)} transactions in the last hour indicates unusual velocity.")

    return " ".join(lines)
