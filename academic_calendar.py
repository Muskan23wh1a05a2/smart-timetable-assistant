"""
academic_calendar.py
----------------------
Handles semester/term templates and the Indian academic calendar
(semester breaks, common festivals/holidays).

This is intentionally a simple, editable JSON-backed module so students
can customize it for their specific university's calendar.
"""

import json
import os
import datetime

TERMS_FILE = "academic_terms.json"
HOLIDAYS_FILE = "academic_holidays.json"

# A starter set of common Indian academic holidays/festivals.
# Dates are illustrative — students should edit academic_holidays.json
# to match their university's actual calendar.
DEFAULT_HOLIDAYS = [
    {"name": "Republic Day", "date": "2026-01-26", "type": "national"},
    {"name": "Holi", "date": "2026-03-04", "type": "festival"},
    {"name": "Good Friday", "date": "2026-04-03", "type": "festival"},
    {"name": "Eid al-Fitr", "date": "2026-03-20", "type": "festival"},
    {"name": "Independence Day", "date": "2026-08-15", "type": "national"},
    {"name": "Raksha Bandhan", "date": "2026-08-28", "type": "festival"},
    {"name": "Ganesh Chaturthi", "date": "2026-09-14", "type": "festival"},
    {"name": "Gandhi Jayanti", "date": "2026-10-02", "type": "national"},
    {"name": "Dussehra", "date": "2026-10-20", "type": "festival"},
    {"name": "Diwali", "date": "2026-11-08", "type": "festival"},
    {"name": "Christmas", "date": "2026-12-25", "type": "festival"},
]


# ----------------------------------------------------------------------
# Semester / Term Templates
# ----------------------------------------------------------------------

def load_terms():
    """
    Returns a list of term dicts:
    {
        "name": str,            e.g. "Semester 5 (Odd 2026)"
        "start_date": str,      YYYY-MM-DD
        "end_date": str,        YYYY-MM-DD
        "exam_start": str,      YYYY-MM-DD (optional)
        "exam_end": str,        YYYY-MM-DD (optional)
        "break_start": str,     YYYY-MM-DD (optional, semester break)
        "break_end": str        YYYY-MM-DD (optional)
    }
    """
    if not os.path.exists(TERMS_FILE):
        return []
    with open(TERMS_FILE, "r") as f:
        return json.load(f)


def save_terms(terms):
    with open(TERMS_FILE, "w") as f:
        json.dump(terms, f, indent=2)


def add_term(name, start_date, end_date, exam_start="", exam_end="",
              break_start="", break_end=""):
    terms = load_terms()
    terms.append({
        "name": name,
        "start_date": start_date,
        "end_date": end_date,
        "exam_start": exam_start,
        "exam_end": exam_end,
        "break_start": break_start,
        "break_end": break_end,
    })
    save_terms(terms)
    return terms


def remove_term(index):
    terms = load_terms()
    if 0 <= index < len(terms):
        terms.pop(index)
        save_terms(terms)
    return terms


def get_active_term(today=None):
    """Returns the term dict whose start/end dates contain `today` (default: today's date), or None."""
    if today is None:
        today = datetime.date.today()
    for term in load_terms():
        try:
            start = datetime.datetime.strptime(term["start_date"], "%Y-%m-%d").date()
            end = datetime.datetime.strptime(term["end_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if start <= today <= end:
            return term
    return None


# ----------------------------------------------------------------------
# Holidays / Festivals
# ----------------------------------------------------------------------

def load_holidays():
    """Returns the list of holidays. Initializes with defaults if file doesn't exist."""
    if not os.path.exists(HOLIDAYS_FILE):
        save_holidays(DEFAULT_HOLIDAYS)
        return DEFAULT_HOLIDAYS
    with open(HOLIDAYS_FILE, "r") as f:
        return json.load(f)


def save_holidays(holidays):
    with open(HOLIDAYS_FILE, "w") as f:
        json.dump(holidays, f, indent=2)


def add_holiday(name, date, htype="festival"):
    holidays = load_holidays()
    holidays.append({"name": name, "date": date, "type": htype})
    holidays.sort(key=lambda h: h["date"])
    save_holidays(holidays)
    return holidays


def remove_holiday(index):
    holidays = load_holidays()
    if 0 <= index < len(holidays):
        holidays.pop(index)
        save_holidays(holidays)
    return holidays


def is_holiday(date):
    """Returns the holiday dict if `date` (datetime.date) is a holiday, else None."""
    date_str = date.strftime("%Y-%m-%d")
    for h in load_holidays():
        if h["date"] == date_str:
            return h
    return None


def get_upcoming_holidays(days_ahead=30):
    """Returns holidays within the next `days_ahead` days, sorted by date."""
    today = datetime.date.today()
    cutoff = today + datetime.timedelta(days=days_ahead)
    upcoming = []
    for h in load_holidays():
        try:
            hdate = datetime.datetime.strptime(h["date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        if today <= hdate <= cutoff:
            upcoming.append((hdate, h))
    upcoming.sort(key=lambda x: x[0])
    return [h for _, h in upcoming]


def is_in_semester_break(date, terms=None):
    """Returns True if `date` falls within any term's break period."""
    if terms is None:
        terms = load_terms()
    for term in terms:
        bs, be = term.get("break_start"), term.get("break_end")
        if bs and be:
            try:
                bstart = datetime.datetime.strptime(bs, "%Y-%m-%d").date()
                bend = datetime.datetime.strptime(be, "%Y-%m-%d").date()
            except ValueError:
                continue
            if bstart <= date <= bend:
                return True
    return False
