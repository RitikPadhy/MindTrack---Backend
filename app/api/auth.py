import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel, EmailStr
from firebase_admin import auth as firebase_auth
from app.core.firebase import db
from dotenv import load_dotenv
from datetime import datetime, timedelta

router = APIRouter()

load_dotenv()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# ---------- Pydantic Models ----------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class ChangePasswordRequest(BaseModel):
    email: EmailStr
    old_password: str
    new_password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class LogoutRequest(BaseModel):
    uid: str


# ---------- Helper Functions ----------
def verify_bearer_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ")[1]
    try:
        return firebase_auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# ---------- Login ----------
@router.post("/login")
def login(request: LoginRequest):
    """
    Logs in a user and returns ID token + Refresh token.
    The frontend must store both tokens locally.
    If ID token expires, frontend can use refresh token to get a new one automatically.
    """
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
        "access_token": data["idToken"],        # short-lived token (1 hour)
        "refresh_token": data["refreshToken"],  # long-lived token (use to refresh)
        "token_type": "bearer",
        "expires_in": data["expiresIn"],
        "uid": data["localId"],
    }


# ---------- Refresh Token ----------
@router.post("/refresh-token")
def refresh_token(request: RefreshTokenRequest):
    """
    Use refresh token to get a new access token.
    This allows auto-login without asking for credentials again.
    """
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": request.refresh_token
    }
    r = requests.post(url, data=payload)
    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=r.json())

    data = r.json()
    return {
        "access_token": data["id_token"],
        "refresh_token": data["refresh_token"],
        "token_type": "bearer",
        "expires_in": data["expires_in"],
        "uid": data["user_id"]
    }


# ---------- Change Password ----------
@router.post("/change-password")
def change_password(request: ChangePasswordRequest):
    """
    Verifies old password, then updates password.
    """
    try:
        signin_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        signin_payload = {
            "email": request.email,
            "password": request.old_password,
            "returnSecureToken": True,
        }
        signin_response = requests.post(signin_url, json=signin_payload)

        if signin_response.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid old password")

        signin_data = signin_response.json()
        uid = signin_data.get("localId")

        firebase_auth.update_user(uid, password=request.new_password)
        return {"message": "Password changed successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error changing password: {str(e)}")


# ---------- Get Profile ----------
@router.get("/me")
def get_profile(user=Depends(verify_bearer_token)):
    # Fetch additional user details from Firestore
    user_doc = db.collection("users").where("uid", "==", user["uid"]).limit(1).get()
    if not user_doc:
        raise HTTPException(status_code=404, detail="User record not found")

    user_data = user_doc[0].to_dict()

    return {
        "uid": user["uid"],
        "email": user.get("email"),
        "role": user_data.get("role"),
        "createdAt": user_data.get("createdAt"),
    }

# ---------- Logout ----------
@router.post("/logout")
def logout(request: LogoutRequest):
    """
    Just clears the refresh token on the client side.
    Server-side logout isn't needed for Firebase, unless you want to revoke tokens.
    """
    try:
        firebase_auth.revoke_refresh_tokens(request.uid)
        return {"message": "User logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error logging out: {str(e)}")


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