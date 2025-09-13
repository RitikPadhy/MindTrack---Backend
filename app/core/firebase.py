import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Load env vars from .env (for local dev)
load_dotenv()

# Get Firebase service account JSON from environment
cred_json = os.getenv("FIREBASE_CRED_JSON")

if not cred_json:
    raise ValueError("FIREBASE_CRED_JSON not set in environment")

# Convert JSON string into dict
cred_dict = json.loads(cred_json)

# Initialize Firebase app only once
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()