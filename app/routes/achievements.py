from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()


def get_last_7_days():
    today = datetime.now().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(7)]


@router.get("/messages")
def get_achievements(user=Depends(verify_bearer_token)):
    uid = user["uid"]
    doc_ref = db.collection("daily_routines").document(uid)
    doc = doc_ref.get()

    if not doc.exists:
        # Default if no routine assigned yet
        return [
            {"title": "Welcome!", "message1": "Your journey starts today 🌱", "message2": "Once you begin logging routines, achievements will appear here."},
            {"title": "No Data Yet", "message1": "Try adding activities this week", "message2": "Small steps make real change."},
            {"title": "You Got This!", "message1": "Every day is a fresh start", "message2": "Start with just one meaningful activity."}
        ]

    data = doc.to_dict()
    routines = data.get("routines", {}) or {}
    tasks_array = data.get("tasks", []) or []

    last_7_days = get_last_7_days()

    # Ensure tasks_array has length 17 minimum
    while len(tasks_array) < 17:
        tasks_array.append({"tasks": []})

    days_with_activity = 0
    total_filled_slots = 0
    category_set = set()

    for day in last_7_days:
        day_data = routines.get(day, {})
        if not isinstance(day_data, dict) or not day_data:
            continue

        day_has_activity = False

        # Activity Detection + Hours
        for hour_data in day_data.values():
            slots = hour_data.get("slots", {})
            for slot in slots.values():
                if slot.get("filled", False):
                    day_has_activity = True
                    total_filled_slots += 1

        if day_has_activity:
            days_with_activity += 1

        # Categories Used
        for hour_index, hour_tasks in enumerate(tasks_array):
            tasks = hour_tasks.get("tasks", [])
            if tasks:
                category_set.add(tasks[0])

    # Convert slots → hours (each slot = 15 min)
    total_hours = (total_filled_slots * 15) / 60

    # ---- BADGES ----
    # Consistency
    if days_with_activity >= 7:
        consistency = ("Habit Hero", "7-day streak — gentle but powerful")
    elif days_with_activity >= 5:
        consistency = ("Daily Rhythm Builder", "Completed routines 5 days")
    elif days_with_activity >= 4:
        consistency = ("Steady Steps", "Tracked activities 4 days this week")
    else:
        consistency = ("Keep Going!", "You're building momentum — show up tomorrow 💛")

    # Variety
    unique_categories = len(category_set)
    if unique_categories >= 7:
        variety = ("Whole-Self Nurturer", "Achieved full life-area balance")
    elif unique_categories >= 5:
        variety = ("Life Balance Seeker", "Engaged across 5 different life areas")
    elif unique_categories >= 3:
        variety = ("Explorer of Routines", "Tried activities in 3 categories")
    else:
        variety = ("Beginner's Path", "Try adding different types of activities 🌱")

    # Time Spent
    if total_hours >= 10:
        time_spent = ("Time Alchemist", "10+ hours of meaningful activity")
    elif total_hours >= 5:
        time_spent = ("Purposeful Hours", "5 hours invested this week")
    elif total_hours >= 1:
        time_spent = ("Mindful Moments", "1+ hour spent on yourself")
    else:
        time_spent = ("Start Small", "Even 5 minutes count — begin gently 💫")

    return [
        {"title": consistency[0], "message1": consistency[1], "message2": "Your consistency is your strength."},
        {"title": variety[0], "message1": variety[1], "message2": "Exploring new activities helps growth."},
        {"title": time_spent[0], "message1": time_spent[1], "message2": "Your time spent reflects care and purpose."}
    ]