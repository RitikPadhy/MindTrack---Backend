from datetime import datetime, timedelta
from firebase_admin import firestore
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()


# ----------------- Routine Generator -----------------
def generate_four_week_routine(created_at: datetime):
    routine_data = {}
    start_date = created_at.date()

    hours_list = [datetime.strptime(f"{h:02}:00", "%H:%M") for h in range(6, 23)]

    for day_offset in range(28):
        current_date = (start_date + timedelta(days=day_offset)).isoformat()
        routine_data[current_date] = {}

        for hour in hours_list:
            hour_label = hour.strftime("%H:%M")
            routine_data[current_date][hour_label] = {"slots": {}}

            for i in range(0, 60, 15):
                time_slot = hour + timedelta(minutes=i)
                slot_label = time_slot.strftime("%H:%M")
                routine_data[current_date][hour_label]["slots"][slot_label] = {"filled": False}

    return routine_data

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


# ----------------- API Endpoints -----------------
@router.patch("/update-slot")
def update_single_slot(request: SingleSlotUpdate, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    field_path = f"routines.{request.date}.{request.hour}.slots.{request.slot}.filled"
    doc_ref.update({field_path: request.filled})

    return {"message": f"Slot {request.slot} on {request.date} updated to {request.filled}"}


@router.patch("/update-hour")
def update_hour_slots(request: HourSlotsUpdate, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    hour_data = doc.to_dict().get("routines", {}).get(request.date, {}).get(request.hour)
    if not hour_data:
        raise HTTPException(status_code=404, detail="Hour not found")

    update_data = {
        f"routines.{request.date}.{request.hour}.slots.{slot}.filled": request.filled
        for slot in hour_data.get("slots", {})
    }

    doc_ref.update(update_data)
    return {"message": f"All slots in {request.hour} on {request.date} updated to {request.filled}"}


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

        # ✅ Preserve filled values exactly as stored
        transformed_routine[hour] = {
            "slots": {
                slot_time: {
                    "filled": slot_data.get("filled", False)
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


@router.patch("/update-tasks-array")
def update_tasks_array(request: UpdateTasksArray, user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)

    if not doc_ref.get().exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    if len(request.tasks) != 17:
        raise HTTPException(status_code=400, detail="Tasks array must have 17 elements")

    for i, hour_data in enumerate(request.tasks):
        if len(hour_data.tasks) > 2:
            raise HTTPException(status_code=400, detail=f"Hour {i} cannot have more than 2 tasks")

    doc_ref.update({"tasks": [task.dict() for task in request.tasks]})
    return {"message": "Tasks array updated successfully"}

## Update day
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