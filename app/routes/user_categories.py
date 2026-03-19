from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from app.core.firebase import db
from app.core.auth import verify_bearer_token

router = APIRouter()


def get_last_4_weeks_dates():
    """Get list of dates for the last 4 weeks (28 days)"""
    today = datetime.now().date()
    return [(today - timedelta(days=i)).isoformat() for i in range(28)]


@router.get("/all-users-categories")
def get_all_users_categories(user=Depends(verify_bearer_token)):
    """
    Get all activity categories for all users from the last 4 weeks.
    Returns data organized by user with their unique categories.
    """
    try:
        # Get all documents from daily_routines collection
        routines_ref = db.collection("daily_routines")
        all_users_docs = routines_ref.stream()

        last_4_weeks = get_last_4_weeks_dates()
        result = []

        for doc in all_users_docs:
            user_id = doc.id
            data = doc.to_dict()

            if not data:
                continue

            routines = data.get("routines", {}) or {}
            tasks_array = data.get("tasks", []) or []

            # Set to store unique categories for this user
            user_categories = set()

            # Iterate through the last 4 weeks
            for day in last_4_weeks:
                day_data = routines.get(day, {})
                if not isinstance(day_data, dict) or not day_data:
                    continue

                # Check each hour's slots
                for hour_data in day_data.values():
                    slots = hour_data.get("slots", {})
                    for slot in slots.values():
                        # Only consider filled slots
                        if not slot.get("filled"):
                            continue

                        # Get the task index
                        task_index = slot.get("taskIndex")
                        if task_index is None or task_index >= len(tasks_array):
                            continue

                        # Extract category from task
                        task_entry = tasks_array[task_index]
                        if "items" in task_entry:
                            for item in task_entry.get("items", []):
                                if isinstance(item, dict) and "category" in item:
                                    category = item["category"]
                                    if category:  # Only add non-empty categories
                                        user_categories.add(category)

            # Add user data to result if they have any categories
            if user_categories:
                result.append({
                    "user_id": user_id,
                    "categories": sorted(list(user_categories)),
                    "total_unique_categories": len(user_categories)
                })

        return {
            "period": "last_4_weeks",
            "total_users": len(result),
            "users": result
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching user categories: {str(e)}"
        )
