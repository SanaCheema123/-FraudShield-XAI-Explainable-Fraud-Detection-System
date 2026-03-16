# 🔒 FraudShield XAI — Explainable Fraud Detection System

A production-ready fraud detection chatbot with:
- **Django REST API + WebSocket** real-time service
- **SHAP explainability** (per-prediction feature attribution)
- **Random Forest** classifier with class-imbalance handling
- **Chat interface** with NL transaction parsing
- **Live streaming** analysis via Django Channels + Redis

---

## Architecture

```
┌─────────────────────────────────────────┐
│           React Frontend                │
│   Chat UI │ Transaction Form │ Dashboard│
└──────────────────┬──────────────────────┘
                   │ HTTP / WebSocket
┌──────────────────▼──────────────────────┐
│         Django + Daphne (ASGI)          │
│                                         │
│  REST API (/api/*)                      │
│  ├── POST /api/analyze/                 │
│  ├── POST /api/chat/                    │
│  ├── GET  /api/transactions/            │
│  ├── GET  /api/stats/                   │
│  └── GET  /api/health/                  │
│                                         │
│  WebSocket (/ws/fraud/<session_id>/)    │
│  ├── type: "analyze" → ML result        │
│  ├── type: "chat"    → assistant reply  │
│  └── type: "ping"    → pong             │
└──────────────────┬──────────────────────┘
        ┌──────────┴──────────┐
        ▼                     ▼
┌───────────────┐    ┌─────────────────────┐
│  SQLite / PG  │    │  Redis Channel Layer │
│  (Transactions│    │  (WS Groups/Alerts)  │
│   Chat logs)  │    └─────────────────────┘
└───────────────┘
        │
        ▼
┌───────────────────────────────────────┐
│        ML Service (Python)            │
│  RandomForestClassifier (sklearn)     │
│  SHAP TreeExplainer                   │
│  → risk_score, shap_values, explanation│
└───────────────────────────────────────┘
```

---

## Quick Start

### Prerequisites
- Python 3.10+
- Redis (for WebSocket channels)
- Node.js 18+ (for React frontend)

### Backend Setup

```bash
cd fraud_detection_system
pip install -r requirements.txt

cd backend
python manage.py makemigrations
python manage.py migrate

# Pre-train the ML model
python -c "from fraud_app.ml_service import FraudDetectionService; FraudDetectionService()"

# Start with Daphne (ASGI — supports both HTTP and WebSocket)
daphne -p 8000 core.asgi:application
```

Or use the one-command setup:
```bash
python setup.py
```

### Environment Variables (`.env`)
```
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
REDIS_URL=redis://127.0.0.1:6379
```

---

## API Reference

### `POST /api/analyze/`
Analyze a transaction for fraud risk.

**Request:**
```json
{
  "amount": 3500.00,
  "hour_of_day": 3,
  "day_of_week": 1,
  "merchant_category_encoded": 9,
  "transaction_velocity_1h": 6,
  "transaction_velocity_24h": 18,
  "avg_transaction_amount": 250.0,
  "amount_deviation": 4.2,
  "is_international": true,
  "is_online": true,
  "card_age_days": 45,
  "account_balance_ratio": 0.88,
  "session_id": "user-session-abc"
}
```

**Response:**
```json
{
  "risk_score": 0.9234,
  "risk_level": "critical",
  "is_fraud": true,
  "confidence": 0.9234,
  "explanation": "🚨 CRITICAL ALERT — 92.3% confidence...",
  "shap_values": [
    {
      "feature": "amount",
      "label": "Transaction Amount ($)",
      "value": 3500.0,
      "shap_value": 0.2841,
      "direction": "increases_risk",
      "magnitude": 0.2841
    }
    ...
  ],
  "top_factors": ["Transaction Amount ($)", "Hour of Day", ...],
  "transaction_id": "uuid-here"
}
```

### `WebSocket: ws://localhost:8000/ws/fraud/<session_id>/`

**Send (analyze):**
```json
{ "type": "analyze", "transaction": { "amount": 500, ... } }
```

**Receive (result):**
```json
{ "type": "analysis_result", "data": { "risk_score": 0.12, ... } }
```

**Send (chat):**
```json
{ "type": "chat", "message": "Check $3,500 international transfer at 3am" }
```

---

## ML Model Details

| Setting | Value |
|---------|-------|
| Algorithm | Random Forest (sklearn) |
| Trees | 100 |
| Max depth | 8 |
| Class weights | {legitimate: 1, fraud: 10} |
| Explainability | SHAP TreeExplainer (exact) |
| Features | 12 transaction features |

### Replacing Synthetic Data
Edit `fraud_app/ml_service.py` → `_generate_synthetic_data()` and replace with your CSV:
```python
def _generate_synthetic_data():
    return pd.read_csv("your_fraud_dataset.csv")
```
Then delete `fraud_app/ml/fraud_model.joblib` and restart to retrain.

---

## File Structure

```
fraud_detection_system/
├── requirements.txt
├── setup.py                    # One-command setup
├── backend/
│   ├── core/
│   │   ├── settings.py         # Django settings + Channels config
│   │   ├── urls.py             # Root URL routing
│   │   ├── asgi.py             # ASGI: HTTP + WebSocket
│   │   └── wsgi.py
│   └── fraud_app/
│       ├── models.py           # Transaction, ChatMessage, AlertRule
│       ├── views.py            # REST API views
│       ├── serializers.py      # DRF serializers
│       ├── consumers.py        # WebSocket consumer
│       ├── chat_engine.py      # NL chat + transaction parsing
│       ├── ml_service.py       # RandomForest + SHAP (SINGLETON)
│       ├── routing.py          # WebSocket URL routing
│       ├── urls.py             # REST URL routing
│       └── ml/
│           ├── fraud_model.joblib   # Trained model (auto-generated)
│           └── scaler.joblib        # Feature scaler (auto-generated)
```

---

## Connecting the React Frontend

Set your API base URL in the frontend:
```js
const API_BASE = "http://localhost:8000/api";
const WS_URL   = "ws://localhost:8000/ws/fraud/my-session/";
```

Replace `mockAnalyze()` and `mockChat()` with real `fetch()` calls to the Django API.

---

## Production Deployment

1. Set `DEBUG=False` and configure `ALLOWED_HOSTS`
2. Switch SQLite → PostgreSQL
3. Use Redis Cloud or ElastiCache for channels
4. Run behind Nginx → Daphne
5. Retrain model on real fraud data
6. Add JWT authentication to API and WebSocket consumers
