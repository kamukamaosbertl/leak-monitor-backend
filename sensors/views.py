from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import LeakEvent
from .serializers import LeakEventSerializer

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
        events     = LeakEvent.objects.all()[:50]  # last 50 events
        serializer = LeakEventSerializer(events, many=True)
        return Response(serializer.data)