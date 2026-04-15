from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # All sensor API endpoints
    path('api/', include('sensors.urls')),
]