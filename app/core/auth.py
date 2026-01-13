from fastapi import HTTPException, Header
from firebase_admin import auth as firebase_auth

def verify_bearer_token(authorization: str = Header(None)):
    """
    Dependency for FastAPI routes to verify Firebase ID token from the Authorization: Bearer header.
    Returns the decoded token dictionary upon successful verification.
    """
    # 1. Check for valid header format
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, 
            detail="Missing or invalid Authorization header (Expected: Bearer <token>)"
        )
    
    token = authorization.split(" ")[1]
    
    # 2. Verify the Firebase ID token
    try:
        decoded_token = firebase_auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        # Catch errors like expired token, invalid signature, etc.
        raise HTTPException(status_code=401, detail=f"Invalid or expired token: {str(e)}")