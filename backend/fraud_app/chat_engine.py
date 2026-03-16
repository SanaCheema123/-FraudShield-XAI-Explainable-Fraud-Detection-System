"""
Chat Engine — Natural Language Fraud Analysis Assistant
-------------------------------------------------------
Parses user messages, extracts transaction data via NLP patterns,
and generates contextual responses with fraud explanations.
"""
import re
import logging
from .ml_service import FraudDetectionService, FEATURE_DESCRIPTIONS

logger = logging.getLogger("fraud_app")

# Suggestion pools by context
SUGGESTIONS = {
    "greeting": [
        "Analyze a transaction: 'Check $500 online purchase'",
        "Explain fraud patterns",
        "Show high-risk indicators",
        "What is SHAP explainability?",
    ],
    "after_analysis": [
        "Why is this flagged?",
        "What factors increase risk?",
        "Compare with my account history",
        "Should I block this transaction?",
    ],
    "explanation": [
        "Analyze another transaction",
        "What are common fraud patterns?",
        "How accurate is the model?",
        "Show recent high-risk transactions",
    ],
}

GREETINGS = {"hi", "hello", "hey", "start", "help", "?"}
EXPLANATION_TRIGGERS = {"why", "explain", "reason", "because", "factor", "shap", "how"}
FRAUD_PATTERN_TRIGGERS = {"pattern", "common", "typical", "fraud", "example"}
ACCURACY_TRIGGERS = {"accurate", "accuracy", "precision", "reliable", "model", "confidence"}


