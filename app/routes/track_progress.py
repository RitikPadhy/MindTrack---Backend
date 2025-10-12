from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.core.firebase import db
from app.core.auth import verify_token_cookie  # centralized auth dependency

router = APIRouter()

# ----------------- Helper Functions -----------------
def get_dates_for_period(period: str):
    """
    Returns a list of date strings (YYYY-MM-DD) for the given period.
    period: "day", "week", "month"
    """
    today = datetime.now().date()
    dates = []

    if period == "day":
        dates = [today.isoformat()]
    elif period == "week":
        # Assuming week starts on Monday
        start_of_week = today - timedelta(days=today.weekday())
        dates = [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]
    elif period == "month":
        start_of_month = today.replace(day=1)
        num_days = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
        dates = [(start_of_month + timedelta(days=i)).isoformat() for i in range(num_days)]
    else:
        raise ValueError("Invalid period")

    return dates

def calculate_task_completion(routines_doc, dates):
    """
    Calculates percentage completion of tasks across given dates.
    Only considers tasks that are marked as done.
    """
    total_tasks_done = 0
    task_counts = 0

    routines = routines_doc.get("routines", {})
    for date in dates:
        day_routine = routines.get(date, {})
        if not day_routine:
            continue

        for hour, hour_data in day_routine.items():
            if hour == "tasks":
                continue
            slots = hour_data.get("slots", {})
            for slot in slots.values():
                if slot.get("filled"):
                    total_tasks_done += 1
                task_counts += 1 if slot.get("filled") else 0  # Only count done tasks

    if total_tasks_done == 0:
        return 0.0

    # Each done task contributes equally
    percentage_per_task = 100 / total_tasks_done
    return round(percentage_per_task * total_tasks_done, 2)

# ----------------- API Endpoints -----------------
@router.get("/progress/{period}")
def track_progress(period: str, user=Depends(verify_token_cookie)):
    """
    period: day | week | month
    Returns percentage of tasks done for the period.
    """
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found for this user")

    try:
        dates = get_dates_for_period(period)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid period. Use day, week, or month.")

    percentage_done = calculate_task_completion(doc.to_dict(), dates)
    return {
        "uid": uid,
        "period": period,
        "percentage_done": percentage_done
    }
