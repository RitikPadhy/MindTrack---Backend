from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, conint
from datetime import datetime, timezone
from app.core.firebase import db
from app.core.auth import verify_bearer_token  # centralized auth

router = APIRouter()

# ----------------- Pydantic Model -----------------

class MAUQResponse(BaseModel):
    """
    mHealth App Usability Questionnaire (MAUQ)
    18 questions, each rated 1-7
    """
    q1: conint(ge=1, le=7)
    q2: conint(ge=1, le=7)
    q3: conint(ge=1, le=7)
    q4: conint(ge=1, le=7)
    q5: conint(ge=1, le=7)
    q6: conint(ge=1, le=7)
    q7: conint(ge=1, le=7)
    q8: conint(ge=1, le=7)
    q9: conint(ge=1, le=7)
    q10: conint(ge=1, le=7)
    q11: conint(ge=1, le=7)
    q12: conint(ge=1, le=7)
    q13: conint(ge=1, le=7)
    q14: conint(ge=1, le=7)
    q15: conint(ge=1, le=7)
    q16: conint(ge=1, le=7)
    q17: conint(ge=1, le=7)
    q18: conint(ge=1, le=7)
    feedback_text: str | None = None  # optional free-text feedback

# ----------------- API Endpoint -----------------

@router.post("/mauq")
def submit_mauq(responses: MAUQResponse, user=Depends(verify_bearer_token)):
    uid = user["uid"]

    # Fetch user record
    user_doc = db.collection("users").document(uid).get()
    if not user_doc.exists:
        raise HTTPException(status_code=404, detail="User record not found")

    user_info = user_doc.to_dict()
    if user_info.get("role") != "Patient":
        raise HTTPException(status_code=403, detail="Access restricted to patients only")

    # Prepare Firestore doc
    doc_ref = db.collection("mauq_feedback").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        doc_ref.set({
            "uid": uid,
            "submittedAt": datetime.now(timezone.utc),
            "responses": {}
        })
        doc = doc_ref.get()

    # Save all 18 questions + optional feedback text
    responses_dict = responses.dict()
    feedback_text = responses_dict.pop("feedback_text", "")

    doc_ref.update({
        "responses": responses_dict,
        "feedback_text": feedback_text,
        "submittedAt": datetime.now(timezone.utc)
    })

    return {"message": "MAUQ responses submitted successfully"}