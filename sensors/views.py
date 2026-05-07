import csv
from io import BytesIO
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Count

from firebase_admin import messaging

from .models import (
    LeakEvent,
    Alert,
    AlertSettings,
    DeviceToken,
    AlertResponse,
    MaintenanceRequest,
)
from .serializers import (
    LeakEventSerializer,
    AlertSerializer,
    AlertSettingsSerializer,
    AlertResponseSerializer,
    MaintenanceRequestSerializer,
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


class AlertResponseCreateView(APIView):
    """
    POST /api/alerts/<id>/respond/

    Records who responded to an alert.

    Expected body:
    {
        "user_id": 1,
        "action": "acknowledged" | "responding" | "resolved" | "dismissed",
        "notes": "Optional notes"
    }
    """
    def post(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)

        user_id = request.data.get("user_id")
        action = request.data.get("action")
        notes = request.data.get("notes", "")

        if not user_id:
            return Response(
                {"error": "user_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not action:
            return Response(
                {"error": "action is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_actions = ["acknowledged", "responding", "resolved", "dismissed"]
        if action not in valid_actions:
            return Response(
                {"error": f"Invalid action. Use one of: {valid_actions}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = get_object_or_404(User, pk=user_id)

        response = AlertResponse.objects.create(
            alert=alert,
            user=user,
            action=action,
            notes=notes,
        )

        if action in["acknowledged","responding"] :
            alert.is_read = True
            alert.save()

        if action in[ "resolved","dismissed"]:
            alert.is_read = True
            alert.is_dismissed = True
            alert.save()

        serializer = AlertResponseSerializer(response)

        return Response(
            {
                "message": "Alert response recorded successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class AlertResponseListView(APIView):
    """
    GET /api/alerts/responses/

    Admin uses this to see who responded to alerts.
    """
    def get(self, request):
        responses = AlertResponse.objects.select_related("alert", "user").all()[:100]
        serializer = AlertResponseSerializer(responses, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class MaintenanceCallView(APIView):
    """
    POST /api/maintenance/call/

    Creates a technician/maintenance request.

    Expected body:
    {
        "device_id": "sensor-001",
        "location": "Kitchen",
        "user_id": 1,
        "reason": "Critical leak detected",
        "severity": "critical"
    }
    """
    def post(self, request):
        device_id = request.data.get("device_id")
        location = request.data.get("location")
        user_id = request.data.get("user_id")
        reason = request.data.get("reason", "Leak detected")
        severity = request.data.get("severity", "critical")

        if not device_id:
            return Response(
                {"error": "device_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not location:
            return Response(
                {"error": "location is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        requested_by = None
        if user_id:
            requested_by = get_object_or_404(User, pk=user_id)

        maintenance_request = MaintenanceRequest.objects.create(
            device_id=device_id,
            location=location,
            requested_by=requested_by,
            reason=reason,
            severity=severity,
            status="pending",
        )

        serializer = MaintenanceRequestSerializer(maintenance_request)

        return Response(
            {
                "message": "Technician request created successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_201_CREATED,
        )


class MaintenanceRequestListView(APIView):
    """
    GET /api/maintenance/requests/

    Admin uses this to view all technician requests.
    """
    def get(self, request):
        requests = MaintenanceRequest.objects.select_related("requested_by").all()[:100]
        serializer = MaintenanceRequestSerializer(requests, many=True)

        return Response(serializer.data, status=status.HTTP_200_OK)


class MaintenanceRequestDetailView(APIView):
    """
    PATCH /api/maintenance/requests/<id>/

    Updates maintenance request status.

    Expected body:
    {
        "status": "assigned" | "in_progress" | "completed"
    }
    """
    def patch(self, request, pk):
        maintenance_request = get_object_or_404(MaintenanceRequest, pk=pk)

        new_status = request.data.get("status")
        valid_statuses = ["pending", "assigned", "in_progress", "completed"]

        if not new_status:
            return Response(
                {"error": "status is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status not in valid_statuses:
            return Response(
                {"error": f"Invalid status. Use one of: {valid_statuses}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        maintenance_request.status = new_status
        maintenance_request.save()

        serializer = MaintenanceRequestSerializer(maintenance_request)

        return Response(
            {
                "message": "Maintenance request updated successfully.",
                "data": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class LatestReportView(APIView):
    """
    GET /api/reports/latest/

    Generates a simple latest incident report from existing data.
    """
    def get(self, request):
        latest_event = LeakEvent.objects.first()

        if not latest_event:
            return Response(
                {"message": "No leak events available for report."},
                status=status.HTTP_404_NOT_FOUND,
            )

        related_alerts = Alert.objects.filter(
            device_id=latest_event.device_id,
            location=latest_event.location,
        )[:5]

        report = {
            "report_type": "latest_leak_report",
            "generated_at": timezone.now(),
            "incident": {
                "id": latest_event.id,
                "device_id": latest_event.device_id,
                "location": latest_event.location,
                "status": latest_event.status,
                "flow_in": latest_event.flow_in,
                "flow_out": latest_event.flow_out,
                "delta": latest_event.delta,
                "duration_minutes": latest_event.duration_minutes,
                "water_lost": latest_event.water_lost,
                "money_lost": latest_event.money_lost,
                "timestamp": latest_event.timestamp,
                "created_at": latest_event.created_at,
            },
            "alerts": AlertSerializer(related_alerts, many=True).data,
        }

        return Response(report, status=status.HTTP_200_OK)
class LatestReportCSVView(APIView):
    """
    GET /api/reports/latest/csv/

    Exports the latest incident report as CSV.
    """
    def get(self, request):
        latest_event = LeakEvent.objects.first()

        if not latest_event:
            return Response(
                {"message": "No leak events available for report."},
                status=status.HTTP_404_NOT_FOUND,
            )

        related_alerts = Alert.objects.filter(
            device_id=latest_event.device_id,
            location=latest_event.location,
        )[:5]

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="latest_leak_report.csv"'

        writer = csv.writer(response)

        writer.writerow(["Latest Leak Report"])
        writer.writerow(["Generated At", timezone.now()])
        writer.writerow([])

        writer.writerow(["Incident Details"])
        writer.writerow(["ID", latest_event.id])
        writer.writerow(["Device ID", latest_event.device_id])
        writer.writerow(["Location", latest_event.location])
        writer.writerow(["Status", latest_event.status])
        writer.writerow(["Flow In", latest_event.flow_in])
        writer.writerow(["Flow Out", latest_event.flow_out])
        writer.writerow(["Delta", latest_event.delta])
        writer.writerow(["Duration Minutes", latest_event.duration_minutes])
        writer.writerow(["Water Lost", latest_event.water_lost])
        writer.writerow(["Money Lost", latest_event.money_lost])
        writer.writerow(["Timestamp", latest_event.timestamp])
        writer.writerow(["Created At", latest_event.created_at])
        writer.writerow([])

        writer.writerow(["Related Alerts"])
        writer.writerow(["ID", "Title", "Message", "Severity", "Location", "Timestamp"])

        for alert in related_alerts:
            writer.writerow([
                alert.id,
                alert.title,
                alert.message,
                alert.severity,
                alert.location,
                alert.timestamp,
            ])

        return response


class LatestReportPDFView(APIView):
    """
    GET /api/reports/latest/pdf/

    Exports the latest incident report as PDF.
    """
    def get(self, request):
        latest_event = LeakEvent.objects.first()

        if not latest_event:
            return Response(
                {"message": "No leak events available for report."},
                status=status.HTTP_404_NOT_FOUND,
            )

        related_alerts = Alert.objects.filter(
            device_id=latest_event.device_id,
            location=latest_event.location,
        )[:5]

        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)

        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(80, 800, "Latest Leak Report")

        pdf.setFont("Helvetica", 10)
        pdf.drawString(80, 780, f"Generated At: {timezone.now()}")

        y = 740

        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(80, y, "Incident Details")
        y -= 25

        pdf.setFont("Helvetica", 11)

        fields = [
            ("ID", latest_event.id),
            ("Device ID", latest_event.device_id),
            ("Location", latest_event.location),
            ("Status", latest_event.status),
            ("Flow In", latest_event.flow_in),
            ("Flow Out", latest_event.flow_out),
            ("Delta", latest_event.delta),
            ("Duration Minutes", latest_event.duration_minutes),
            ("Water Lost", latest_event.water_lost),
            ("Money Lost", latest_event.money_lost),
            ("Timestamp", latest_event.timestamp),
            ("Created At", latest_event.created_at),
        ]

        for label, value in fields:
            pdf.drawString(80, y, f"{label}: {value}")
            y -= 20

            if y < 80:
                pdf.showPage()
                y = 800
                pdf.setFont("Helvetica", 11)

        y -= 20
        pdf.setFont("Helvetica-Bold", 13)
        pdf.drawString(80, y, "Related Alerts")
        y -= 25

        pdf.setFont("Helvetica", 10)

        if related_alerts:
            for alert in related_alerts:
                pdf.drawString(80, y, f"Title: {alert.title}")
                y -= 16
                pdf.drawString(80, y, f"Severity: {alert.severity}")
                y -= 16
                pdf.drawString(80, y, f"Location: {alert.location}")
                y -= 16
                pdf.drawString(80, y, f"Timestamp: {alert.timestamp}")
                y -= 16
                pdf.drawString(80, y, f"Message: {alert.message}")
                y -= 30

                if y < 80:
                    pdf.showPage()
                    y = 800
                    pdf.setFont("Helvetica", 10)
        else:
            pdf.drawString(80, y, "No related alerts found.")

        pdf.showPage()
        pdf.save()

        buffer.seek(0)

        response = HttpResponse(buffer, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="latest_leak_report.pdf"'

        return response


class AdminSummaryView(APIView):
    """
    GET /api/admin/summary/

    Gives admin dashboard summary counts.
    """
    def get(self, request):
        today = timezone.now().date()

        total_alerts = Alert.objects.count()
        active_alerts = Alert.objects.filter(is_dismissed=False).count()
        critical_alerts = Alert.objects.filter(
            severity="critical",
            is_dismissed=False,
        ).count()

        total_responses = AlertResponse.objects.count()
        responses_today = AlertResponse.objects.filter(
            created_at__date=today,
        ).count()

        pending_maintenance = MaintenanceRequest.objects.filter(
            status="pending",
        ).count()

        maintenance_by_status = MaintenanceRequest.objects.values("status").annotate(
            count=Count("id")
        )

        return Response(
            {
                "total_alerts": total_alerts,
                "active_alerts": active_alerts,
                "critical_alerts": critical_alerts,
                "total_responses": total_responses,
                "responses_today": responses_today,
                "pending_maintenance": pending_maintenance,
                "maintenance_by_status": list(maintenance_by_status),
            },
            status=status.HTTP_200_OK,
        )
class ClearDismissedAlertsView(APIView):
    """
    DELETE /api/alerts/clear-dismissed/
    Deletes only dismissed alerts.
    Active alerts are kept.
    """
    def delete(self, request):
        deleted_count, _ = Alert.objects.filter(is_dismissed=True).delete()

        return Response(
            {
                "message": "Dismissed alerts cleared successfully.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


class ClearResolvedAlertResponsesView(APIView):
    """
    DELETE /api/alerts/responses/clear-resolved/
    Deletes only resolved/dismissed alert responses.
    Active response records like acknowledged/responding are kept.
    """
    def delete(self, request):
        deleted_count, _ = AlertResponse.objects.filter(
            action__in=["resolved", "dismissed"]
        ).delete()

        return Response(
            {
                "message": "Resolved/dismissed alert responses cleared successfully.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )


class ClearCompletedMaintenanceRequestsView(APIView):
    """
    DELETE /api/maintenance/requests/clear-completed/
    Deletes only completed maintenance requests.
    Pending, assigned, and in_progress requests are kept.
    """
    def delete(self, request):
        deleted_count, _ = MaintenanceRequest.objects.filter(
            status="completed"
        ).delete()

        return Response(
            {
                "message": "Completed maintenance requests cleared successfully.",
                "deleted_count": deleted_count,
            },
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
            
class ClearPlaceholderMaintenanceRequestsView(APIView):
    """
    DELETE /api/maintenance/requests/clear-placeholders/
    Deletes fake/placeholder maintenance requests.
    """
    def delete(self, request):
        deleted_count, _ = MaintenanceRequest.objects.filter(
            device_id="unknown",
            location="Waiting for sensor...",
        ).delete()

        return Response(
            {
                "message": "Placeholder maintenance requests cleared successfully.",
                "deleted_count": deleted_count,
            },
            status=status.HTTP_200_OK,
        )            

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)