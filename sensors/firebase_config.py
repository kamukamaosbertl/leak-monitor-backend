import json
import os

import firebase_admin
from django.conf import settings
from firebase_admin import credentials


if not firebase_admin._apps:
    service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

    if service_account_json:
        # Production/Render: Firebase credentials come from environment variable
        service_account_info = json.loads(service_account_json)
        cred = credentials.Certificate(service_account_info)

    else:
        # Local development: Firebase credentials come from a JSON file
        local_firebase_file = settings.BASE_DIR / "water-ab382-firebase-adminsdk-fbsvc-021f046960.json"

        if not local_firebase_file.exists():
            raise FileNotFoundError(
                f"Firebase service account file not found: {local_firebase_file}"
            )

        cred = credentials.Certificate(local_firebase_file)

    firebase_admin.initialize_app(cred)