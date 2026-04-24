import json
import os
import firebase_admin
import firebase_admin
from firebase_admin import credentials
import os
import json
from django.conf import settings


if not firebase_admin._apps:
    try:
        # ✅ Try to use ENV (Render / production)
        service_account_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")

        if service_account_json:
            service_account_info = json.loads(service_account_json)
            cred = credentials.Certificate(service_account_info)
        else:
            raise ValueError("No FIREBASE_SERVICE_ACCOUNT_JSON found")

    except Exception:
        # ✅ Fallback for LOCAL development (use JSON file)
        cred = credentials.Certificate(
            settings.BASE_DIR / "water-ab382-firebase-adminsdk-fbsvc-021f046960.json"
        )

    firebase_admin.initialize_app(cred)