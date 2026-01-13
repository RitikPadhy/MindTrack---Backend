from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()

# ----------------- Helper: Get Dates -----------------
def get_dates(period: str):
    today = datetime.now().date()

    if period == "day":
        return [today.isoformat()]

    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return [(start + timedelta(days=i)).isoformat() for i in range(7)]

    elif period == "month":
        start = today.replace(day=1)
        next_month = start.replace(month=start.month % 12 + 1, day=1)
        days_in_month = (next_month - start).days
        return [(start + timedelta(days=i)).isoformat() for i in range(days_in_month)]

    raise ValueError("Invalid period. Use day, week, or month.")


# ----------------- Core Calculation -----------------
def compute_task_progress(doc_data, dates):
    task_list = doc_data.get("tasks", [])
    routines = doc_data.get("routines", {})

    task_stats = {}  # {task_name: {"filled": x, "total": y}}

    for day in dates:
        day_data = routines.get(day, {})
        if not day_data:
            continue

        # Iterate by hour in the day
        for idx, (hour, hour_data) in enumerate(sorted(day_data.items())):
            if idx >= len(task_list):
                continue  # safety

            # Get first task name for this hour
            # Handle both formats: {"tasks": [...]} (old) and {"items": [...]} (new from web interface)
            task_name = None
            if "items" in task_list[idx]:
                # New format: items is a list of objects with "title" and "category"
                items = task_list[idx].get("items", [])
                if items and isinstance(items[0], dict) and "title" in items[0]:
                    task_name = items[0]["title"]
            elif "tasks" in task_list[idx]:
                # Old format: tasks is a list of strings
                tasks_for_hour = task_list[idx].get("tasks", [])
                if tasks_for_hour:
                    task_name = tasks_for_hour[0] if isinstance(tasks_for_hour[0], str) else str(tasks_for_hour[0])
            
            if not task_name:
                continue

            # Initialize aggregate bucket
            if task_name not in task_stats:
                task_stats[task_name] = {"filled": 0, "total": 0}

            slots = hour_data.get("slots", {})
            for slot in slots.values():
                task_stats[task_name]["total"] += 1
                if slot.get("filled"):
                    task_stats[task_name]["filled"] += 1

    # Convert to %
    results = []
    for task, stats in task_stats.items():
        if stats["total"] == 0:
            percentage = 0.0
        else:
            percentage = round((stats["filled"] / stats["total"]) * 100, 2)

        results.append({
            "task": task,
            "percentage_done": percentage,
            "filled": stats["filled"],
            "total_slots": stats["total"]
        })

    # return top 5 highest %
    results.sort(key=lambda x: x["percentage_done"], reverse=True)
    return results[:5]


# ----------------- API -----------------
@router.get("/progress/{period}")
def get_top_tasks(period: str, user=Depends(verify_bearer_token)):
    uid = user["uid"]

    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Routine not found")

    try:
        dates = get_dates(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    results = compute_task_progress(doc.to_dict(), dates)

    return {
        "uid": uid,
        "period": period,
        "top_tasks": results
    }