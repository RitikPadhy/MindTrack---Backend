import firebase_admin
from firebase_admin import credentials, firestore

# Path to secret file provided by Render
cred_path = "/etc/secrets/firebase-service-account.json"

cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

db = firestore.client()