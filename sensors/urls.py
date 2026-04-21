from django.urls import path
from .views import (
    LeakEventCreateView,
    LeakEventListView,

    # NEW imports for alerts
    AlertListView,
    MarkAlertReadView,
    DismissAlertView,
    MarkAllAlertsReadView,
)

urlpatterns = [
    # ───── EXISTING (DO NOT TOUCH) ─────
    path('leaks/', LeakEventCreateView.as_view(), name='leak-create'),
    path('leaks/history/', LeakEventListView.as_view(), name='leak-history'),

    # ───── NEW (ADDED FOR ALERTS) ─────
    path('alerts/', AlertListView.as_view(), name='alerts-list'),
    path('alerts/<int:pk>/read/', MarkAlertReadView.as_view(), name='alert-read'),
    path('alerts/<int:pk>/dismiss/', DismissAlertView.as_view(), name='alert-dismiss'),
    path('alerts/mark-all-read/', MarkAllAlertsReadView.as_view(), name='alerts-mark-all-read'),
]