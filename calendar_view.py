"""
calendar_view.py
------------------
Renders monthly, weekly, and daily calendar views as HTML tables for
embedding in Streamlit via st.markdown(..., unsafe_allow_html=True).

Combines Google Calendar events with the recurring class schedule.
"""

import calendar
import datetime
from dateutil import parser as date_parser

DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse_event_start(event):
    """Returns (date, time_str or None, summary) for a Google Calendar event."""
    start = event["start"].get("dateTime", event["start"].get("date"))
    is_all_day = "date" in event["start"] and "dateTime" not in event["start"]
    dt = date_parser.isoparse(start)
    if dt.tzinfo:
        dt = dt.replace(tzinfo=None)
    time_str = None if is_all_day else dt.strftime("%H:%M")
    return dt.date(), time_str, event.get("summary", "(No title)")


def _events_by_date(events):
    """Groups Google Calendar events by date."""
    grouped = {}
    for e in events:
        try:
            d, t, summary = _parse_event_start(e)
        except Exception:
            continue
        grouped.setdefault(d, []).append((t, summary))
    return grouped


def _classes_for_weekday(class_schedule, weekday_index):
    """Returns class sessions occurring on a given weekday (0=Mon ... 6=Sun)."""
    day_name = DAY_NAMES[weekday_index]
    result = []
    for c in class_schedule:
        if day_name in c.get("days", []):
            label = f"{c['course_name']} [{c.get('session_type','Lecture')}]"
            result.append((c["start_time"], label))
    return sorted(result)


def render_month_view(year, month, events, class_schedule=None):
    """
    Returns an HTML string rendering a monthly calendar grid for the given
    year/month, with Google Calendar events and recurring classes shown
    as small badges on each day.
    """
    class_schedule = class_schedule or []
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdatescalendar(year, month)
    events_by_date = _events_by_date(events)
    today = datetime.date.today()

    html = ['<div style="font-family: sans-serif; width: 100%;">']
    html.append('<table style="width:100%; border-collapse: collapse; table-layout: fixed;">')
    html.append('<tr>')
    for day_name in DAY_NAMES:
        html.append(f'<th style="border:1px solid #ddd; padding:4px; background:#f5f5f5; font-size:12px;">{day_name}</th>')
    html.append('</tr>')

    for week in month_days:
        html.append('<tr>')
        for day in week:
            in_month = (day.month == month)
            is_today = (day == today)
            bg = "#e8f0fe" if is_today else ("#ffffff" if in_month else "#fafafa")
            text_color = "#999" if not in_month else "#000"

            cell_html = [f'<div style="font-weight:bold; font-size:12px; color:{text_color};">{day.day}</div>']

            # Class sessions for this weekday
            weekday_idx = day.weekday()
            for start_time, label in _classes_for_weekday(class_schedule, weekday_idx):
                cell_html.append(
                    f'<div style="font-size:10px; background:#fff3cd; border-radius:3px; '
                    f'padding:1px 3px; margin:1px 0; overflow:hidden; text-overflow:ellipsis; '
                    f'white-space:nowrap;">{start_time} {label}</div>'
                )

            # Calendar events for this date
            for time_str, summary in sorted(events_by_date.get(day, []), key=lambda x: (x[0] or "")):
                time_label = time_str if time_str else "All day"
                cell_html.append(
                    f'<div style="font-size:10px; background:#d4edda; border-radius:3px; '
                    f'padding:1px 3px; margin:1px 0; overflow:hidden; text-overflow:ellipsis; '
                    f'white-space:nowrap;">{time_label} {summary}</div>'
                )

            html.append(
                f'<td style="border:1px solid #ddd; padding:4px; vertical-align:top; '
                f'background:{bg}; height:90px; overflow:hidden;">' + "".join(cell_html) + '</td>'
            )
        html.append('</tr>')

    html.append('</table></div>')
    return "".join(html)


def render_week_view(start_of_week, events, class_schedule=None):
    """
    Returns an HTML string rendering a 7-day week view starting from
    `start_of_week` (a Monday, datetime.date), showing hourly time slots
    from 7 AM to 10 PM with events and classes.
    """
    class_schedule = class_schedule or []
    events_by_date = _events_by_date(events)
    days = [start_of_week + datetime.timedelta(days=i) for i in range(7)]
    today = datetime.date.today()

    html = ['<div style="font-family: sans-serif; width:100%; overflow-x:auto;">']
    html.append('<table style="width:100%; border-collapse: collapse; table-layout: fixed; min-width:700px;">')

    # Header row
    html.append('<tr>')
    html.append('<th style="border:1px solid #ddd; padding:4px; background:#f5f5f5; font-size:11px; width:50px;"></th>')
    for day in days:
        bg = "#e8f0fe" if day == today else "#f5f5f5"
        html.append(
            f'<th style="border:1px solid #ddd; padding:4px; background:{bg}; font-size:11px;">'
            f'{DAY_NAMES[day.weekday()]}<br>{day.strftime("%b %d")}</th>'
        )
    html.append('</tr>')

    # All-day / class + event summary row per day (compact agenda style instead of hourly grid)
    html.append('<tr>')
    html.append('<td style="border:1px solid #ddd; padding:4px; font-size:11px; vertical-align:top;">Agenda</td>')
    for day in days:
        cell_html = []
        weekday_idx = day.weekday()
        for start_time, label in _classes_for_weekday(class_schedule, weekday_idx):
            cell_html.append(
                f'<div style="font-size:10px; background:#fff3cd; border-radius:3px; '
                f'padding:2px 4px; margin:2px 0;">{start_time} — {label}</div>'
            )
        for time_str, summary in sorted(events_by_date.get(day, []), key=lambda x: (x[0] or "")):
            time_label = time_str if time_str else "All day"
            cell_html.append(
                f'<div style="font-size:10px; background:#d4edda; border-radius:3px; '
                f'padding:2px 4px; margin:2px 0;">{time_label} — {summary}</div>'
            )
        if not cell_html:
            cell_html.append('<div style="font-size:10px; color:#aaa;">—</div>')
        html.append(
            f'<td style="border:1px solid #ddd; padding:4px; vertical-align:top; height:160px;">'
            + "".join(cell_html) + '</td>'
        )
    html.append('</tr>')

    html.append('</table></div>')
    return "".join(html)


def render_day_view(day, events, class_schedule=None):
    """
    Returns an HTML string rendering a single day's schedule as a timeline
    list (classes + calendar events), sorted by time.
    """
    class_schedule = class_schedule or []
    events_by_date = _events_by_date(events)
    weekday_idx = day.weekday()

    items = []
    for start_time, label in _classes_for_weekday(class_schedule, weekday_idx):
        items.append((start_time, "Class", label))
    for time_str, summary in events_by_date.get(day, []):
        items.append((time_str or "00:00", "Event" if time_str else "All day", summary))

    items.sort(key=lambda x: x[0])

    html = [f'<div style="font-family: sans-serif;"><h4>{day.strftime("%A, %B %d, %Y")}</h4>']
    if not items:
        html.append('<p style="color:#999;">No classes or events scheduled.</p>')
    else:
        html.append('<table style="width:100%; border-collapse: collapse;">')
        for time_str, kind, label in items:
            color = "#fff3cd" if kind == "Class" else "#d4edda"
            html.append(
                f'<tr><td style="padding:6px; font-weight:bold; width:80px;">{time_str}</td>'
                f'<td style="padding:6px; background:{color}; border-radius:4px;">'
                f'<span style="font-size:11px; color:#666;">[{kind}]</span> {label}</td></tr>'
            )
        html.append('</table>')
    html.append('</div>')
    return "".join(html)
