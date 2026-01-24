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
        if start.month == 12:
            next_month = start.replace(year=start.year + 1, month=1)
        else:
            next_month = start.replace(month=start.month + 1)
        days_in_month = (next_month - start).days
        return [(start + timedelta(days=i)).isoformat() for i in range(days_in_month)]

    raise ValueError("Invalid period. Use day, week, or month.")


# ----------------- Core Calculation -----------------
def compute_task_progress(doc_data, dates):
    task_list = doc_data.get("tasks", [])
    routines = doc_data.get("routines", {})

    task_stats = {}  # {task_name: {"filled": int, "total": int}}

    for day in dates:
        day_data = routines.get(day, {})
        if not day_data:
            continue

        for hour_data in day_data.values():
            slots = hour_data.get("slots", {})

            for slot in slots.values():
                task_index = slot.get("taskIndex")
                if task_index is None:
                    continue

                if not isinstance(task_index, int):
                    continue

                if task_index >= len(task_list):
                    continue

                task_entry = task_list[task_index]
                task_name = None

                # New format (web)
                if "items" in task_entry:
                    items = task_entry.get("items", [])
                    if items and isinstance(items[0], dict):
                        task_name = items[0].get("title")

                # Old format (mobile)
                elif "tasks" in task_entry:
                    tasks = task_entry.get("tasks", [])
                    if tasks:
                        task_name = tasks[0] if isinstance(tasks[0], str) else str(tasks[0])

                if not task_name:
                    continue

                if task_name not in task_stats:
                    task_stats[task_name] = {"filled": 0, "total": 0}

                task_stats[task_name]["total"] += 1
                if slot.get("filled") is True:
                    task_stats[task_name]["filled"] += 1

    results = []
    for task, stats in task_stats.items():
        percentage = (
            round((stats["filled"] / stats["total"]) * 100, 2)
            if stats["total"] > 0 else 0.0
        )

        results.append({
            "task": task,
            "percentage_done": percentage,
            "filled": stats["filled"],
            "total_slots": stats["total"]
        })

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