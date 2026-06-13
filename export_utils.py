"""
export_utils.py
-----------------
Export functionality:
- Generate .ics (iCalendar) files for events, class schedules, exams, and assignments
- Generate text/CSV schedule reports
"""

import datetime
import io
import csv

DAY_MAP = {"Mon": "MO", "Tue": "TU", "Wed": "WE", "Thu": "TH", "Fri": "FR", "Sat": "SA", "Sun": "SU"}


def _format_ics_datetime(dt):
    """Formats a datetime as an ICS UTC-less local datetime string."""
    return dt.strftime("%Y%m%dT%H%M%S")


def _ics_escape(text):
    """Escapes special characters for ICS text fields."""
    if not text:
        return ""
    return (
        text.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\n", "\\n")
    )


def generate_ics(events=None, class_schedule=None, exams=None, assignments=None,
                  calendar_name="Student Schedule"):
    """
    Generates an .ics (iCalendar) file content as a string, combining:
    - events: list of Google Calendar event dicts (with 'summary', 'start', 'end', etc.)
    - class_schedule: list of recurring class session dicts (with RRULE)
    - exams: list of exam dicts (single VEVENT each)
    - assignments: list of assignment dicts (as all-day VEVENTs / deadlines)

    Returns the full ICS file content as a string.
    """
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Student Schedule Assistant//EN",
        f"X-WR-CALNAME:{_ics_escape(calendar_name)}",
        "CALSCALE:GREGORIAN",
    ]

    now_stamp = _format_ics_datetime(datetime.datetime.utcnow()) + "Z"
    uid_counter = 0

    def next_uid():
        nonlocal uid_counter
        uid_counter += 1
        return f"student-schedule-{uid_counter}-{now_stamp}@local"

    # --- Google Calendar events ---
    if events:
        for e in events:
            try:
                start_raw = e["start"].get("dateTime", e["start"].get("date"))
                end_raw = e["end"].get("dateTime", e["end"].get("date"))
                is_all_day = "date" in e["start"] and "dateTime" not in e["start"]

                lines.append("BEGIN:VEVENT")
                lines.append(f"UID:{next_uid()}")
                lines.append(f"DTSTAMP:{now_stamp}")
                if is_all_day:
                    start_d = datetime.datetime.strptime(start_raw, "%Y-%m-%d")
                    end_d = datetime.datetime.strptime(end_raw, "%Y-%m-%d")
                    lines.append(f"DTSTART;VALUE=DATE:{start_d.strftime('%Y%m%d')}")
                    lines.append(f"DTEND;VALUE=DATE:{end_d.strftime('%Y%m%d')}")
                else:
                    start_dt = datetime.datetime.fromisoformat(start_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    end_dt = datetime.datetime.fromisoformat(end_raw.replace("Z", "+00:00")).replace(tzinfo=None)
                    lines.append(f"DTSTART:{_format_ics_datetime(start_dt)}")
                    lines.append(f"DTEND:{_format_ics_datetime(end_dt)}")
                lines.append(f"SUMMARY:{_ics_escape(e.get('summary', '(No title)'))}")
                if e.get("location"):
                    lines.append(f"LOCATION:{_ics_escape(e['location'])}")
                if e.get("description"):
                    lines.append(f"DESCRIPTION:{_ics_escape(e['description'])}")
                lines.append("END:VEVENT")
            except Exception:
                continue

    # --- Recurring class schedule (weekly RRULE) ---
    if class_schedule:
        today = datetime.date.today()
        for cls in class_schedule:
            try:
                days = [DAY_MAP[d] for d in cls["days"] if d in DAY_MAP]
                if not days:
                    continue
                start_time = datetime.datetime.strptime(cls["start_time"], "%H:%M").time()
                end_time = datetime.datetime.strptime(cls["end_time"], "%H:%M").time()

                start_dt = datetime.datetime.combine(today, start_time)
                end_dt = datetime.datetime.combine(today, end_time)

                title = cls["course_name"]
                session_type = cls.get("session_type", "Lecture")
                instructor = cls.get("instructor", "")

                lines.append("BEGIN:VEVENT")
                lines.append(f"UID:{next_uid()}")
                lines.append(f"DTSTAMP:{now_stamp}")
                lines.append(f"DTSTART:{_format_ics_datetime(start_dt)}")
                lines.append(f"DTEND:{_format_ics_datetime(end_dt)}")
                lines.append(f"RRULE:FREQ=WEEKLY;BYDAY={','.join(days)}")
                lines.append(f"SUMMARY:{_ics_escape(title + ' (' + session_type + ')')}")
                if cls.get("location"):
                    lines.append(f"LOCATION:{_ics_escape(cls['location'])}")
                if instructor:
                    lines.append(f"DESCRIPTION:{_ics_escape('Instructor: ' + instructor)}")
                lines.append("END:VEVENT")
            except Exception:
                continue

    # --- Exams ---
    if exams:
        for ex in exams:
            try:
                exam_date = datetime.datetime.strptime(ex["exam_date"], "%Y-%m-%d").date()
                exam_time = datetime.datetime.strptime(ex.get("exam_time", "10:00"), "%H:%M").time()
                start_dt = datetime.datetime.combine(exam_date, exam_time)
                end_dt = start_dt + datetime.timedelta(minutes=ex.get("duration_minutes", 120))

                lines.append("BEGIN:VEVENT")
                lines.append(f"UID:{next_uid()}")
                lines.append(f"DTSTAMP:{now_stamp}")
                lines.append(f"DTSTART:{_format_ics_datetime(start_dt)}")
                lines.append(f"DTEND:{_format_ics_datetime(end_dt)}")
                lines.append(f"SUMMARY:{_ics_escape('EXAM: ' + ex['course'])}")
                if ex.get("location"):
                    lines.append(f"LOCATION:{_ics_escape(ex['location'])}")
                lines.append(f"DESCRIPTION:{_ics_escape('Priority: ' + ex.get('priority','High'))}")
                lines.append("END:VEVENT")
            except Exception:
                continue

    # --- Assignments (as all-day deadline events) ---
    if assignments:
        for a in assignments:
            if a.get("completed"):
                continue
            try:
                due_date = datetime.datetime.strptime(a["due_date"], "%Y-%m-%d").date()
                next_day = due_date + datetime.timedelta(days=1)

                lines.append("BEGIN:VEVENT")
                lines.append(f"UID:{next_uid()}")
                lines.append(f"DTSTAMP:{now_stamp}")
                lines.append(f"DTSTART;VALUE=DATE:{due_date.strftime('%Y%m%d')}")
                lines.append(f"DTEND;VALUE=DATE:{next_day.strftime('%Y%m%d')}")
                lines.append(f"SUMMARY:{_ics_escape('DUE: ' + a['title'] + ' (' + a['course'] + ')')}")
                lines.append(f"DESCRIPTION:{_ics_escape('Priority: ' + a.get('priority','Medium') + '. Notes: ' + a.get('notes',''))}")
                lines.append("END:VEVENT")
            except Exception:
                continue

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def generate_csv_report(class_schedule=None, assignments=None, exams=None):
    """
    Generates a combined CSV schedule report as a string.
    Columns: Type, Title/Course, Detail, Day(s)/Date, Time, Location/Priority
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Type", "Title/Course", "Detail", "Day(s)/Date", "Time", "Location/Priority"])

    if class_schedule:
        for c in class_schedule:
            writer.writerow([
                "Class",
                c["course_name"],
                c.get("session_type", "Lecture"),
                ", ".join(c["days"]),
                f"{c['start_time']}-{c['end_time']}",
                c.get("location", ""),
            ])

    if exams:
        for e in exams:
            writer.writerow([
                "Exam",
                e["course"],
                f"{e.get('duration_minutes',120)} min",
                e["exam_date"],
                e.get("exam_time", ""),
                f"Priority: {e.get('priority','High')}",
            ])

    if assignments:
        for a in assignments:
            status = "Completed" if a.get("completed") else "Pending"
            writer.writerow([
                "Assignment",
                a["title"],
                a["course"],
                a["due_date"],
                a.get("due_time", ""),
                f"Priority: {a.get('priority','Medium')} ({status})",
            ])

    return output.getvalue()


def generate_text_summary(class_schedule=None, assignments=None, exams=None, holidays=None):
    """Generates a human-readable plain-text schedule summary report."""
    lines = []
    lines.append("=" * 50)
    lines.append("STUDENT SCHEDULE SUMMARY REPORT")
    lines.append(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    lines.append("\n--- WEEKLY CLASS SCHEDULE ---")
    if class_schedule:
        for c in class_schedule:
            lines.append(f"  {c['course_name']} [{c.get('session_type','Lecture')}] - "
                          f"{', '.join(c['days'])} {c['start_time']}-{c['end_time']} "
                          f"({c.get('location','')})")
    else:
        lines.append("  (none)")

    lines.append("\n--- UPCOMING EXAMS ---")
    if exams:
        for e in exams:
            lines.append(f"  {e['course']} - {e['exam_date']} {e.get('exam_time','')} "
                          f"[{e.get('priority','High')}] Study goal: {e.get('study_hours_goal',10)}h")
    else:
        lines.append("  (none)")

    lines.append("\n--- ASSIGNMENT DEADLINES ---")
    if assignments:
        for a in assignments:
            status = "[DONE]" if a.get("completed") else ""
            lines.append(f"  {a['title']} ({a['course']}) - due {a['due_date']} "
                          f"{a.get('due_time','')} [{a.get('priority','Medium')}] {status}")
    else:
        lines.append("  (none)")

    lines.append("\n--- UPCOMING HOLIDAYS/FESTIVALS ---")
    if holidays:
        for h in holidays:
            lines.append(f"  {h['name']} - {h['date']} ({h['type']})")
    else:
        lines.append("  (none)")

    lines.append("\n" + "=" * 50)
    return "\n".join(lines)
