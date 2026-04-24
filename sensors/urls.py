from django.urls import path
from .views import (
    LeakEventCreateView,
    LeakEventListView,

    # History actions
    LeakEventDetailView,
    LeakEventClearView,

    # Alerts
    AlertListView,
    MarkAlertReadView,
    DismissAlertView,
    MarkAllAlertsReadView,

    # Alert responses
    AlertResponseCreateView,
    AlertResponseListView,

    # Maintenance
    MaintenanceCallView,
    MaintenanceRequestListView,
    MaintenanceRequestDetailView,

    # Reports
    LatestReportView,

    # Admin
    AdminSummaryView,

    # Settings
    AlertSettingsView,

    # Device Token
    RegisterDeviceTokenView,
)

urlpatterns = [
    # ───── LEAKS ─────
    path('leaks/', LeakEventCreateView.as_view(), name='leak-create'),
    path('leaks/history/', LeakEventListView.as_view(), name='leak-history'),
    path('leaks/history/<int:pk>/', LeakEventDetailView.as_view(), name='leak-history-detail'),
    path('leaks/history/clear/', LeakEventClearView.as_view(), name='leak-history-clear'),

    # ───── ALERTS ─────
    path('alerts/', AlertListView.as_view(), name='alerts-list'),
    path('alerts/<int:pk>/read/', MarkAlertReadView.as_view(), name='alert-read'),
    path('alerts/<int:pk>/dismiss/', DismissAlertView.as_view(), name='alert-dismiss'),
    path('alerts/mark-all-read/', MarkAllAlertsReadView.as_view(), name='alerts-mark-all-read'),

    # ───── ALERT RESPONSES ─────
    path('alerts/<int:pk>/respond/', AlertResponseCreateView.as_view(), name='alert-response-create'),
    path('alerts/responses/', AlertResponseListView.as_view(), name='alert-responses-list'),

    # ───── MAINTENANCE ─────
    path('maintenance/call/', MaintenanceCallView.as_view(), name='maintenance-call'),
    path('maintenance/requests/', MaintenanceRequestListView.as_view(), name='maintenance-requests'),
    path('maintenance/requests/<int:pk>/', MaintenanceRequestDetailView.as_view(), name='maintenance-request-detail'),

    # ───── REPORTS ─────
    path('reports/latest/', LatestReportView.as_view(), name='latest-report'),

    # ───── ADMIN ─────
    path('admin/summary/', AdminSummaryView.as_view(), name='admin-summary'),

    # ───── SETTINGS ─────
    path('settings/alerts/', AlertSettingsView.as_view(), name='alert-settings'),

    # ───── DEVICE TOKEN ─────
    path('device-token/', RegisterDeviceTokenView.as_view(), name='device-token'),
]