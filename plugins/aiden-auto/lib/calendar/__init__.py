"""
Calendar Integration Library

Google Calendar API integration with gws CLI + Python API fallback.

Usage:
    from lib.calendar import CalendarClient, login

    # First time: OAuth flow
    login()

    # Create client
    client = CalendarClient()

    # List events
    events = client.list_events(days=7)
    today = client.today()
    week = client.week()

    # Create event
    from lib.calendar.models import CreateEventRequest
    req = CreateEventRequest(summary="Meeting", start_time=start, end_time=end)
    event = client.create_event(req)

CLI Usage:
    python -m lib.calendar login
    python -m lib.calendar status
    python -m lib.calendar today
    python -m lib.calendar week
    python -m lib.calendar list --days 14
    python -m lib.calendar create "Meeting" "2026-03-15 14:00" "2026-03-15 15:00"
    python -m lib.calendar calendars
"""

__version__ = "1.0.0"

from .calendar_client import CalendarClient
from .auth import login, get_credentials
from .models import (
    CalendarEvent,
    CalendarInfo,
    EventTime,
    EventAttendee,
    CreateEventRequest,
)
from .errors import (
    CalendarError,
    CalendarAuthError,
    CalendarRateLimitError,
    CalendarAPIError,
    CalendarCredentialsNotFoundError,
    CalendarGwsNotFoundError,
)

__all__ = [
    "__version__",
    "CalendarClient",
    "login",
    "get_credentials",
    "CalendarEvent",
    "CalendarInfo",
    "EventTime",
    "EventAttendee",
    "CreateEventRequest",
    "CalendarError",
    "CalendarAuthError",
    "CalendarRateLimitError",
    "CalendarAPIError",
    "CalendarCredentialsNotFoundError",
    "CalendarGwsNotFoundError",
]
