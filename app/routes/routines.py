from datetime import datetime, timedelta, timezone
from firebase_admin import firestore
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.core.firebase import db
from app.core.auth import verify_token_cookie  # centralized auth dependency

router = APIRouter()

# ----------------- Routine Generator -----------------
def generate_four_week_routine(created_at: datetime):
    routine_data = {}
    start_date = created_at.date()
    
    # Number of hours from 6:00 to 23:00 inclusive
    hours_list = [datetime.strptime(f"{h:02}:00", "%H:%M") for h in range(6, 23)]

    for day_offset in range(28):
        current_date = (start_date + timedelta(days=day_offset)).isoformat()
        routine_data[current_date] = {}
        
        for hour in hours_list:
            hour_label = hour.strftime("%H:%M")
            routine_data[current_date][hour_label] = {
                "slots": {}  # 4 slots of 15-min each
            }
            for i in range(0, 60, 15):
                time_slot = hour + timedelta(minutes=i)
                slot_label = time_slot.strftime("%H:%M")
                routine_data[current_date][hour_label]["slots"][slot_label] = {"filled": False}

    return routine_data

# ----------------- Create Patient Routine -----------------
def create_patient_routine(uid: str, email: str, role: str, created_at: datetime):
    routine_data = generate_four_week_routine(created_at)
    
    # Tasks array outside routines, 17 empty elements (6am-11pm)
    tasks_array = [{"tasks": []} for _ in range(17)]

    routine_doc = {
        "uid": uid,
        "email": email,
        "role": role,
        "createdAt": created_at,
        "routines": routine_data,
        "tasks": tasks_array  # <-- outside routines
    }
    db.collection("daily_routines").document(uid).set(routine_doc)
    print(f"✅ Routine created for patient {uid}")

# ----------------- Pydantic Models -----------------
class SingleSlotUpdate(BaseModel):
    date: str           # YYYY-MM-DD
    hour: str           # HH:MM
    slot: str           # HH:MM
    filled: bool        # True or False

class HourSlotsUpdate(BaseModel):
    date: str           # YYYY-MM-DD
    hour: str           # HH:MM
    filled: bool        # True or False for all 4 slots
    
class HourTask(BaseModel):
    tasks: list[str]

class UpdateTasksArray(BaseModel):
    tasks: list[HourTask]    # List of tasks, length must be 17 (6am-11pm)

# ----------------- API Endpoints -----------------
@router.get("/get-day-routine")
def get_day_routine(date: str, user=Depends(verify_token_cookie)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found for this user")

    routines = doc.to_dict().get("routines", {})
    day_routine = routines.get(date)
    if not day_routine:
        raise HTTPException(status_code=404, detail=f"No routine found for date {date}")

    tasks_array = doc.to_dict().get("tasks", [])
    return {"uid": uid, "date": date, "routine": day_routine, "tasks": tasks_array}

@router.patch("/update-tasks-array")
def update_tasks_array(request: UpdateTasksArray, user=Depends(verify_token_cookie)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found for this user")

    if len(request.tasks) != 17:
        raise HTTPException(status_code=400, detail="Tasks array must have 17 elements (6am to 11pm)")

    # Validate each hour’s task list
    for idx, hour_data in enumerate(request.tasks):
        if len(hour_data.tasks) > 2:
            raise HTTPException(status_code=400, detail=f"Hour index {idx} can only have up to 2 tasks")

    # ✅ Convert to Firestore-safe format (list of dicts)
    firestore_safe_tasks = [hour_data.dict() for hour_data in request.tasks]
    doc_ref.update({"tasks": firestore_safe_tasks})

    return {"message": "Tasks array updated successfully", "tasks": firestore_safe_tasks}