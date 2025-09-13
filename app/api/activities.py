from fastapi import APIRouter
from app.core.firebase import db

router = APIRouter()

@router.post("/activity")
def create_activity(therapistId: str, patientId: str, title: str, description: str, date: str):
    activity_ref = db.collection("activities").document()
    activity = {
        "id": activity_ref.id,
        "therapistId": therapistId,
        "patientId": patientId,
        "title": title,
        "description": description,
        "date": date,
        "completed": False
    }
    activity_ref.set(activity)
    return activity