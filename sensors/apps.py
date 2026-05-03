from django.apps import AppConfig
from django.conf import settings


class SensorsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sensors'

    def ready(self):
        """
        Only load Firebase when enabled.

        Prevents crashes when Firebase credentials are missing locally.
        """
        if getattr(settings, "ENABLE_FIREBASE", False):
            import sensors.firebase_config