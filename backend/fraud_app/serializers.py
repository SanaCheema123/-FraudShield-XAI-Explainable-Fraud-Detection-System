"""
Serializers — Fraud Detection System
"""
from rest_framework import serializers
from .models import Transaction, ChatMessage, AlertRule
from .ml_service import FEATURE_NAMES


class TransactionInputSerializer(serializers.Serializer):
    """Validates raw transaction input before ML analysis."""

    amount = serializers.FloatField(min_value=0.01)
    hour_of_day = serializers.IntegerField(min_value=0, max_value=23, default=12)
    day_of_week = serializers.IntegerField(min_value=0, max_value=6, default=0)
    merchant_category_encoded = serializers.IntegerField(min_value=0, max_value=9, default=0)
    transaction_velocity_1h = serializers.IntegerField(min_value=0, default=1)
    transaction_velocity_24h = serializers.IntegerField(min_value=0, default=5)
    avg_transaction_amount = serializers.FloatField(min_value=0.0, default=100.0)
    amount_deviation = serializers.FloatField(default=0.0)
    is_international = serializers.BooleanField(default=False)
    is_online = serializers.BooleanField(default=False)
    card_age_days = serializers.IntegerField(min_value=0, default=365)
    account_balance_ratio = serializers.FloatField(min_value=0.0, max_value=1.0, default=0.3)
    session_id = serializers.CharField(max_length=100, default="default")


class TransactionResultSerializer(serializers.ModelSerializer):
    """Full transaction result including SHAP explanation."""

    class Meta:
        model = Transaction
        fields = [
            "id",
            "created_at",
            "amount",
            "risk_score",
            "risk_level",
            "is_fraud",
            "confidence",
            "explanation",
            "shap_values",
            "top_factors",
            "is_international",
            "is_online",
            "card_age_days",
            "session_id",
        ]
        read_only_fields = fields


class ChatMessageSerializer(serializers.ModelSerializer):
    transaction_result = TransactionResultSerializer(source="transaction", read_only=True)

    class Meta:
        model = ChatMessage
        fields = ["id", "session_id", "role", "content", "transaction_result", "created_at"]
        read_only_fields = ["id", "created_at"]


class ChatInputSerializer(serializers.Serializer):
    session_id = serializers.CharField(max_length=100)
    message = serializers.CharField(max_length=2000)


class TransactionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ["id", "created_at", "amount", "risk_score", "risk_level", "is_fraud", "confidence"]


class AlertRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AlertRule
        fields = "__all__"
