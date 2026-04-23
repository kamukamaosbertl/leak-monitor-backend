from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from firebase_admin import messaging

from .models import LeakEvent, Alert, AlertSettings, DeviceToken
from .serializers import (
    LeakEventSerializer,
    AlertSerializer,
    AlertSettingsSerializer,
)


def send_push_notification(title, body):
    tokens = DeviceToken.objects.filter(is_active=True).values_list("token", flat=True)

    for token in tokens:
        try:
            message = messaging.Message(
                token=token,
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
            )
            messaging.send(message)
            print(f"Notification sent to {token}")
        except Exception as e:
            print(f"Error sending to {token}: {e}")


class RegisterDeviceTokenView(APIView):
    """
    POST /api/device-token/
    Flutter sends FCM token here so Django can store it.
    """
    def post(self, request):
        token = request.data.get("token")
        device_id = request.data.get("device_id")
        platform = request.data.get("platform")

        if not token:
            return Response(
                {"error": "token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obj, created = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "device_id": device_id,
                "platform": platform,
                "is_active": True,
            }
        )

        return Response(
            {
                "message": "Device token saved successfully.",
                "created": created,
                "token_id": obj.id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class LeakEventCreateView(APIView):
    """
    POST /api/leaks/
    ESP32 calls this when leak data is sent directly through REST.
    Saves the leak event to PostgreSQL.
    Also creates an alert and sends push notification when needed.
    """
    def post(self, request):
        serializer = LeakEventSerializer(data=request.data)

        if serializer.is_valid():
            leak_event = serializer.save()
            alert = None

            if leak_event.status == "critical":
                alert = Alert.objects.create(
                    device_id=leak_event.device_id,
                    title="🚨 Critical Water Leak Detected",
                    message=f"Critical leak detected at {leak_event.location}. Immediate action is required.",
                    location=leak_event.location,
                    severity="critical",
                    timestamp=leak_event.timestamp,
                )
                send_push_notification(alert.title, alert.message)

            elif leak_event.status in ["warning", "leak_detected"]:
                alert = Alert.objects.create(
                    device_id=leak_event.device_id,
                    title="⚠️ Water Leak Detected",
                    message=f"Leak detected at {leak_event.location}. Please check your system.",
                    location=leak_event.location,
                    severity="warning",
                    timestamp=leak_event.timestamp,
                )
                send_push_notification(alert.title, alert.message)

            return Response(
                {
                    "message": "Leak event saved.",
                    "data": serializer.data,
                    "alert_created": alert.id if alert else None,
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LeakEventListView(APIView):
    """
    GET /api/leaks/history/
    Flutter calls this to fetch past leak events.
    Returns the most recent 100 events.
    """
    def get(self, request):
        events = LeakEvent.objects.all()[:100]
        serializer = LeakEventSerializer(events, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class LeakEventDetailView(APIView):
    """
    PATCH /api/leaks/history/<id>/
    Update one history record.

    DELETE /api/leaks/history/<id>/
    Delete one history record.
    """
    def patch(self, request, pk):
        event = get_object_or_404(LeakEvent, pk=pk)
        serializer = LeakEventSerializer(
            event,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Leak event updated successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        event = get_object_or_404(LeakEvent, pk=pk)
        event.delete()

        return Response(
            {"message": "Leak event deleted successfully."},
            status=status.HTTP_200_OK,
        )


class LeakEventClearView(APIView):
    """
    DELETE /api/leaks/history/clear/
    Deletes all history records.
    """
    def delete(self, request):
        deleted_count, _ = LeakEvent.objects.all().delete()

        return Response(
            {
                "message": "All leak history deleted successfully.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


class AlertListView(APIView):
    """
    GET /api/alerts/
    Flutter calls this to fetch alerts.
    """
    def get(self, request):
        alerts = Alert.objects.filter(is_dismissed=False)[:50]
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class MarkAlertReadView(APIView):
    """
    PATCH /api/alerts/<id>/read/
    Marks one alert as read.
    """
    def patch(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)
        alert.is_read = True
        alert.save()

        return Response(
            {"message": "Alert marked as read"},
            status=status.HTTP_200_OK,
        )


class DismissAlertView(APIView):
    """
    PATCH /api/alerts/<id>/dismiss/
    Dismisses one alert.
    """
    def patch(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)
        alert.is_dismissed = True
        alert.save()

        return Response(
            {"message": "Alert dismissed"},
            status=status.HTTP_200_OK,
        )


class MarkAllAlertsReadView(APIView):
    """
    PATCH /api/alerts/mark-all-read/
    Marks all unread alerts as read.
    """
    def patch(self, request):
        Alert.objects.filter(is_read=False).update(is_read=True)

        return Response(
            {"message": "All alerts marked as read"},
            status=status.HTTP_200_OK,
        )


class AlertSettingsView(APIView):
    """
    GET /api/settings/alerts/
    Returns the current global alert threshold settings.

    PATCH /api/settings/alerts/
    Updates the global alert threshold settings.
    """
    def get(self, request):
        settings_obj, _ = AlertSettings.objects.get_or_create(id=1)
        serializer = AlertSettingsSerializer(settings_obj)

        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        settings_obj, _ = AlertSettings.objects.get_or_create(id=1)
        serializer = AlertSettingsSerializer(
            settings_obj,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "message": "Alert settings updated successfully.",
                    "data": serializer.data,
                },
                status=status.HTTP_200_OK,
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)