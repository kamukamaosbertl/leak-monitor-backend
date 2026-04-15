import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import sensors.routing

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = ProtocolTypeRouter({
    # Normal HTTP requests
    'http': get_asgi_application(),
    # WebSocket requests
    'websocket': AuthMiddlewareStack(
        URLRouter(
            sensors.routing.websocket_urlpatterns
        )
    ),
})