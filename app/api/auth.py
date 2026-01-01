from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from firebase_admin import auth as firebase_auth
from app.core.firebase import db
import bcrypt

router = APIRouter()

# ---------- Pydantic Models ----------

class LoginRequest(BaseModel):
    uid: str
    password: str

class LogoutRequest(BaseModel):
    uid: str


# ---------- Helper: Verify Bearer Token ----------

def verify_bearer_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization.split(" ")[1]
    try:
        return firebase_auth.verify_id_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------- Login (UID + Password → Custom Token) ----------

@router.post("/login")
def login(request: LoginRequest):
    # 1️⃣ Fetch user from Firestore
    user_doc = db.collection("users").document(request.uid).get()

    if not user_doc.exists:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_data = user_doc.to_dict()
    password_hash = user_data.get("passwordHash")

    if not password_hash:
        raise HTTPException(status_code=401, detail="User has no password set")

    # 2️⃣ Verify password
    if not bcrypt.checkpw(
        request.password.encode("utf-8"),
        password_hash.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # 3️⃣ Create Firebase Custom Token
    custom_token = firebase_auth.create_custom_token(request.uid)

    return {
        "custom_token": custom_token.decode("utf-8"),
        "uid": request.uid,
        "role": user_data.get("role"),
    }


# ---------- Get Profile ----------

@router.get("/me")
def get_profile(user=Depends(verify_bearer_token)):
    uid = user["uid"]

    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User not found")

    user_data = user_doc.to_dict()

    routine_doc = db.collection("daily_routines").document(uid).get()
    tasks = routine_doc.to_dict().get("tasks", []) if routine_doc.exists else []

    return {
        "uid": uid,
        "name": user_data.get("name"),
        "role": user_data.get("role"),
        "gender": user_data.get("gender"),
        "createdAt": user_data.get("createdAt"),
        "tasks": tasks,
    }


# ---------- Logout ----------

@router.post("/logout")
def logout(request: LogoutRequest):
    try:
        firebase_auth.revoke_refresh_tokens(request.uid)
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------- Delete User (Admin Only) ----------

@router.delete("/delete-user/{uid}")
def delete_user(uid: str, admin_user=Depends(verify_bearer_token)):
    admin_uid = admin_user["uid"]

    admin_doc = db.collection("users").document(admin_uid).get()
    if not admin_doc.exists or admin_doc.to_dict().get("role") != "Admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    firebase_auth.delete_user(uid)
    db.collection("users").document(uid).delete()
    db.collection("daily_routines").document(uid).delete()

    return {"message": f"User {uid} deleted"}