from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()

# ----------------- Helper: Get Dates -----------------
def get_dates(period: str):
    today = datetime.now().date()
    period = period.lower()

    if period == "day":
        return [today.isoformat()]

    elif period == "week":
        # Last 7 days INCLUDING today
        start = today - timedelta(days=6)
        return [(start + timedelta(days=i)).isoformat() for i in range(7)]

    elif period == "month":
        # Last 30 days INCLUDING today
        start = today - timedelta(days=29)
        return [(start + timedelta(days=i)).isoformat() for i in range(30)]

    raise ValueError("Invalid period. Use day, week, or month.")


# ----------------- Helpers -----------------
def hour_sort_key(hour_str: str) -> int:
    """
    Supports:
      '13'
      '13:00'
      '09:30'
    """
    try:
        return int(hour_str.split(":")[0])
    except Exception:
        return 0


# ----------------- Core Calculation -----------------
def compute_task_progress(doc_data, dates):
    task_list = doc_data.get("tasks", [])
    routines = doc_data.get("routines", {})

    task_stats = {}  # {task_name: {"filled": x, "total": y}}

    for day in dates:
        day_data = routines.get(day, {})
        if not day_data:
            continue

        for idx, (hour, hour_data) in enumerate(
            sorted(day_data.items(), key=lambda x: hour_sort_key(x[0]))
        ):
            if idx >= len(task_list):
                continue

            task_name = None
            template = task_list[idx]

            # New format
            if isinstance(template, dict) and "items" in template:
                items = template.get("items", [])
                if items and isinstance(items[0], dict):
                    task_name = items[0].get("title")

            # Old format
            elif isinstance(template, dict) and "tasks" in template:
                tasks_for_hour = template.get("tasks", [])
                if tasks_for_hour:
                    task_name = (
                        tasks_for_hour[0]
                        if isinstance(tasks_for_hour[0], str)
                        else str(tasks_for_hour[0])
                    )

            if not task_name:
                continue

            task_stats.setdefault(task_name, {"filled": 0, "total": 0})

            slots = hour_data.get("slots", {})
            for slot in slots.values():
                task_stats[task_name]["total"] += 1
                if slot.get("filled"):
                    task_stats[task_name]["filled"] += 1

    # Convert to %
    results = []
    for task, stats in task_stats.items():
        total = stats["total"]
        filled = stats["filled"]

        percentage = round((filled / total) * 100, 2) if total else 0.0

        results.append(
            {
                "task": task,
                "percentage_done": percentage,
                "filled": filled,
                "total_slots": total,
            }
        )

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
        "top_tasks": results,
    }