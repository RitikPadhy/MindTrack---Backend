import os
import requests
from fastapi import APIRouter, HTTPException, Depends, Cookie, Response
from pydantic import BaseModel, EmailStr
from firebase_admin import auth, firestore
from app.core.firebase import db
from dotenv import load_dotenv

router = APIRouter()

load_dotenv()
FIREBASE_API_KEY = os.getenv("FIREBASE_API_KEY")

# ---------- Pydantic Models ----------
class SignupRequest(BaseModel):
    uid: str  # User-provided UID (required)
    email: EmailStr  # validated email
    password: str
    role: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class LogoutRequest(BaseModel):
    uid: str
    
class SignupResponse(BaseModel):
    uid: str       # Provided by user
    email: EmailStr
    role: str
    doc_id: str    # Firestore-generated document ID

# ---------- Signup ----------
@router.post("/signup", response_model=SignupResponse)
def signup(request: SignupRequest):
    try:
        # ---------- Limit total users ----------
        users_ref = db.collection("users").stream()
        total_users = sum(1 for _ in users_ref)
        if total_users >= 33:
            raise HTTPException(status_code=400, detail="User limit reached (max 33 users allowed)")

        # Check if UID already exists in Firebase Auth
        try:
            auth.get_user(request.uid)
            raise HTTPException(status_code=400, detail="UID already exists")
        except auth.UserNotFoundError:
            pass

        # Check if email already exists in Firebase Auth
        try:
            auth.get_user_by_email(request.email)
            raise HTTPException(status_code=400, detail="Email already exists")
        except auth.UserNotFoundError:
            pass

        # Create user in Firebase Authentication
        user = auth.create_user(uid=request.uid, email=request.email, password=request.password)

        # Add user to Firestore
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
def login(request: LoginRequest, response: Response):
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

    # Set JWT idToken in secure cookie
    response.set_cookie(
        key="access_token",
        value=data["idToken"],
        httponly=True,
        secure=True,
        samesite="none",
        max_age=int(data.get("expiresIn", 3600)),
    )

    return data


# ---------- Logout ----------
@router.post("/logout")
def logout(request: LogoutRequest, response: Response):
    try:
        # Revoke refresh tokens in Firebase
        auth.revoke_refresh_tokens(request.uid)

        # Delete the access_token cookie from the browser
        response.delete_cookie(
            key="access_token",
            path="/",
            samesite="none",
            secure=True
        )

        return {"message": f"User {request.uid} logged out (refresh tokens revoked and cookie cleared)"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Verify Token ----------
def verify_token(access_token: str = Cookie(None)):
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token cookie")
    try:
        decoded_token = auth.verify_id_token(access_token)
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
    """
    Delete a user by UID (Admin only)
    """
    try:
        # Verify the requestor's role from Firestore
        admin_doc = db.collection("users").where("uid", "==", user["uid"]).limit(1).get()
        if not admin_doc or len(admin_doc) == 0:
            raise HTTPException(status_code=403, detail="User record not found")

        admin_data = admin_doc[0].to_dict()
        if admin_data.get("role") != "Admin":
            raise HTTPException(status_code=403, detail="Only Admins can delete users")

        # Delete the target user from Firebase Auth
        try:
            auth.delete_user(uid)
        except auth.UserNotFoundError:
            raise HTTPException(status_code=404, detail="User not found in Firebase Auth")

        # Delete the user from Firestore
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