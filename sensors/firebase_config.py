# sensors/firebase_config.py

import firebase_admin
from firebase_admin import credentials

from core.settings import BASE_DIR

if not firebase_admin._apps:
    cred = credentials.Certificate(BASE_DIR/"water-ab382-firebase-adminsdk-fbsvc-021f046960.json")
    firebase_admin.initialize_app(cred)