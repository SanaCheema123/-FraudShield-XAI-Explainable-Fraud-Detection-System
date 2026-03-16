# fraud_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("health/", views.health_check, name="health"),
    path("analyze/", views.AnalyzeTransactionView.as_view(), name="analyze"),
    path("chat/", views.ChatView.as_view(), name="chat"),
    path("transactions/", views.TransactionHistoryView.as_view(), name="transactions"),
    path("transactions/<uuid:pk>/", views.TransactionDetailView.as_view(), name="transaction-detail"),
    path("stats/", views.DashboardStatsView.as_view(), name="stats"),
    path("alerts/", views.AlertRuleView.as_view(), name="alerts"),
]
