from django.urls import re_path
from .consumers import SensorConsumer

websocket_urlpatterns = [
    # WebSocket URL
    # ESP32 and Flutter both connect to: ws://localhost:8000/ws/sensors/
    re_path(r'ws/sensors/$', SensorConsumer.as_asgi()),
]