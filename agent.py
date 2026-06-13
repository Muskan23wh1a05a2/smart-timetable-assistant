"""
agent.py
---------
LangChain-based conversational scheduling agent.

The agent has access to tools for:
- Listing upcoming calendar events
- Creating new calendar events
- Checking for conflicts before creating an event
- Finding free time slots on a given day
- Adding assignment deadlines

Requires an OpenAI-compatible API key set as the OPENAI_API_KEY environment
variable (or entered in the Streamlit sidebar). You can swap ChatOpenAI for
another LangChain-supported chat model if you prefer (e.g. Anthropic, etc.)
"""

import datetime
import json

from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

from google_calendar import list_upcoming_events, create_event
from schedule_store import load_schedule
from assignment_store import add_assignment, load_assignments
from conflict_detector import check_new_event_conflict, find_free_slots
from exam_store import add_exam, get_upcoming_exams, allocate_study_slots, load_exams
from academic_calendar import get_upcoming_holidays, get_active_term


def build_agent(calendar_service, openai_api_key, model="gpt-4o-mini"):
    """
    Builds and returns a LangChain AgentExecutor wired up with scheduling tools.

    `calendar_service` must be an authenticated Google Calendar service object
    (from google_calendar.get_calendar_service()).
    """

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    @tool
    def list_events(days_ahead: int = 7) -> str:
        """List upcoming Google Calendar events for the next N days (default 7)."""
        time_min = datetime.datetime.utcnow().isoformat() + "Z"
        events = list_upcoming_events(calendar_service, max_results=50, time_min=time_min)
        cutoff = datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)

        result = []
        for e in events:
            start = e["start"].get("dateTime", e["start"].get("date"))
            result.append({
                "title": e.get("summary", "(No title)"),
                "start": start,
                "location": e.get("location", ""),
            })
        return json.dumps(result, indent=2) if result else "No upcoming events found."

    @tool
    def create_calendar_event(title: str, start_datetime: str, end_datetime: str,
                               description: str = "", location: str = "") -> str:
        """
        Create a new event on the user's Google Calendar.
        start_datetime and end_datetime must be ISO format strings,
        e.g. '2026-06-15T14:00:00'. Before creating, this tool automatically
        checks for conflicts with existing events and the class schedule.
        """
        start_dt = datetime.datetime.fromisoformat(start_datetime)
        end_dt = datetime.datetime.fromisoformat(end_datetime)

        # Check conflicts first
        time_min = datetime.datetime.utcnow().isoformat() + "Z"
        events = list_upcoming_events(calendar_service, max_results=50, time_min=time_min)
        class_schedule = load_schedule()
        conflicts = check_new_event_conflict(start_dt, end_dt, events, class_schedule)

        if conflicts:
            conflict_text = "; ".join(conflicts)
            return (
                f"⚠️ Conflict detected, event NOT created: {conflict_text}. "
                f"Ask the user if they'd like to proceed anyway, pick a different time, "
                f"or use find_free_time to suggest alternatives."
            )

        created = create_event(
            calendar_service, summary=title, start_datetime=start_dt,
            end_datetime=end_dt, description=description, location=location
        )
        return f"✅ Event '{title}' created successfully for {start_datetime} - {end_datetime}."

    @tool
    def force_create_calendar_event(title: str, start_datetime: str, end_datetime: str,
                                     description: str = "", location: str = "") -> str:
        """
        Create a new event WITHOUT conflict checking. Use this only if the user
        explicitly confirms they want to proceed despite a conflict warning.
        """
        start_dt = datetime.datetime.fromisoformat(start_datetime)
        end_dt = datetime.datetime.fromisoformat(end_datetime)
        create_event(
            calendar_service, summary=title, start_datetime=start_dt,
            end_datetime=end_dt, description=description, location=location
        )
        return f"✅ Event '{title}' created (without conflict check) for {start_datetime} - {end_datetime}."

    @tool
    def find_free_time(date: str, min_duration_minutes: int = 30) -> str:
        """
        Find free time slots on a given date (format: YYYY-MM-DD), considering
        existing calendar events and the recurring class schedule.
        Returns a list of free (start, end) time ranges between 8 AM and 10 PM.
        """
        day = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        time_min = datetime.datetime.utcnow().isoformat() + "Z"
        events = list_upcoming_events(calendar_service, max_results=50, time_min=time_min)
        class_schedule = load_schedule()

        slots = find_free_slots(events, day, min_duration_minutes=min_duration_minutes,
                                 class_schedule=class_schedule)
        if not slots:
            return f"No free slots of at least {min_duration_minutes} minutes found on {date}."

        result = [f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}" for s, e in slots]
        return f"Free slots on {date}: " + ", ".join(result)

    @tool
    def add_assignment_deadline(title: str, course: str, due_date: str,
                                 due_time: str = "23:59", notes: str = "",
                                 priority: str = "Medium") -> str:
        """
        Add an assignment deadline. due_date format: YYYY-MM-DD, due_time format: HH:MM.
        priority must be one of: Low, Medium, High, Critical (default Medium).
        """
        add_assignment(title, course, due_date, due_time, notes, priority)
        return f"✅ Added assignment '{title}' for {course}, due {due_date} {due_time}, priority {priority}."

    @tool
    def add_exam_schedule(course: str, exam_date: str, exam_time: str = "10:00",
                           duration_minutes: int = 120, location: str = "",
                           priority: str = "High", study_hours_goal: int = 10) -> str:
        """
        Add an exam to the schedule. exam_date format: YYYY-MM-DD, exam_time format: HH:MM.
        priority must be one of: Low, Medium, High, Critical (default High).
        study_hours_goal is the total hours of study time desired before the exam (default 10).
        """
        add_exam(course, exam_date, exam_time, duration_minutes, location, priority, study_hours_goal)
        return f"✅ Added exam for '{course}' on {exam_date} at {exam_time}, with a {study_hours_goal}h study goal."

    @tool
    def list_exams() -> str:
        """List all upcoming exams (next 60 days)."""
        exams = get_upcoming_exams(days_ahead=60)
        if not exams:
            return "No upcoming exams found."
        return json.dumps(exams, indent=2)

    @tool
    def suggest_study_plan(course: str, days_before: int = 7, session_length_minutes: int = 60) -> str:
        """
        Suggests study time slots leading up to the next exam for the given course,
        based on free time in the calendar and class schedule. Does NOT create
        calendar events automatically - just returns suggestions.
        """
        exams = load_exams()
        matching = [e for e in exams if e["course"].lower() == course.lower()]
        if not matching:
            return f"No exam found for course '{course}'. Add it first with add_exam_schedule."

        exam = matching[0]
        time_min = datetime.datetime.utcnow().isoformat() + "Z"
        events = list_upcoming_events(calendar_service, max_results=100, time_min=time_min)
        class_schedule = load_schedule()

        suggestions = allocate_study_slots(exam, events, class_schedule,
                                            days_before=days_before,
                                            session_length_minutes=session_length_minutes)
        if not suggestions:
            return f"No free slots found in the {days_before} days before the {course} exam."

        return json.dumps(suggestions, indent=2)

    @tool
    def get_upcoming_festivals(days_ahead: int = 30) -> str:
        """List upcoming Indian holidays/festivals in the next N days (default 30)."""
        holidays = get_upcoming_holidays(days_ahead=days_ahead)
        if not holidays:
            return f"No holidays/festivals in the next {days_ahead} days."
        return json.dumps(holidays, indent=2)

    @tool
    def get_current_term() -> str:
        """Get info about the currently active academic term/semester."""
        term = get_active_term()
        if not term:
            return "No active term found for today's date."
        return json.dumps(term, indent=2)

    @tool
    def list_assignments() -> str:
        """List all tracked assignment deadlines, including priority."""
        assignments = load_assignments()
        if not assignments:
            return "No assignments tracked yet."
        return json.dumps(assignments, indent=2)

    @tool
    def get_class_schedule() -> str:
        """Get the student's recurring weekly class schedule."""
        schedule = load_schedule()
        if not schedule:
            return "No classes added to the schedule yet."
        return json.dumps(schedule, indent=2)

    tools = [
        list_events,
        create_calendar_event,
        force_create_calendar_event,
        find_free_time,
        add_assignment_deadline,
        list_assignments,
        get_class_schedule,
        add_exam_schedule,
        list_exams,
        suggest_study_plan,
        get_upcoming_festivals,
        get_current_term,
    ]

    # ------------------------------------------------------------------
    # LLM + Agent (langgraph-based, compatible with langchain 1.x)
    # ------------------------------------------------------------------
    llm = ChatOpenAI(model=model, api_key=openai_api_key, temperature=0)

    today_str = datetime.date.today().isoformat()

    system_prompt = (
        f"You are a helpful Student Schedule Assistant. Today's date is {today_str}. "
        "You help students manage their academic calendar, classes, assignments, exams, "
        "and find free time, following the Indian academic calendar (semester terms, "
        "exam periods, breaks, festivals). "
        "Always confirm details (date/time) with the user if ambiguous. "
        "When creating events, use create_calendar_event first (it checks for conflicts). "
        "Only use force_create_calendar_event if the user explicitly says to proceed "
        "despite a conflict. When asked about exams, use suggest_study_plan to propose "
        "study sessions, but don't create calendar events for them unless the user confirms. "
        "Be concise and friendly."
    )

    agent_executor = create_react_agent(llm, tools, prompt=system_prompt)

    return agent_executor
