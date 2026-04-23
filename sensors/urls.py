from django.urls import path
from .views import (
    LeakEventCreateView,
    LeakEventListView,

    # NEW: history actions
    LeakEventDetailView,
    LeakEventClearView,

    # Alerts
    AlertListView,
    MarkAlertReadView,
    DismissAlertView,
    MarkAllAlertsReadView,

    # Settings
    AlertSettingsView,

    # Device Token
    RegisterDeviceTokenView,
)

urlpatterns = [
    # ───── EXISTING (DO NOT TOUCH) ─────
    path('leaks/', LeakEventCreateView.as_view(), name='leak-create'),
    path('leaks/history/', LeakEventListView.as_view(), name='leak-history'),

    # ───── NEW: HISTORY ACTIONS ─────
    path('leaks/history/<int:pk>/', LeakEventDetailView.as_view(), name='leak-history-detail'),
    path('leaks/history/clear/', LeakEventClearView.as_view(), name='leak-history-clear'),

    # ───── ALERTS ─────
    path('alerts/', AlertListView.as_view(), name='alerts-list'),
    path('alerts/<int:pk>/read/', MarkAlertReadView.as_view(), name='alert-read'),
    path('alerts/<int:pk>/dismiss/', DismissAlertView.as_view(), name='alert-dismiss'),
    path('alerts/mark-all-read/', MarkAllAlertsReadView.as_view(), name='alerts-mark-all-read'),

    # ───── SETTINGS ─────
    path('settings/alerts/', AlertSettingsView.as_view(), name='alert-settings'),

    # ───── DEVICE TOKEN ─────
    path('device-token/', RegisterDeviceTokenView.as_view(), name='device-token'),
]