# fraud_app/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/fraud/(?P<session_id>[^/]+)/$", consumers.FraudAnalysisConsumer.as_asgi()),
]
