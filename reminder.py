"""
reminder.py
------------
Simple email reminder system using SMTP (Gmail-compatible).

Setup:
1. Use a Gmail account.
2. Enable 2-Step Verification on the account.
3. Create an "App Password" at https://myaccount.google.com/apppasswords
4. Set these as environment variables (or enter them in the Streamlit sidebar):
   - SENDER_EMAIL
   - SENDER_APP_PASSWORD
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email_reminder(sender_email, sender_app_password, recipient_email,
                         subject, body):
    """
    Sends a plain-text email reminder via Gmail's SMTP server.

    Returns True on success, raises an exception on failure.
    """
    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(sender_email, sender_app_password)
        server.sendmail(sender_email, recipient_email, msg.as_string())

    return True


def build_assignment_reminder_body(assignment):
    """Builds a friendly reminder message for an assignment."""
    return (
        f"Reminder: '{assignment['title']}' for {assignment['course']} "
        f"is due on {assignment['due_date']} at {assignment.get('due_time', '23:59')}.\n\n"
        f"Notes: {assignment.get('notes', '(none)')}\n\n"
        f"-- Sent by your Student Schedule Assistant"
    )


def build_event_reminder_body(event_summary, event_time, location=""):
    """Builds a friendly reminder message for a calendar event."""
    loc_text = f" at {location}" if location else ""
    return (
        f"Reminder: '{event_summary}' is coming up at {event_time}{loc_text}.\n\n"
        f"-- Sent by your Student Schedule Assistant"
    )
