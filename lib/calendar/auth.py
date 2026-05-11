"""
Calendar OAuth 2.0 Authentication

Reuses the same OAuth credentials as google_docs/gmail.
Adds Calendar-specific scopes.

Usage:
    from lib.calendar.auth import get_credentials, login
"""

import json
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from .errors import CalendarAuthError, CalendarCredentialsNotFoundError


_BASE = Path(__file__).resolve().parent.parent.parent  # → C:/claude/
CREDENTIALS_PATH = _BASE / "json" / "desktop_credentials.json"
TOKEN_PATH = _BASE / "json" / "token_calendar.json"

DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_credentials() -> Optional[Credentials]:
    """
    Get Google OAuth credentials for Calendar API.

    Returns:
        Google Credentials object if available, None otherwise
    """
    creds = None

    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), DEFAULT_SCOPES)
        except Exception as e:
            import sys
            print(f"[WARN] Failed to load calendar token: {e}", file=sys.stderr)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_token(creds)
        except Exception as e:
            import sys
            print(f"[WARN] Calendar token refresh failed: {e}", file=sys.stderr)
            creds = None

    return creds


def _save_token(creds: Credentials) -> None:
    """Save credentials to token file."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    # client_id/client_secret are required for token refresh (Google OAuth desktop app pattern)
    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
    }

    TOKEN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def login(scopes: list[str] = None) -> Credentials:
    """
    Perform OAuth flow for Calendar API.

    Args:
        scopes: OAuth scopes (default: DEFAULT_SCOPES)

    Returns:
        Google Credentials object

    Raises:
        CalendarAuthError: If login fails
    """
    scopes = scopes or DEFAULT_SCOPES
    creds = None

    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)
        except Exception:
            pass

    if creds and creds.expired and creds.refresh_token:
        try:
            print("Refreshing expired Calendar token...")
            creds.refresh(Request())
        except Exception as e:
            print(f"Token refresh failed: {e}")
            creds = None

    if not creds or not creds.valid:
        if not CREDENTIALS_PATH.exists():
            raise CalendarCredentialsNotFoundError(str(CREDENTIALS_PATH))

        print("Opening browser for Calendar authorization...")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes)
        creds = flow.run_local_server(port=0)

    _save_token(creds)
    print(f"Calendar token saved to {TOKEN_PATH}")

    return creds
