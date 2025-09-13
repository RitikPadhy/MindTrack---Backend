import os
from firebase_admin import credentials, firestore, initialize_app

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cred_path = os.path.join(BASE_DIR, "config/firebase-service-account.json")

cred = credentials.Certificate(cred_path)
initialize_app(cred)

db = firestore.client()