"""
Calendar API Client — gws CLI wrapper + Python API fallback

Primary: subprocess → gws calendar (structured JSON output)
Fallback: Python Google Calendar API (when gws unavailable)

Usage:
    from lib.calendar import CalendarClient

    client = CalendarClient()
    events = client.list_events(days=7)
    event = client.create_event("Meeting", start, end)
"""

import json
import shutil
import subprocess
from datetime import datetime, timedelta, date, timezone
from typing import Optional, List

from .auth import get_credentials, TOKEN_PATH
from .models import (
    CalendarEvent, CalendarInfo, EventTime, EventAttendee,
    CreateEventRequest,
)
from .errors import (
    CalendarError, CalendarAuthError, CalendarAPIError,
    CalendarRateLimitError, CalendarGwsNotFoundError,
)


class CalendarClient:
    """Google Calendar client with gws CLI + Python API fallback."""

    def __init__(self, credentials=None, prefer_gws: bool = True):
        """
        Initialize Calendar client.

        Args:
            credentials: Optional Google Credentials object
            prefer_gws: If True, try gws CLI first (default: True)
        """
        self._gws_available = prefer_gws and shutil.which("gws") is not None
        self._service = None

        if credentials is None:
            credentials = get_credentials()

        if credentials is None and not self._gws_available:
            raise CalendarAuthError(
                f"Not authenticated. Run 'python -m lib.calendar login' first.\n"
                f"Token file not found: {TOKEN_PATH}"
            )

        self.credentials = credentials

    @property
    def service(self):
        """Lazy-init Google Calendar API service."""
        if self._service is None:
            from googleapiclient.discovery import build
            self._service = build("calendar", "v3", credentials=self.credentials)
        return self._service

    # ── gws CLI helpers ───────────────────────────────────────

    def _gws_call(self, resource: str, method: str, params: dict = None) -> dict:
        """
        Call gws CLI and return parsed JSON.

        Args:
            resource: API resource (e.g., "calendar.events")
            method: API method (e.g., "list")
            params: API parameters

        Returns:
            Parsed JSON response

        Raises:
            CalendarGwsNotFoundError: If gws not found
            CalendarAPIError: If gws call fails
        """
        if not self._gws_available:
            raise CalendarGwsNotFoundError("gws CLI not found")

        cmd = ["gws", resource, method]
        if params:
            cmd.extend(["--params", json.dumps(params)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                encoding="utf-8",
            )

            if result.returncode != 0:
                raise CalendarAPIError(
                    f"gws command failed: {result.stderr.strip()}",
                    status_code=result.returncode,
                )

            return json.loads(result.stdout)
        except FileNotFoundError:
            self._gws_available = False
            raise CalendarGwsNotFoundError("gws CLI not found")
        except json.JSONDecodeError as e:
            raise CalendarAPIError(f"Failed to parse gws output: {e}")
        except subprocess.TimeoutExpired:
            raise CalendarAPIError("gws command timed out (30s)")

    # ── Public API ────────────────────────────────────────────

    def list_calendars(self) -> List[CalendarInfo]:
        """
        List all calendars.

        Returns:
            List of CalendarInfo objects
        """
        # Try gws first
        if self._gws_available:
            try:
                data = self._gws_call("calendar.calendarList", "list")
                return [
                    CalendarInfo(
                        id=cal["id"],
                        summary=cal.get("summary", ""),
                        description=cal.get("description", ""),
                        time_zone=cal.get("timeZone", "Asia/Seoul"),
                        primary=cal.get("primary", False),
                    )
                    for cal in data.get("items", [])
                ]
            except CalendarGwsNotFoundError:
                pass

        # Python API fallback
        try:
            result = self.service.calendarList().list().execute()
            return [
                CalendarInfo(
                    id=cal["id"],
                    summary=cal.get("summary", ""),
                    description=cal.get("description", ""),
                    time_zone=cal.get("timeZone", "Asia/Seoul"),
                    primary=cal.get("primary", False),
                )
                for cal in result.get("items", [])
            ]
        except Exception as e:
            self._handle_error(e)

    def list_events(
        self,
        calendar_id: str = "primary",
        days: int = 7,
        max_results: int = 50,
        query: str = None,
    ) -> List[CalendarEvent]:
        """
        List upcoming events.

        Args:
            calendar_id: Calendar ID (default: "primary")
            days: Number of days to look ahead
            max_results: Maximum events to return
            query: Free text search query

        Returns:
            List of CalendarEvent objects
        """
        now = datetime.now(timezone.utc)
        time_min = now.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        time_max = (now + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        # Try gws first
        if self._gws_available:
            try:
                params = {
                    "calendarId": calendar_id,
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "maxResults": max_results,
                    "singleEvents": True,
                    "orderBy": "startTime",
                }
                if query:
                    params["q"] = query

                data = self._gws_call("calendar.events", "list", params)
                return [self._parse_event(item) for item in data.get("items", [])]
            except CalendarGwsNotFoundError:
                pass

        # Python API fallback
        try:
            params = {
                "calendarId": calendar_id,
                "timeMin": time_min,
                "timeMax": time_max,
                "maxResults": max_results,
                "singleEvents": True,
                "orderBy": "startTime",
            }
            if query:
                params["q"] = query

            result = self.service.events().list(**params).execute()
            return [self._parse_event(item) for item in result.get("items", [])]
        except Exception as e:
            self._handle_error(e)

    def get_event(self, event_id: str, calendar_id: str = "primary") -> CalendarEvent:
        """
        Get a single event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID

        Returns:
            CalendarEvent object
        """
        if self._gws_available:
            try:
                data = self._gws_call("calendar.events", "get", {
                    "calendarId": calendar_id,
                    "eventId": event_id,
                })
                return self._parse_event(data)
            except CalendarGwsNotFoundError:
                pass

        try:
            result = self.service.events().get(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            return self._parse_event(result)
        except Exception as e:
            self._handle_error(e)

    def create_event(self, request: CreateEventRequest) -> CalendarEvent:
        """
        Create a new event.

        Args:
            request: CreateEventRequest with event details

        Returns:
            Created CalendarEvent
        """
        body = {"summary": request.summary}

        if request.description:
            body["description"] = request.description
        if request.location:
            body["location"] = request.location

        if request.all_day_start:
            body["start"] = {"date": request.all_day_start.isoformat()}
            body["end"] = {"date": (request.all_day_end or request.all_day_start).isoformat()}
        else:
            if request.start_time is None or request.end_time is None:
                raise CalendarAPIError("start_time and end_time are required for timed events")
            body["start"] = {
                "dateTime": request.start_time.isoformat(),
                "timeZone": request.time_zone,
            }
            body["end"] = {
                "dateTime": request.end_time.isoformat(),
                "timeZone": request.time_zone,
            }

        if request.attendees:
            body["attendees"] = [{"email": email} for email in request.attendees]

        if self._gws_available:
            try:
                data = self._gws_call("calendar.events", "insert", {
                    "calendarId": request.calendar_id,
                    "resource": body,
                })
                return self._parse_event(data)
            except CalendarGwsNotFoundError:
                pass

        try:
            result = self.service.events().insert(
                calendarId=request.calendar_id, body=body
            ).execute()
            return self._parse_event(result)
        except Exception as e:
            self._handle_error(e)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> None:
        """
        Delete an event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID
        """
        if self._gws_available:
            try:
                self._gws_call("calendar.events", "delete", {
                    "calendarId": calendar_id,
                    "eventId": event_id,
                })
                return
            except CalendarGwsNotFoundError:
                pass

        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
        except Exception as e:
            self._handle_error(e)

    def today(self, calendar_id: str = "primary") -> List[CalendarEvent]:
        """Get today's events."""
        return self.list_events(calendar_id=calendar_id, days=1)

    def week(self, calendar_id: str = "primary") -> List[CalendarEvent]:
        """Get this week's events."""
        return self.list_events(calendar_id=calendar_id, days=7)

    # ── Internal helpers ──────────────────────────────────────

    def _parse_event(self, item: dict) -> CalendarEvent:
        """Parse API response into CalendarEvent."""
        start = self._parse_event_time(item.get("start", {}))
        end = self._parse_event_time(item.get("end", {}))

        attendees = []
        for att in item.get("attendees", []):
            attendees.append(EventAttendee(
                email=att.get("email", ""),
                display_name=att.get("displayName", ""),
                response_status=att.get("responseStatus", "needsAction"),
                organizer=att.get("organizer", False),
                self_=att.get("self", False),
            ))

        created = None
        if item.get("created"):
            try:
                created = datetime.fromisoformat(item["created"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        updated = None
        if item.get("updated"):
            try:
                updated = datetime.fromisoformat(item["updated"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return CalendarEvent(
            id=item.get("id", ""),
            summary=item.get("summary", ""),
            description=item.get("description", ""),
            location=item.get("location", ""),
            start=start,
            end=end,
            status=item.get("status", "confirmed"),
            html_link=item.get("htmlLink", ""),
            creator_email=item.get("creator", {}).get("email", ""),
            organizer_email=item.get("organizer", {}).get("email", ""),
            attendees=attendees,
            recurring_event_id=item.get("recurringEventId"),
            created=created,
            updated=updated,
        )

    def _parse_event_time(self, time_data: dict) -> Optional[EventTime]:
        """Parse event time from API response."""
        if not time_data:
            return None

        dt = None
        d = None

        if "dateTime" in time_data:
            try:
                dt = datetime.fromisoformat(time_data["dateTime"])
            except (ValueError, TypeError):
                pass
        elif "date" in time_data:
            try:
                d = date.fromisoformat(time_data["date"])
            except (ValueError, TypeError):
                pass

        return EventTime(
            date_time=dt,
            date=d,
            time_zone=time_data.get("timeZone", "Asia/Seoul"),
        )

    def _handle_error(self, error: Exception):
        """Convert errors to CalendarError."""
        from googleapiclient.errors import HttpError

        if isinstance(error, HttpError):
            status = error.resp.status
            if status == 401:
                raise CalendarAuthError(
                    "Authentication failed. Run 'python -m lib.calendar login'"
                )
            elif status == 429:
                raise CalendarRateLimitError()
            elif status == 403:
                raise CalendarAPIError("Permission denied. Check API scopes.", status_code=status)
            else:
                raise CalendarAPIError(str(error), status_code=status)
        raise CalendarAPIError(str(error))
