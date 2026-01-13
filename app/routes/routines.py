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
    taskIndex: int | None


class HourSlotsUpdate(BaseModel):
    date: str
    hour: str
    filled: bool


class HourTask(BaseModel):
    tasks: List[str]


class UpdateTasksArray(BaseModel):
    tasks: List[HourTask]
    
class SlotUpdate(BaseModel):
    filled: bool
    taskIndex: int | None

class GranularCompletion(BaseModel):
    date: str
    hour_slots_status: Dict[str, Dict[str, SlotUpdate]]


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

    transformed_routine = {}

    for hour, hour_data in routine.items():
        slots = hour_data.get("slots", {})

        transformed_routine[hour] = {
            "slots": {
                slot_time: {
                    "filled": slot_data.get("filled", False),
                    "taskIndex": slot_data.get("taskIndex")
                }
                for slot_time, slot_data in slots.items()
            }
        }

    return {
        "uid": uid,
        "date": date,
        "routine": transformed_routine,
        "tasks": data.get("tasks", [])
    }

@router.patch("/update-day")
def update_day_completion_granular(request: GranularCompletion, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    update_data = {}

    for hour, slot_map in request.hour_slots_status.items():
        for slot, slot_data in slot_map.items():

            # 🔒 SAFETY RULE
            if slot_data.filled and slot_data.taskIndex is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Filled slot {hour}:{slot} must have taskIndex"
                )

            base = f"routines.{request.date}.{hour}.slots.{slot}"
            update_data[f"{base}.filled"] = slot_data.filled
            update_data[f"{base}.taskIndex"] = slot_data.taskIndex

    if update_data:
        doc_ref.update(update_data)

    return {"message": f"Routine for {request.date} updated successfully"}