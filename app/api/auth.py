import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from firebase_admin import auth, firestore
from app.core.firebase import db
from dotenv import load_dotenv

router = APIRouter()

load_dotenv()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# ---------- Pydantic Models ----------
class SignupRequest(BaseModel):
    uid: str
    email: EmailStr
    password: str
    role: str

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

# ---------- Signup ----------
@router.post("/signup", response_model=SignupResponse)
def signup(request: SignupRequest):
    try:
        users_ref = db.collection("users").stream()
        total_users = sum(1 for _ in users_ref)
        if total_users >= 33:
            raise HTTPException(status_code=400, detail="User limit reached (max 33 users allowed)")

        try:
            auth.get_user(request.uid)
            raise HTTPException(status_code=400, detail="UID already exists")
        except auth.UserNotFoundError:
            pass

        try:
            auth.get_user_by_email(request.email)
            raise HTTPException(status_code=400, detail="Email already exists")
        except auth.UserNotFoundError:
            pass

        user = auth.create_user(uid=request.uid, email=request.email, password=request.password)

        doc_ref = db.collection("users").add({
            "uid": request.uid,
            "email": request.email,
            "role": request.role,
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        doc_id = doc_ref[1].id

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
    # Return token in JSON
    return {
        "idToken": data["idToken"],
        "refreshToken": data.get("refreshToken"),
        "expiresIn": data.get("expiresIn"),
        "localId": data.get("localId")
    }


# ---------- Verify Token ----------
def verify_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing access token in Authorization header")
    token = authorization.split(" ")[1]
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------- Protected Route ----------
@router.get("/me")
def get_profile(user=Depends(verify_token)):
    return {"uid": user["uid"], "email": user.get("email")}


# ---------- Delete User (Admin Only) ----------
@router.delete("/delete-user/{uid}")
def delete_user(uid: str, user=Depends(verify_token)):
    try:
        admin_doc = db.collection("users").where("uid", "==", user["uid"]).limit(1).get()
        if not admin_doc or len(admin_doc) == 0:
            raise HTTPException(status_code=403, detail="User record not found")

        admin_data = admin_doc[0].to_dict()
        if admin_data.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Only Admins can delete users")

        try:
            auth.delete_user(uid)
        except auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="User not found in Firebase Auth")

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