"""
schedule_store.py
------------------
Local JSON-based storage for the student's recurring class schedule, now
with support for course-specific scheduling: lectures, labs, and tutorials
each as separate sessions for the same course.
"""

import json
import os

DATA_FILE = "class_schedule.json"

# Valid session types for course-specific scheduling
SESSION_TYPES = ["Lecture", "Lab", "Tutorial", "Seminar"]


def load_schedule():
    """Returns a list of class session dicts. Each dict has:
    {
        "course_name": str,
        "session_type": str   one of SESSION_TYPES (default "Lecture"),
        "instructor": str,
        "days": list[str]   e.g. ["Mon", "Wed", "Fri"],
        "start_time": str   e.g. "10:00",
        "end_time": str     e.g. "11:00",
        "location": str
    }
    """
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        data = json.load(f)

    # Backward compatibility: add session_type to old entries
    changed = False
    for item in data:
        if "session_type" not in item:
            item["session_type"] = "Lecture"
            changed = True
    if changed:
        save_schedule(data)

    return data


def save_schedule(schedule):
    """Saves the full schedule list back to disk."""
    with open(DATA_FILE, "w") as f:
        json.dump(schedule, f, indent=2)


def add_class(course_name, instructor, days, start_time, end_time,
               location="", session_type="Lecture"):
    """Adds a new class session to the schedule and persists it."""
    schedule = load_schedule()
    schedule.append({
        "course_name": course_name,
        "session_type": session_type,
        "instructor": instructor,
        "days": days,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
    })
    save_schedule(schedule)
    return schedule


def remove_class(index):
    """Removes a class by its index in the list."""
    schedule = load_schedule()
    if 0 <= index < len(schedule):
        schedule.pop(index)
        save_schedule(schedule)
    return schedule


def get_courses():
    """Returns a sorted list of unique course names in the schedule."""
    schedule = load_schedule()
    return sorted(set(c["course_name"] for c in schedule))


def get_sessions_for_course(course_name):
    """Returns all session entries (lecture/lab/tutorial) for a given course."""
    schedule = load_schedule()
    return [c for c in schedule if c["course_name"] == course_name]
