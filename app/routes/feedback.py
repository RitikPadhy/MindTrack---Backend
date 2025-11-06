from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from app.core.firebase import db
from app.core.auth import verify_bearer_token  # centralized auth dependency

router = APIRouter()

# ----------------- Pydantic Models -----------------

class WeeklyFeedbackUpdate(BaseModel):
    week_number: int = Field(..., ge=1, le=4)
    energy_levels: float = Field(..., ge=0.0, le=10.0)
    satisfaction: float = Field(..., ge=0.0, le=10.0)
    happiness: float = Field(..., ge=0.0, le=10.0)
    proud_of_achievements: float = Field(..., ge=0.0, le=10.0)
    how_busy: float = Field(..., ge=0.0, le=10.0)

# ----------------- Helper Functions -----------------
def get_week_number(start_date: datetime, current_date: datetime) -> int:
    """
    Calculate which week (1-4) based on start_date
    """
    delta_days = (current_date.date() - start_date.date()).days
    week_num = delta_days // 7 + 1
    if week_num < 1:
        week_num = 1
    elif week_num > 4:
        week_num = 4
    return week_num

# ----------------- API Endpoints -----------------
@router.patch("/update-week")
def update_week(feedback: WeeklyFeedbackUpdate, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    if user.get("role") != "Patient":
        raise HTTPException(status_code=403, detail="Access restricted to patients only")
    
    doc_ref = db.collection("weekly_feedback").document(uid)
    doc = doc_ref.get()

    # If no doc exists, create empty structure
    if not doc.exists:
        doc_ref.set({
            "uid": uid,
            "weeks": {
                "1": {},
                "2": {},
                "3": {},
                "4": {}
            },
            "createdAt": datetime.now(timezone.utc)
        })
        doc = doc_ref.get()

    if feedback.week_number not in [1, 2, 3, 4]:
        raise HTTPException(status_code=400, detail="Week number must be between 1 and 4")

    # Update all 5 metrics at once
    field_path = f"weeks.{str(feedback.week_number)}"
    doc_ref.update({field_path: {
        "energy_levels": float(feedback.energy_levels),
        "satisfaction": float(feedback.satisfaction),
        "happiness": float(feedback.happiness),
        "proud_of_achievements": float(feedback.proud_of_achievements),
        "how_busy": float(feedback.how_busy)
    }})

    return {"message": f"Week {feedback.week_number} feedback updated successfully"}

@router.get("/get-current-week")
def get_current_week(user=Depends(verify_bearer_token)):
    """
    Returns the feedback for the current week (1-4) based on the start date of feedback.
    """
    uid = user["uid"]
    if user.get("role") != "Patient":
        raise HTTPException(status_code=403, detail="Access restricted to patients only")
    
    doc_ref = db.collection("weekly_feedback").document(uid)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Weekly feedback not found for this user")

    data = doc.to_dict()
    start_date = data.get("createdAt")
    if not start_date:
        raise HTTPException(status_code=404, detail="Start date not found in feedback")

    current_date = datetime.now(timezone.utc)
    week_num = get_week_number(start_date, current_date)

    week_feedback = data.get("weeks", {}).get(str(week_num), {})
    return {
        "uid": uid,
        "week_number": week_num,
        "feedback": week_feedback
    }