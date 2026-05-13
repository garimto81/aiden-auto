"""
Calendar Library Pydantic Models
"""

from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, computed_field


class CalendarInfo(BaseModel):
    """Calendar metadata."""

    id: str
    summary: str = ""
    description: str = ""
    time_zone: str = "Asia/Seoul"
    primary: bool = False


class EventTime(BaseModel):
    """Event start/end time."""

    date_time: Optional[datetime] = None
    date: Optional[date] = None
    time_zone: str = "Asia/Seoul"

    @computed_field
    @property
    def is_all_day(self) -> bool:
        """Check if this is an all-day event."""
        return self.date is not None and self.date_time is None


class EventAttendee(BaseModel):
    """Event attendee."""

    email: str
    display_name: str = ""
    response_status: str = "needsAction"
    organizer: bool = False
    self_: bool = False


class CalendarEvent(BaseModel):
    """Calendar event."""

    id: str
    summary: str = ""
    description: str = ""
    location: str = ""
    start: Optional[EventTime] = None
    end: Optional[EventTime] = None
    status: str = "confirmed"
    html_link: str = ""
    creator_email: str = ""
    organizer_email: str = ""
    attendees: List[EventAttendee] = []
    recurring_event_id: Optional[str] = None
    created: Optional[datetime] = None
    updated: Optional[datetime] = None

    @computed_field
    @property
    def is_all_day(self) -> bool:
        """Check if this is an all-day event."""
        return self.start.is_all_day if self.start else False

    @computed_field
    @property
    def permalink(self) -> str:
        """Generate Google Calendar web URL."""
        return self.html_link or f"https://calendar.google.com/calendar/event?eid={self.id}"


class CreateEventRequest(BaseModel):
    """Request to create an event."""

    summary: str
    description: str = ""
    location: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    all_day_start: Optional[date] = None
    all_day_end: Optional[date] = None
    time_zone: str = "Asia/Seoul"
    attendees: List[str] = []
    calendar_id: str = "primary"
