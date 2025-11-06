from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()

# ----------------- Helper Functions -----------------
def get_dates_for_period(period: str):
    """
    Returns list of date strings for: day | week | month
    """
    today = datetime.now().date()

    if period == "day":
        return [today.isoformat()]

    elif period == "week":
        start_of_week = today - timedelta(days=today.weekday())  # Monday
        return [(start_of_week + timedelta(days=i)).isoformat() for i in range(7)]

    elif period == "month":
        start_of_month = today.replace(day=1)
        next_month = today.replace(month=today.month % 12 + 1, day=1)
        num_days = (next_month - timedelta(days=1)).day
        return [(start_of_month + timedelta(days=i)).isoformat() for i in range(num_days)]

    else:
        raise ValueError("Invalid period")


def calculate_task_percentages(routines_doc, dates):
    """
    Calculate top 5 tasks based on appearance vs completion across given dates.
    Only the FIRST task in each hour is counted.
    """
    task_totals = {}   # task_name → number of slots existing
    task_filled = {}   # task_name → number of slots completed

    routines = routines_doc.get("routines", {})

    for date in dates:
        day_routine = routines.get(date, {})
        if not day_routine:
            continue

        for hour, hour_data in day_routine.items():
            if hour == "tasks":
                continue

            slots = hour_data.get("slots", {})

            # If there are two tasks, only consider the FIRST one
            sorted_slots = sorted(slots.items(), key=lambda x: x[0])
            if not sorted_slots:
                continue

            first_slot = sorted_slots[0][1]
            task_name = first_slot.get("task_name")
            filled = first_slot.get("filled", False)

            if not task_name:
                continue

            task_totals[task_name] = task_totals.get(task_name, 0) + 1
            if filled:
                task_filled[task_name] = task_filled.get(task_name, 0) + 1

    task_percentages = []
    for task, total in task_totals.items():
        completed = task_filled.get(task, 0)
        percentage = (completed / total) * 100 if total > 0 else 0
        task_percentages.append({
            "task_name": task,
            "percentage_done": round(percentage, 2),
        })

    task_percentages.sort(key=lambda x: x["percentage_done"], reverse=True)

    return task_percentages[:5]


# ----------------- API Endpoint -----------------
@router.get("/progress/{period}")
def track_progress(period: str, user=Depends(verify_bearer_token)):
    """
    Returns the TOP 5 tasks with highest completion percentage
    for the selected period: day | week | month
    """
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found for this user")

    try:
        dates = get_dates_for_period(period)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid period. Use: day | week | month")

    top_tasks = calculate_task_percentages(doc.to_dict(), dates)

    return {
        "uid": uid,
        "period": period,
        "top_tasks": top_tasks
    }