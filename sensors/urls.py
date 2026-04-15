from django.urls import path
from .views import LeakEventCreateView, LeakEventListView

urlpatterns = [
    # ESP32 posts leak events here
    path('leaks/', LeakEventCreateView.as_view(), name='leak-create'),
    # Flutter fetches leak history here
    path('leaks/history/', LeakEventListView.as_view(), name='leak-history'),
]