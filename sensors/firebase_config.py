import json
import os
import firebase_admin
from firebase_admin import credentials

if not firebase_admin._apps:
    service_account_info = json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT_JSON"])
    cred = credentials.Certificate(service_account_info)
    firebase_admin.initialize_app(cred)