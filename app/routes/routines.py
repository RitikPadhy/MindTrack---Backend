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
    hour_slots_status: Dict[str, Dict[str, Dict[int, bool]]]


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
def update_day_completion_granular(request: GranularCompletion, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    update_data = {}

    for hour, slots_map in request.hour_slots_status.items():
        for slot, tasks_map in slots_map.items():
            for task_index, filled in tasks_map.items():
                update_data[f"routines.{request.date}.{hour}.slots.{slot}.tasks.{task_index}.filled"] = filled

    if update_data:
        doc_ref.update(update_data)

    return {"message": f"Routine for {request.date} updated successfully"}