from datetime import datetime, timedelta
from firebase_admin import firestore
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Any
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
    hour_slots_status: Dict[str, Dict[str, Dict[str, Any]]]


@router.get("/get-day-routine")
def get_day_routine(date: str, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc = db.collection("daily_routines").document(uid).get()
    tasks = doc.to_dict().get("tasks", []) if doc.exists else []

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    data = doc.to_dict()

    routines = data.get("routines", {})
    day_routine = routines.get(date, {})

    # ---------------- Normalize routine slots (06:00 → 23:00) ----------------
    normalized = {}
    for i in range(18):  # 06 → 23 inclusive
        hour = f"{6 + i:02d}:00"
        existing = day_routine.get(hour, {})
        slots = existing.get("slots", {})

        # Ensure all 4 slots exist
        hour_slots = {}
        for m in ["00", "15", "30", "45"]:
            key = f"{hour[:2]}:{m}"
            slot = slots.get(key, {})
            hour_slots[key] = {
                "filled": bool(slot.get("filled", False)),
                "taskIndex": slot.get("taskIndex", None),
            }

        normalized[hour] = {"slots": hour_slots}

    return {
        "uid": uid,
        "date": date,
        "routine": normalized,
        "tasks": tasks,
    }

@router.patch("/update-day")
def update_day_completion_granular(
    request: GranularCompletion,
    user=Depends(verify_bearer_token)
):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    updates = {}

    for hour, hour_data in request.hour_slots_status.items():
        # hour_data is like {"slots": { "06:15": {...}, ... }}
        slots_map = hour_data.get("slots", {})
        for slot, slot_data in slots_map.items():
            base_path = f"routines.{request.date}.{hour}.slots.{slot}"
            updates[f"{base_path}.filled"] = slot_data.get("filled")
            updates[f"{base_path}.taskIndex"] = slot_data.get("taskIndex")

    if not updates:
        return {"message": "Nothing to update"}

    try:
        doc_ref.update(updates)
    except firestore.NotFound:
        # Create doc if missing
        doc_ref.set({}, merge=True)
        doc_ref.update(updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": "Updated successfully"}