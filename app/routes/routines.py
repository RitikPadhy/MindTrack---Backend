from datetime import datetime, timedelta
from firebase_admin import firestore
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()


# ----------------- Pydantic Models -----------------
class SingleSlotUpdate(BaseModel):
    date: str
    hour: str
    slot: str
    filled: bool


class HourSlotsUpdate(BaseModel):
    date: str
    hour: str
    filled: bool


class HourTask(BaseModel):
    tasks: List[str]


class UpdateTasksArray(BaseModel):
    tasks: List[HourTask]


class GranularCompletion(BaseModel):
    date: str
    hour_slots_status: Dict[str, Dict[str, bool]]


@router.get("/get-day-routine")
def get_day_routine(date: str, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc = db.collection("daily_routines").document(uid).get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    data = doc.to_dict()
    routine = data.get("routines", {}).get(date)

    if routine is None:
        raise HTTPException(status_code=404, detail=f"No routine found for {date}")

    # Ensure every hour has 4 slots (filled = True/False)
    transformed_routine = {}
    for hour, tasks in routine.items():
        transformed_routine[hour] = {
            "tasks": tasks,  # Keep original tasks per hour if you have them
            "slots": {f"{hour[:2]}:{minute}": {"filled": False} for minute in ["00", "15", "30", "45"]}
        }

    return {"uid": uid, "date": date, "routine": transformed_routine, "tasks": data.get("tasks", [])}

@router.patch("/update-day")
def update_day_completion_granular(request: GranularCompletion, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    update_data = {
        f"routines.{request.date}.{hour}.slots.{slot}.filled": filled
        for hour, slot_map in request.hour_slots_status.items()
        for slot, filled in slot_map.items()
    }

    if update_data:
        doc_ref.update(update_data)

    return {"message": f"Routine for {request.date} updated successfully"}