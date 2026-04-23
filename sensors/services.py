# sensors/services.py

from firebase_admin import messaging
from .models import DeviceToken


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
            print(f"Sent to {token}")
        except Exception as e:
            print(f"Error sending to {token}: {e}")