import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from firebase_admin import auth as firebase_auth, firestore
from app.core.firebase import db
from dotenv import load_dotenv
from app.routes.routines import create_patient_routine
from datetime import datetime, timezone

router = APIRouter()

load_dotenv()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# ---------- Pydantic Models ----------
class SignupRequest(BaseModel):
    uid: str
    email: EmailStr
    password: str
    role: str
    gender: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LogoutRequest(BaseModel):
    uid: str

class SignupResponse(BaseModel):
    uid: str
    email: EmailStr
    role: str
    doc_id: str

# ---------- Dependency: Verify Bearer Token ----------
def verify_bearer_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

# ---------- Signup ----------
@router.post("/signup", response_model=SignupResponse)
def signup(request: SignupRequest):
    try:
        # Limit max users
        users_ref = db.collection("users").stream()
        total_users = sum(1 for _ in users_ref)
        if total_users >= 33:
            raise HTTPException(status_code=400, detail="User limit reached (max 33 users allowed)")

        # Ensure UID and email uniqueness
        try:
            firebase_auth.get_user(request.uid)
            raise HTTPException(status_code=400, detail="UID already exists")
        except firebase_auth.UserNotFoundError:
            pass

        try:
            firebase_auth.get_user_by_email(request.email)
            raise HTTPException(status_code=400, detail="Email already exists")
        except firebase_auth.UserNotFoundError:
            pass

        # Create Firebase user
        user = firebase_auth.create_user(uid=request.uid, email=request.email, password=request.password)

        # Add user to Firestore
        doc_ref = db.collection("users").add({
            "uid": request.uid,
            "email": request.email,
            "role": request.role,
            "gender": request.gender,  # 👈 Added
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        doc_id = doc_ref[1].id

        # Automatically create daily routine if Patient
        if request.role.lower() == "patient":
            created_at = datetime.now(timezone.utc)
            create_patient_routine(request.uid, request.email, request.role, created_at)

        return {
            "uid": user.uid,
            "email": request.email,
            "role": request.role,
            "doc_id": doc_id
        }

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ---------- Login ----------
@router.post("/login")
def login(request: LoginRequest):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {
        "email": request.email,
        "password": request.password,
        "returnSecureToken": True,
    }
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.json())

    data = r.json()
    return {
        "access_token": data["idToken"],
        "token_type": "bearer",
        "refresh_token": data.get("refreshToken"),
        "expires_in": data.get("expiresIn"),
        "uid": data.get("localId")
    }

# ---------- Protected Route ----------
@router.get("/me")
def get_profile(user=Depends(verify_bearer_token)):
    return {"uid": user["uid"], "email": user.get("email")}

# ---------- Delete User (Admin Only) ----------
@router.delete("/delete-user/{uid}")
def delete_user(uid: str, admin_user=Depends(verify_bearer_token)):
    try:
        # Verify admin
        admin_doc = db.collection("users").where("uid", "==", admin_user["uid"]).limit(1).get()
        if not admin_doc or len(admin_doc) == 0:
            raise HTTPException(status_code=403, detail="Admin user record not found")

        admin_data = admin_doc[0].to_dict()
        if admin_data.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Only Admins can delete users")

        # Delete Firebase user
        try:
            firebase_auth.delete_user(uid)
        except firebase_auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="User not found in Firebase Auth")

        # Delete Firestore document(s)
        target_docs = db.collection("users").where("uid", "==", uid).stream()
        deleted = False
        for doc in target_docs:
            doc.reference.delete()
            deleted = True

        if not deleted:
            raise HTTPException(status_code=404, detail="User not found in Firestore")

        return {"message": f"User {uid} deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))