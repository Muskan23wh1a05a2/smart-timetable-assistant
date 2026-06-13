"""
google_calendar.py
-------------------
Handles authentication and basic operations (create, list, delete events)
with the Google Calendar API.

Setup instructions (see README.md for full details):
1. Go to https://console.cloud.google.com/
2. Create a project and enable the "Google Calendar API"
3. Create OAuth 2.0 Client ID credentials (type: Desktop app)
4. Download the JSON file and save it as `credentials.json` in the project root
5. The first time you run the app, a browser window will open asking you
   to authorize access. A `token.json` file will be created automatically
   so you don't have to log in every time.
"""

import os
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/calendar"]

CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "token.json"


# ----------------------------------------------------------------------
# Web OAuth flow (for cloud deployments - Streamlit Cloud, HF Spaces, etc.)
# ----------------------------------------------------------------------

def get_web_client_config():
    """
    Builds the OAuth client config dict for the web flow from environment
    variables / Streamlit secrets:
      - GOOGLE_CLIENT_ID
      - GOOGLE_CLIENT_SECRET

    Returns None if not configured (caller should fall back to desktop flow
    or show a setup message).
    """
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        try:
            import streamlit as st
            client_id = client_id or st.secrets.get("GOOGLE_CLIENT_ID")
            client_secret = client_secret or st.secrets.get("GOOGLE_CLIENT_SECRET")
        except Exception:
            pass

    if not client_id or not client_secret:
        return None

    return {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


def get_authorization_url(redirect_uri):
    """
    Returns (authorization_url, state) for the user to click to start the
    Google OAuth consent flow. `redirect_uri` must exactly match one of the
    Authorized redirect URIs configured on the Web OAuth client in Google
    Cloud Console (e.g. your deployed app's URL).
    """
    client_config = get_web_client_config()
    if not client_config:
        raise ValueError(
            "Google OAuth web client not configured. Set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET as environment variables or Streamlit secrets."
        )

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url, state


def exchange_code_for_credentials(auth_code, redirect_uri):
    """
    Exchanges the OAuth `code` returned by Google (after user consent) for
    a Credentials object. Call this when the app detects ?code=... in the
    URL query params.
    """
    client_config = get_web_client_config()
    if not client_config:
        raise ValueError("Google OAuth web client not configured.")

    flow = Flow.from_client_config(client_config, scopes=SCOPES, redirect_uri=redirect_uri)
    flow.fetch_token(code=auth_code)
    return flow.credentials


def get_calendar_service_from_credentials(creds):
    """Builds a Google Calendar service object from a Credentials object
    (used with the web OAuth flow, where creds are stored in session state)."""
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)


def credentials_to_dict(creds):
    """Serializes Credentials to a dict for storing in st.session_state."""
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


def credentials_from_dict(data):
    """Rebuilds a Credentials object from a dict (from st.session_state)."""
    return Credentials(**data)


# ----------------------------------------------------------------------
# Desktop OAuth flow (for local development)
# ----------------------------------------------------------------------


def get_calendar_service():
    """
    Authenticates the user (via OAuth 2.0) and returns a Google Calendar
    API service object that can be used to create, list, and delete events.
    """
    creds = None

    # token.json stores the user's access and refresh tokens
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"'{CREDENTIALS_FILE}' not found. Please follow the setup "
                    "instructions in README.md to download your OAuth credentials "
                    "from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)
    return service


def list_upcoming_events(service, max_results=20, time_min=None):
    """
    Returns a list of upcoming events from the user's primary calendar.
    """
    if time_min is None:
        time_min = datetime.datetime.utcnow().isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=time_min,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    return events_result.get("items", [])


def create_event(service, summary, start_datetime, end_datetime,
                  description="", location="", timezone="Asia/Kolkata"):
    """
    Creates a new event on the user's primary Google Calendar.

    start_datetime / end_datetime: Python datetime objects (timezone-naive,
    will be interpreted in the given `timezone`)
    """
    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {
            "dateTime": start_datetime.isoformat(),
            "timeZone": timezone,
        },
        "end": {
            "dateTime": end_datetime.isoformat(),
            "timeZone": timezone,
        },
    }

    created_event = service.events().insert(calendarId="primary", body=event).execute()
    return created_event


def delete_event(service, event_id):
    """
    Deletes an event from the user's primary Google Calendar by its ID.
    """
    service.events().delete(calendarId="primary", eventId=event_id).execute()
