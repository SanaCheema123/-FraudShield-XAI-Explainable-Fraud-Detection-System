"""
WebSocket Consumer — Real-Time Fraud Analysis Streaming
-------------------------------------------------------
Provides a persistent WebSocket connection per session for:
  - Streaming transaction analysis results
  - Live chat with the fraud assistant
  - Real-time alert push notifications
"""
import json
import logging
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

from .ml_service import FraudDetectionService
from .chat_engine import FraudChatEngine
from .models import Transaction, ChatMessage

logger = logging.getLogger("fraud_app")


class FraudAnalysisConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time fraud analysis.

    Client connects to: ws://localhost:8000/ws/fraud/<session_id>/

    Message protocol (JSON):
        Client → Server:
            { "type": "analyze",  "transaction": {...} }
            { "type": "chat",     "message": "..." }
            { "type": "ping" }

        Server → Client:
            { "type": "analysis_result",  "data": {...} }
            { "type": "chat_response",    "message": "...", "transaction": {...} }
            { "type": "alert",            "level": "critical", "data": {...} }
            { "type": "pong" }
            { "type": "error",            "message": "..." }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = None
        self.group_name = None

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"fraud_{self.session_id}"

        # Join session group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        logger.info(f"WS connected: session={self.session_id}")

        # Send welcome
        await self.send_json({
            "type": "connected",
            "session_id": self.session_id,
            "message": "🔒 Fraud Detection System connected. Send a transaction for analysis.",
            "timestamp": timezone.now().isoformat(),
        })

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WS disconnected: session={self.session_id}, code={close_code}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            msg_type = data.get("type", "")

            if msg_type == "analyze":
                await self._handle_analyze(data.get("transaction", {}))
            elif msg_type == "chat":
                await self._handle_chat(data.get("message", ""))
            elif msg_type == "ping":
                await self.send_json({"type": "pong", "timestamp": timezone.now().isoformat()})
            else:
                await self.send_json({"type": "error", "message": f"Unknown message type: {msg_type}"})

        except json.JSONDecodeError:
            await self.send_json({"type": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.exception(f"WS receive error: {e}")
            await self.send_json({"type": "error", "message": str(e)})

    async def _handle_analyze(self, transaction_data: dict):
        """Run ML analysis and stream results back."""
        await self.send_json({"type": "analyzing", "message": "Running fraud analysis..."})

        try:
            # Run analysis in thread pool (CPU-bound)
            result = await asyncio.get_event_loop().run_in_executor(
                None, self._run_analysis, transaction_data
            )

            # Save to DB
            txn = await self._save_transaction(transaction_data, result)
            result["transaction_id"] = str(txn.id)

            await self.send_json({"type": "analysis_result", "data": result})

            # Trigger alert if high/critical risk
            if result["risk_level"] in ("high", "critical"):
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "fraud_alert",
                        "level": result["risk_level"],
                        "transaction_id": result["transaction_id"],
                        "risk_score": result["risk_score"],
                        "message": f"🚨 {result['risk_level'].upper()} RISK transaction detected!",
                    },
                )

        except Exception as e:
            logger.exception("Analysis failed in WS consumer")
            await self.send_json({"type": "error", "message": f"Analysis error: {str(e)}"})

    async def _handle_chat(self, message: str):
        """Handle a chat message from the user."""
        if not message.strip():
            return

        # Save user message
        await self._save_chat_message("user", message, None)

        # Get history
        history = await self._get_chat_history()

        # Generate response in thread pool
        engine = FraudChatEngine()
        response_data = await asyncio.get_event_loop().run_in_executor(
            None, engine.respond, message, history, self.session_id
        )

        # Save assistant response
        txn_id = response_data.get("transaction_id")
        txn = await self._get_transaction(txn_id) if txn_id else None
        await self._save_chat_message("assistant", response_data["message"], txn)

        payload = {
            "type": "chat_response",
            "message": response_data["message"],
            "suggestions": response_data.get("suggestions", []),
        }
        if txn:
            payload["transaction"] = await self._serialize_transaction(txn)

        await self.send_json(payload)

    # ——— Channel layer message handlers ———

    async def fraud_alert(self, event):
        """Broadcast fraud alert to all clients in this session group."""
        await self.send_json({
            "type": "alert",
            "level": event["level"],
            "transaction_id": event.get("transaction_id"),
            "risk_score": event.get("risk_score"),
            "message": event.get("message"),
            "timestamp": timezone.now().isoformat(),
        })

    # ——— Helpers ———

    def _run_analysis(self, transaction_data: dict) -> dict:
        service = FraudDetectionService()
        return service.analyze(transaction_data)

    @database_sync_to_async
    def _save_transaction(self, data: dict, result: dict):
        return Transaction.objects.create(
            session_id=self.session_id,
            risk_score=result["risk_score"],
            risk_level=result["risk_level"],
            is_fraud=result["is_fraud"],
            confidence=result["confidence"],
            explanation=result["explanation"],
            shap_values=result["shap_values"],
            top_factors=result["top_factors"],
            **{k: v for k, v in data.items() if k != "session_id"},
        )

    @database_sync_to_async
    def _save_chat_message(self, role: str, content: str, transaction):
        return ChatMessage.objects.create(
            session_id=self.session_id,
            role=role,
            content=content,
            transaction=transaction,
        )

    @database_sync_to_async
    def _get_chat_history(self):
        return list(
            ChatMessage.objects.filter(session_id=self.session_id)
            .order_by("created_at")
            .values("role", "content")
        )

    @database_sync_to_async
    def _get_transaction(self, txn_id):
        try:
            return Transaction.objects.get(id=txn_id)
        except Transaction.DoesNotExist:
            return None

    @database_sync_to_async
    def _serialize_transaction(self, txn):
        from .serializers import TransactionResultSerializer
        return TransactionResultSerializer(txn).data

    async def send_json(self, data: dict):
        await self.send(text_data=json.dumps(data, default=str))
