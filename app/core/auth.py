from fastapi import HTTPException, Cookie
from firebase_admin import auth as firebase_auth

def verify_token_cookie(access_token: str = Cookie(None)):
    """
    Dependency for FastAPI routes to verify Firebase ID token from HttpOnly cookie.
    Returns the decoded token.
    """
    if not access_token:
        raise HTTPException(status_code=401, detail="Missing access token cookie")
    try:
        decoded_token = firebase_auth.verify_id_token(access_token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")