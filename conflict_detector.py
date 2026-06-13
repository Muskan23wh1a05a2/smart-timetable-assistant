"""
conflict_detector.py
---------------------
Basic conflict detection between Google Calendar events and the student's
recurring class schedule, plus simple free-time finding.
"""

import datetime
from dateutil import parser as date_parser

DAY_MAP = {
    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6
}


def _parse_event_times(event):
    """Returns (start_dt, end_dt) as naive datetimes for a Google Calendar event."""
    start = event["start"].get("dateTime", event["start"].get("date"))
    end = event["end"].get("dateTime", event["end"].get("date"))
    start_dt = date_parser.isoparse(start)
    end_dt = date_parser.isoparse(end)
    # Strip timezone info for simple comparison
    if start_dt.tzinfo:
        start_dt = start_dt.replace(tzinfo=None)
    if end_dt.tzinfo:
        end_dt = end_dt.replace(tzinfo=None)
    return start_dt, end_dt


def find_event_conflicts(events):
    """
    Checks a list of Google Calendar events for overlapping time ranges.
    Returns a list of conflict dicts: {"event1": ..., "event2": ...}
    """
    conflicts = []
    parsed = []
    for e in events:
        try:
            start, end = _parse_event_times(e)
            parsed.append((start, end, e))
        except Exception:
            continue

    parsed.sort(key=lambda x: x[0])

    for i in range(len(parsed)):
        for j in range(i + 1, len(parsed)):
            start_a, end_a, event_a = parsed[i]
            start_b, end_b, event_b = parsed[j]
            # Overlap check
            if start_a < end_b and start_b < end_a:
                conflicts.append({
                    "event1": event_a.get("summary", "(No title)"),
                    "event1_time": f"{start_a} - {end_a}",
                    "event2": event_b.get("summary", "(No title)"),
                    "event2_time": f"{start_b} - {end_b}",
                })
    return conflicts


def check_new_event_conflict(new_start, new_end, events, class_schedule=None):
    """
    Checks if a proposed new event (new_start, new_end as datetimes) conflicts
    with existing calendar events or the recurring class schedule.

    Returns a list of human-readable conflict descriptions (empty if no conflicts).
    """
    conflicts = []

    # Check against existing calendar events
    for e in events:
        try:
            start, end = _parse_event_times(e)
        except Exception:
            continue
        if new_start < end and start < new_end:
            conflicts.append(
                f"Overlaps with existing event '{e.get('summary', '(No title)')}' "
                f"({start.strftime('%Y-%m-%d %H:%M')} - {end.strftime('%H:%M')})"
            )

    # Check against recurring class schedule
    if class_schedule:
        weekday = new_start.weekday()  # Monday=0
        for cls in class_schedule:
            class_days = [DAY_MAP[d] for d in cls["days"] if d in DAY_MAP]
            if weekday not in class_days:
                continue
            class_start = datetime.datetime.combine(
                new_start.date(),
                datetime.datetime.strptime(cls["start_time"], "%H:%M").time()
            )
            class_end = datetime.datetime.combine(
                new_start.date(),
                datetime.datetime.strptime(cls["end_time"], "%H:%M").time()
            )
            if new_start < class_end and class_start < new_end:
                conflicts.append(
                    f"Overlaps with class '{cls['course_name']}' "
                    f"({cls['start_time']} - {cls['end_time']})"
                )

    return conflicts


def find_free_slots(events, day, day_start_hour=8, day_end_hour=22,
                     min_duration_minutes=30, class_schedule=None):
    """
    Finds free time slots on a given `day` (datetime.date object), between
    `day_start_hour` and `day_end_hour`, considering both Google Calendar
    events and the recurring class schedule.

    Returns a list of (start_datetime, end_datetime) tuples representing
    free slots of at least `min_duration_minutes`.
    """
    day_start = datetime.datetime.combine(day, datetime.time(day_start_hour, 0))
    day_end = datetime.datetime.combine(day, datetime.time(day_end_hour, 0))

    busy_intervals = []

    # Add calendar events that fall on this day
    for e in events:
        try:
            start, end = _parse_event_times(e)
        except Exception:
            continue
        if start.date() == day or end.date() == day:
            busy_intervals.append((max(start, day_start), min(end, day_end)))

    # Add recurring classes that fall on this day
    if class_schedule:
        weekday = day.weekday()
        for cls in class_schedule:
            class_days = [DAY_MAP[d] for d in cls["days"] if d in DAY_MAP]
            if weekday in class_days:
                cstart = datetime.datetime.combine(
                    day, datetime.datetime.strptime(cls["start_time"], "%H:%M").time()
                )
                cend = datetime.datetime.combine(
                    day, datetime.datetime.strptime(cls["end_time"], "%H:%M").time()
                )
                busy_intervals.append((cstart, cend))

    # Sort and merge overlapping busy intervals
    busy_intervals.sort(key=lambda x: x[0])
    merged = []
    for start, end in busy_intervals:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))

    # Find gaps between merged busy intervals
    free_slots = []
    cursor = day_start
    for start, end in merged:
        if start > cursor:
            gap_minutes = (start - cursor).total_seconds() / 60
            if gap_minutes >= min_duration_minutes:
                free_slots.append((cursor, start))
        cursor = max(cursor, end)

    if cursor < day_end:
        gap_minutes = (day_end - cursor).total_seconds() / 60
        if gap_minutes >= min_duration_minutes:
            free_slots.append((cursor, day_end))

    return free_slots
