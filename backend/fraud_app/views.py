"""
REST API Views — Fraud Detection System
"""
import logging
from datetime import datetime, timedelta
from django.db.models import Avg, Count, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import Transaction, ChatMessage, AlertRule
from .serializers import (
    TransactionInputSerializer,
    TransactionResultSerializer,
    ChatMessageSerializer,
    ChatInputSerializer,
    TransactionSummarySerializer,
    AlertRuleSerializer,
)
from .ml_service import FraudDetectionService
from .chat_engine import FraudChatEngine

logger = logging.getLogger("fraud_app")


class AnalyzeTransactionView(APIView):
    """
    POST /api/analyze/
    Analyze a single transaction for fraud risk with SHAP explanations.
    """

    def post(self, request):
        serializer = TransactionInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {"error": "Invalid input", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = serializer.validated_data
        session_id = data.pop("session_id", "default")

        try:
            service = FraudDetectionService()
            result = service.analyze(data)

            # Persist transaction
            txn = Transaction.objects.create(
                session_id=session_id,
                risk_score=result["risk_score"],
                risk_level=result["risk_level"],
                is_fraud=result["is_fraud"],
                confidence=result["confidence"],
                explanation=result["explanation"],
                shap_values=result["shap_values"],
                top_factors=result["top_factors"],
                **data,
            )

            result["transaction_id"] = str(txn.id)
            result["timestamp"] = txn.created_at.isoformat()

            logger.info(
                f"Transaction {txn.id} analyzed — risk={result['risk_level']}, "
                f"score={result['risk_score']:.3f}"
            )
            return Response(result, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Analysis failed")
            return Response(
                {"error": "Analysis failed", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ChatView(APIView):
    """
    POST /api/chat/
    Send a chat message to the fraud analysis assistant.
    GET  /api/chat/?session_id=xxx
    Retrieve conversation history for a session.
    """

    def get(self, request):
        session_id = request.query_params.get("session_id", "default")
        messages = ChatMessage.objects.filter(session_id=session_id).order_by("created_at")
        return Response(ChatMessageSerializer(messages, many=True).data)

    def post(self, request):
        serializer = ChatInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        session_id = serializer.validated_data["session_id"]
        user_message = serializer.validated_data["message"]

        # Save user message
        ChatMessage.objects.create(
            session_id=session_id, role="user", content=user_message
        )

        # Get conversation history
        history = list(
            ChatMessage.objects.filter(session_id=session_id)
            .order_by("created_at")
            .values("role", "content")
        )

        # Generate assistant response
        engine = FraudChatEngine()
        response_data = engine.respond(user_message, history, session_id)

        # Save assistant message (link transaction if any)
        txn = None
        if response_data.get("transaction_id"):
            txn = Transaction.objects.filter(id=response_data["transaction_id"]).first()

        assistant_msg = ChatMessage.objects.create(
            session_id=session_id,
            role="assistant",
            content=response_data["message"],
            transaction=txn,
        )

        return Response(
            {
                "message_id": str(assistant_msg.id),
                "message": response_data["message"],
                "transaction": (
                    TransactionResultSerializer(txn).data if txn else None
                ),
                "suggestions": response_data.get("suggestions", []),
            },
            status=status.HTTP_200_OK,
        )


class TransactionHistoryView(APIView):
    """
    GET /api/transactions/
    List recent transactions with optional filters.
    """

    def get(self, request):
        session_id = request.query_params.get("session_id")
        risk_level = request.query_params.get("risk_level")
        limit = int(request.query_params.get("limit", 20))

        qs = Transaction.objects.all()
        if session_id:
            qs = qs.filter(session_id=session_id)
        if risk_level:
            qs = qs.filter(risk_level=risk_level)

        transactions = qs[:limit]
        return Response(TransactionSummarySerializer(transactions, many=True).data)


class DashboardStatsView(APIView):
    """
    GET /api/stats/
    Real-time dashboard statistics.
    """

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)
        last_7d = now - timedelta(days=7)

        total = Transaction.objects.count()
        last_24h_qs = Transaction.objects.filter(created_at__gte=last_24h)
        last_7d_qs = Transaction.objects.filter(created_at__gte=last_7d)

        risk_distribution = (
            Transaction.objects.values("risk_level")
            .annotate(count=Count("id"))
            .order_by("risk_level")
        )

        stats = {
            "total_transactions": total,
            "transactions_24h": last_24h_qs.count(),
            "fraud_detected_24h": last_24h_qs.filter(is_fraud=True).count(),
            "fraud_rate_24h": _safe_rate(
                last_24h_qs.filter(is_fraud=True).count(),
                last_24h_qs.count(),
            ),
            "avg_risk_score": last_7d_qs.aggregate(avg=Avg("risk_score"))["avg"] or 0.0,
            "risk_distribution": {item["risk_level"]: item["count"] for item in risk_distribution},
            "high_risk_24h": last_24h_qs.filter(
                Q(risk_level="high") | Q(risk_level="critical")
            ).count(),
            "timestamp": now.isoformat(),
        }
        return Response(stats)


class TransactionDetailView(APIView):
    """GET /api/transactions/<uuid:pk>/"""

    def get(self, request, pk):
        try:
            txn = Transaction.objects.get(pk=pk)
            return Response(TransactionResultSerializer(txn).data)
        except Transaction.DoesNotExist:
            return Response({"error": "Not found"}, status=status.HTTP_404_NOT_FOUND)


class AlertRuleView(APIView):
    """GET/POST /api/alerts/"""

    def get(self, request):
        rules = AlertRule.objects.filter(is_active=True)
        return Response(AlertRuleSerializer(rules, many=True).data)

    def post(self, request):
        serializer = AlertRuleSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET"])
def health_check(request):
    """GET /api/health/ — Service health endpoint."""
    return Response({"status": "healthy", "service": "fraud-detection-api", "version": "1.0.0"})


def _safe_rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator > 0 else 0.0
