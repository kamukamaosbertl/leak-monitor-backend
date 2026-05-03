from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


# Simple root endpoint to confirm API is running
def api_root(request):
    return JsonResponse({
        "message": "Leak Monitor API running"
    })


urlpatterns = [
    # Admin panel (only for you)
    path('admin/', admin.site.urls),

    # Root check
    path('', api_root),

    # Authentication (login, register, logout)
    path('api/auth/', include('accounts.urls')),

    # Sensor + leakage endpoints
    path('api/', include('sensors.urls')),
]