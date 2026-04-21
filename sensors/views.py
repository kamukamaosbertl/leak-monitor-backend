from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404

from .models import LeakEvent, Alert
from .serializers import LeakEventSerializer, AlertSerializer


class LeakEventCreateView(APIView):
    """
    POST /api/leaks/
    ESP32 calls this every 20 sec when leak is detected.
    Saves the leak event to PostgreSQL.
    """
    def post(self, request):
        serializer = LeakEventSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {'message': 'Leak event saved.', 'data': serializer.data},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LeakEventListView(APIView):
    """
    GET /api/leaks/history/
    Flutter calls this to fetch past leak events.
    """
    def get(self, request):
        events = LeakEvent.objects.all()[:50]  # last 50 events
        serializer = LeakEventSerializer(events, many=True)
        return Response(serializer.data)


class AlertListView(APIView):
    """
    GET /api/alerts/
    Flutter calls this to fetch alerts.
    """
    def get(self, request):
        alerts = Alert.objects.filter(is_dismissed=False)[:50]
        serializer = AlertSerializer(alerts, many=True)
        return Response(serializer.data)


class MarkAlertReadView(APIView):
    """
    PATCH /api/alerts/<id>/read/
    Marks one alert as read.
    """
    def patch(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)
        alert.is_read = True
        alert.save()
        return Response({'message': 'Alert marked as read'}, status=status.HTTP_200_OK)


class DismissAlertView(APIView):
    """
    PATCH /api/alerts/<id>/dismiss/
    Dismisses one alert.
    """
    def patch(self, request, pk):
        alert = get_object_or_404(Alert, pk=pk)
        alert.is_dismissed = True
        alert.save()
        return Response({'message': 'Alert dismissed'}, status=status.HTTP_200_OK)


class MarkAllAlertsReadView(APIView):
    """
    PATCH /api/alerts/mark-all-read/
    Marks all unread alerts as read.
    """
    def patch(self, request):
        Alert.objects.filter(is_read=False).update(is_read=True)
        return Response({'message': 'All alerts marked as read'}, status=status.HTTP_200_OK)