import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from firebase_admin import auth, firestore
from app.core.firebase import db
from dotenv import load_dotenv

router = APIRouter()

load_dotenv()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# ---------- Pydantic Models ----------
class SignupRequest(BaseModel):
    email: str
    password: str
    role: str


class LoginRequest(BaseModel):
    email: str
    password: str


# ---------- Signup ----------
@router.post("/signup")
def signup(request: SignupRequest):
    try:
        user = auth.create_user(email=request.email, password=request.password)
        db.collection("users").document(user.uid).set({
            "uid": user.uid,
            "email": request.email,
            "role": request.role,
            "createdAt": firestore.SERVER_TIMESTAMP
        })
        return {"uid": user.uid, "email": request.email, "role": request.role}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Login ----------
@router.post("/login")
def login(request: LoginRequest):
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": request.email, "password": request.password, "returnSecureToken": True}
    r = requests.post(url, json=payload)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.json())
    return r.json()


# ---------- Logout ----------
@router.post("/logout")
def logout(uid: str):
    try:
        auth.revoke_refresh_tokens(uid)
        return {"message": "User logged out (refresh tokens revoked)"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Verify Token ----------
def verify_token(authorization: str = Header(...)):
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------- Protected Route ----------
@router.get("/me")
def get_profile(user=Depends(verify_token)):
    return {"uid": user["uid"], "email": user.get("email")}