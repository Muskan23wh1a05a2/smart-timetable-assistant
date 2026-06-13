"""
exam_store.py
--------------
Local JSON-based storage for exam schedules, plus logic to allocate
study time slots leading up to each exam based on free time in the
student's calendar and class schedule.
"""

import json
import os
import datetime

from conflict_detector import find_free_slots

DATA_FILE = "exams.json"


def load_exams():
    """Returns a list of exam dicts:
    {
        "course": str,
        "exam_date": str (YYYY-MM-DD),
        "exam_time": str (HH:MM),
        "duration_minutes": int,
        "location": str,
        "priority": str  one of ["Low","Medium","High","Critical"],
        "study_hours_goal": int  total hours of study time desired before the exam
    }
    """
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_exams(exams):
    with open(DATA_FILE, "w") as f:
        json.dump(exams, f, indent=2)


def add_exam(course, exam_date, exam_time, duration_minutes=120,
              location="", priority="High", study_hours_goal=10):
    exams = load_exams()
    exams.append({
        "course": course,
        "exam_date": exam_date,
        "exam_time": exam_time,
        "duration_minutes": duration_minutes,
        "location": location,
        "priority": priority,
        "study_hours_goal": study_hours_goal,
    })
    exams.sort(key=lambda e: f"{e['exam_date']} {e['exam_time']}")
    save_exams(exams)
    return exams


def remove_exam(index):
    exams = load_exams()
    if 0 <= index < len(exams):
        exams.pop(index)
        save_exams(exams)
    return exams


def get_upcoming_exams(days_ahead=60):
    """Returns exams within the next `days_ahead` days, sorted by date."""
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=days_ahead)
    upcoming = []
    for e in load_exams():
        try:
            edate = datetime.datetime.strptime(e["exam_date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= edate <= cutoff:
            upcoming.append((edate, e))
    upcoming.sort(key=lambda x: x[0])
    return [e for _, e in upcoming]


def allocate_study_slots(exam, calendar_events, class_schedule, days_before=7,
                          session_length_minutes=60):
    """
    Suggests study time slots for the given exam in the `days_before` days
    leading up to the exam date, based on free time in the calendar and
    class schedule.

    Returns a list of dicts:
    {
        "date": "YYYY-MM-DD",
        "start": "HH:MM",
        "end": "HH:MM",
        "course": exam["course"]
    }
    Stops once `study_hours_goal` worth of sessions have been allocated,
    or `days_before` is exhausted.
    """
    try:
        exam_date = datetime.datetime.strptime(exam["exam_date"], "%Y-%m-%d").date()
    except ValueError:
        return []

    goal_minutes = exam.get("study_hours_goal", 10) * 60
    allocated_minutes = 0
    suggestions = []

    for offset in range(1, days_before + 1):
        day = exam_date - datetime.timedelta(days=offset)
        if day < datetime.date.today():
            continue  # don't suggest sessions in the past

        if allocated_minutes >= goal_minutes:
            break

        free_slots = find_free_slots(
            calendar_events, day,
            min_duration_minutes=session_length_minutes,
            class_schedule=class_schedule,
        )

        for start, end in free_slots:
            if allocated_minutes >= goal_minutes:
                break
            slot_minutes = min(session_length_minutes,
                                int((end - start).total_seconds() // 60))
            slot_end = start + datetime.timedelta(minutes=slot_minutes)
            suggestions.append({
                "date": day.strftime("%Y-%m-%d"),
                "start": start.strftime("%H:%M"),
                "end": slot_end.strftime("%H:%M"),
                "course": exam["course"],
            })
            allocated_minutes += slot_minutes

    return suggestions