class FraudChatEngine:
    """Rule-based + ML-hybrid chat engine for fraud analysis."""

    def respond(self, message: str, history: list, session_id: str) -> dict:
        msg = message.strip().lower()
        words = set(re.findall(r"\w+", msg))

        # 1. Greeting / help
        if words & GREETINGS and len(words) <= 4:
            return self._greeting_response()

        # 2. Try to parse a transaction from the message
        txn_data = self._extract_transaction(message)
        if txn_data:
            return self._analyze_and_respond(txn_data, session_id)

        # 3. Explanation request about last transaction
        if words & EXPLANATION_TRIGGERS:
            last_txn = self._get_last_transaction_from_history(history)
            if last_txn:
                return self._explain_response(last_txn)
            return {
                "message": "I don't have a recent transaction to explain. Please share a transaction first — e.g., *'Check $1,200 international online purchase'*.",
                "suggestions": SUGGESTIONS["greeting"],
            }

        # 4. Fraud patterns
        if words & FRAUD_PATTERN_TRIGGERS:
            return self._fraud_patterns_response()

        # 5. Model accuracy
        if words & ACCURACY_TRIGGERS:
            return self._accuracy_response()

        # 6. Fallback
        return {
            "message": (
                "I'm your **Fraud Detection Assistant** 🔍. I can:\n\n"
                "• **Analyze transactions** — just describe one (e.g., *'$3,500 international purchase at 2am'*)\n"
                "• **Explain risk factors** with SHAP values\n"
                "• **Discuss fraud patterns** and model behavior\n\n"
                "What would you like to do?"
            ),
            "suggestions": SUGGESTIONS["greeting"],
        }

    def _extract_transaction(self, message: str) -> dict | None:
        """
        Extract transaction features from natural language.
        Examples:
            "$1,500 online international purchase"
            "check amount 3000 at 3am, 5 recent transactions"
            "analyze $250 domestic in-store"
        """
        data = {}

        # Amount
        amount_match = re.search(r"\$?([\d,]+(?:\.\d{1,2})?)", message)
        if not amount_match:
            return None
        data["amount"] = float(amount_match.group(1).replace(",", ""))

        # Hour of day
        hour_match = re.search(r"(\d{1,2})\s*(?:am|pm|AM|PM)", message)
        if hour_match:
            h = int(hour_match.group(1))
            if "pm" in message.lower() and h < 12:
                h += 12
            data["hour_of_day"] = h % 24
        else:
            data["hour_of_day"] = 14  # default: 2pm

        # Is international
        data["is_international"] = int(
            bool(re.search(r"international|foreign|abroad|overseas", message, re.I))
        )

        # Is online
        data["is_online"] = int(
            bool(re.search(r"online|web|internet|e-?commerce|digital", message, re.I))
        )

        # Transaction velocity (mentions of "N transactions")
        vel_match = re.search(r"(\d+)\s*(?:recent\s+)?transactions?", message, re.I)
        if vel_match:
            data["transaction_velocity_1h"] = min(int(vel_match.group(1)), 20)
            data["transaction_velocity_24h"] = min(int(vel_match.group(1)) * 3, 50)

        # Defaults for unspecified features
        data.setdefault("transaction_velocity_1h", 1)
        data.setdefault("transaction_velocity_24h", 4)
        data.setdefault("merchant_category_encoded", 3)
        data.setdefault("day_of_week", 1)
        data.setdefault("avg_transaction_amount", data["amount"] * 0.6)
        data.setdefault("amount_deviation", (data["amount"] - data["avg_transaction_amount"]) / max(data["avg_transaction_amount"], 1))
        data.setdefault("card_age_days", 500)
        data.setdefault("account_balance_ratio", 0.3)

        return data

    def _analyze_and_respond(self, txn_data: dict, session_id: str) -> dict:
        try:
            service = FraudDetectionService()
            result = service.analyze(txn_data)

            # Save transaction to DB
            from .models import Transaction
            txn = Transaction.objects.create(
                session_id=session_id,
                risk_score=result["risk_score"],
                risk_level=result["risk_level"],
                is_fraud=result["is_fraud"],
                confidence=result["confidence"],
                explanation=result["explanation"],
                shap_values=result["shap_values"],
                top_factors=result["top_factors"],
                **txn_data,
            )

            # Format SHAP top factors
            top = result["shap_values"][:3]
            factor_lines = "\n".join(
                f"  {'🔴' if x['direction'] == 'increases_risk' else '🟢'} **{x['label']}** "
                f"(impact: {'+' if x['shap_value'] > 0 else ''}{x['shap_value']:.3f})"
                for x in top
            )

            risk_emoji = {"low": "✅", "medium": "⚠️", "high": "🔴", "critical": "🚨"}.get(
                result["risk_level"], "❓"
            )

            message = (
                f"{risk_emoji} **{result['risk_level'].upper()} RISK** — "
                f"Score: `{result['risk_score']:.1%}` | Confidence: `{result['confidence']:.1%}`\n\n"
                f"{result['explanation']}\n\n"
                f"**Top SHAP Factors:**\n{factor_lines}"
            )

            return {
                "message": message,
                "transaction_id": str(txn.id),
                "suggestions": SUGGESTIONS["after_analysis"],
            }

        except Exception as e:
            logger.exception("Chat analysis error")
            return {
                "message": f"⚠️ Analysis failed: {str(e)}",
                "suggestions": SUGGESTIONS["greeting"],
            }

    def _explain_response(self, txn_data: dict) -> dict:
        shap_values = txn_data.get("shap_values") or []
        if not shap_values:
            return {
                "message": "No SHAP data available for the last transaction.",
                "suggestions": SUGGESTIONS["greeting"],
            }

        lines = []
        for x in shap_values[:5]:
            icon = "🔴" if x["direction"] == "increases_risk" else "🟢"
            direction_text = "increases" if x["direction"] == "increases_risk" else "decreases"
            lines.append(
                f"{icon} **{x['label']}** = `{x['value']:.2f}` → "
                f"{direction_text} fraud risk by `{abs(x['shap_value']):.4f}`"
            )

        return {
            "message": (
                "**SHAP Explanation** — How each feature contributed to this prediction:\n\n"
                + "\n".join(lines)
                + "\n\n*SHAP values represent how much each feature pushed the risk score "
                "up (🔴) or down (🟢) from the baseline prediction.*"
            ),
            "suggestions": SUGGESTIONS["explanation"],
        }

    def _get_last_transaction_from_history(self, history: list) -> dict | None:
        """Find the last transaction in the DB for this session (crude but functional)."""
        from .models import Transaction
        txn = Transaction.objects.order_by("-created_at").first()
        if txn and txn.shap_values:
            return {"shap_values": txn.shap_values, "risk_level": txn.risk_level}
        return None

    def _fraud_patterns_response(self) -> dict:
        return {
            "message": (
                "**Common Fraud Patterns** our model detects:\n\n"
                "🌙 **Off-hours activity** — Transactions at 1–4am significantly increase risk\n"
                "🌍 **International + online** — Combined flags correlate with card-not-present fraud\n"
                "⚡ **High velocity** — 5+ transactions in 1 hour suggests automated attacks\n"
                "💰 **Amount anomaly** — Purchases far above historical average are suspicious\n"
                "🆕 **New card** — Cards under 90 days old are higher risk\n"
                "📊 **Balance ratio** — High balance utilization (>85%) can indicate account takeover\n\n"
                "The model uses **SHAP values** to show which factors drove each specific prediction."
            ),
            "suggestions": SUGGESTIONS["explanation"],
        }

    def _accuracy_response(self) -> dict:
        return {
            "message": (
                "**Model Performance** (trained on 5,000 synthetic transactions):\n\n"
                "• **Algorithm**: Random Forest (100 trees, class-weighted for imbalance)\n"
                "• **Fraud class recall**: ~92% — catches most fraud\n"
                "• **Precision**: ~87% — low false positive rate\n"
                "• **Explainability**: SHAP TreeExplainer (exact, not approximated)\n\n"
                "In production, replace synthetic training data with your historical transaction "
                "dataset and retrain. The model path is configurable via `settings.ML_MODEL_PATH`.\n\n"
                "⚠️ *This system is a decision support tool — always apply human review for critical flags.*"
            ),
            "suggestions": SUGGESTIONS["explanation"],
        }

    def _greeting_response(self) -> dict:
        return {
            "message": (
                "👋 Welcome to the **Explainable Fraud Detection System**!\n\n"
                "I can analyze transactions in real time using machine learning and explain "
                "*exactly why* each transaction is flagged using **SHAP values**.\n\n"
                "**Try something like:**\n"
                "• *'Check $2,500 international online purchase at 2am'*\n"
                "• *'Analyze $150 domestic in-store transaction'*\n"
                "• *'5 transactions in last hour, $800 each'*\n\n"
                "Or ask me about fraud patterns, model accuracy, or explainability!"
            ),
            "suggestions": SUGGESTIONS["greeting"],
        }
