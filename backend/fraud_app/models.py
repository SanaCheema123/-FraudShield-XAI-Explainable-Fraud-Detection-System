"""
Models — Fraud Detection System
"""
from django.db import models
import uuid


class Transaction(models.Model):
    """Represents a financial transaction submitted for analysis."""

    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
        ("pending", "Pending"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    # Transaction features
    amount = models.FloatField()
    hour_of_day = models.IntegerField(default=12)
    day_of_week = models.IntegerField(default=0)
    merchant_category_encoded = models.IntegerField(default=0)
    transaction_velocity_1h = models.IntegerField(default=1)
    transaction_velocity_24h = models.IntegerField(default=5)
    avg_transaction_amount = models.FloatField(default=100.0)
    amount_deviation = models.FloatField(default=0.0)
    is_international = models.BooleanField(default=False)
    is_online = models.BooleanField(default=False)
    card_age_days = models.IntegerField(default=365)
    account_balance_ratio = models.FloatField(default=0.3)

    # ML results
    risk_score = models.FloatField(null=True, blank=True)
    risk_level = models.CharField(
        max_length=10, choices=RISK_CHOICES, default="pending"
    )
    is_fraud = models.BooleanField(null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True)
    explanation = models.TextField(blank=True)
    shap_values = models.JSONField(null=True, blank=True)
    top_factors = models.JSONField(null=True, blank=True)

    # Metadata
    session_id = models.CharField(max_length=100, blank=True)
    analyst_note = models.TextField(blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["risk_level"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["session_id"]),
        ]

    def __str__(self):
        return f"Transaction {self.id} — ${self.amount:.2f} [{self.risk_level}]"

    @property
    def risk_color(self):
        return {
            "low": "#00ff88",
            "medium": "#ffb800",
            "high": "#ff4444",
            "critical": "#ff0066",
            "pending": "#888888",
        }.get(self.risk_level, "#888888")


class ChatMessage(models.Model):
    """Stores chatbot conversation history per session."""

    ROLE_CHOICES = [("user", "User"), ("assistant", "Assistant")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_id = models.CharField(max_length=100, db_index=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    transaction = models.ForeignKey(
        Transaction, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.session_id}] {self.role}: {self.content[:60]}"


class AlertRule(models.Model):
    """Configurable alert rules for fraud thresholds."""

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    risk_threshold = models.FloatField(default=0.8)
    amount_threshold = models.FloatField(default=10000.0)
    velocity_threshold = models.IntegerField(default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
