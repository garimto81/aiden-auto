"""
Gmail OAuth 2.0 Authentication

Usage:
    from lib.gmail.auth import login, get_token

    # First time: OAuth flow
    token = login()

    # Subsequent: Load from file
    token = get_token()
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from .models import GmailCredentials, GmailToken
from .errors import GmailAuthError, GmailCredentialsNotFoundError


# File paths — __file__ 기반 상대 경로 (이식성)
_BASE = Path(__file__).resolve().parent.parent.parent  # → C:/claude/
CREDENTIALS_PATH = _BASE / "json" / "desktop_credentials.json"
TOKEN_PATH = _BASE / "json" / "token_gmail.json"

# Default OAuth scopes
DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",     # Read emails
    "https://www.googleapis.com/auth/gmail.send",         # Send emails
    "https://www.googleapis.com/auth/gmail.modify",       # Modify labels
    "https://www.googleapis.com/auth/gmail.labels",       # Manage labels
]


def load_credentials() -> GmailCredentials:
    """
    Load OAuth credentials from file.

    Returns:
        GmailCredentials object

    Raises:
        GmailCredentialsNotFoundError: If credentials file not found
    """
    if not CREDENTIALS_PATH.exists():
        raise GmailCredentialsNotFoundError(str(CREDENTIALS_PATH))

    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        # Handle nested "installed" or "web" format
        if "installed" in data:
            data = data["installed"]
        elif "web" in data:
            data = data["web"]
        return GmailCredentials(**data)
    except (json.JSONDecodeError, KeyError) as e:
        raise GmailAuthError(f"Invalid credentials file: {e}")


def get_credentials() -> Optional[Credentials]:
    """
    Get Google OAuth credentials for Gmail API.

    Returns:
        Google Credentials object if available, None otherwise
    """
    creds = None

    # Try to load existing token
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), DEFAULT_SCOPES)
        except Exception:
            pass

    # Check if refresh needed
    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            save_token_from_credentials(creds)
        except Exception as e:
            import sys
            print(f"[WARN] Token refresh failed: {e}", file=sys.stderr)
            creds = None

    return creds


def get_token() -> Optional[GmailToken]:
    """
    Load token from file.

    Returns:
        GmailToken if available, None otherwise
    """
    if not TOKEN_PATH.exists():
        return None

    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))

        expires_at = None
        if data.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(data["expires_at"])
            except (ValueError, TypeError):
                pass

        return GmailToken(
            access_token=data["token"],
            refresh_token=data.get("refresh_token"),
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            scopes=data.get("scopes", []),
        )
    except (json.JSONDecodeError, KeyError):
        return None


def save_token_from_credentials(creds: Credentials) -> None:
    """
    Save credentials to token file.

    Args:
        creds: Google Credentials object
    """
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else [],
        "expires_at": creds.expiry.isoformat() if creds.expiry else None,
    }

    TOKEN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def login(scopes: list[str] = None) -> GmailToken:
    """
    Perform OAuth flow to get access token.

    Args:
        scopes: OAuth scopes (default: DEFAULT_SCOPES)

    Returns:
        GmailToken object

    Raises:
        GmailAuthError: If login fails
    """
    scopes = scopes or DEFAULT_SCOPES
    creds = None

    # Check existing credentials
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), scopes)
        except Exception:
            pass

    # Refresh if expired
    if creds and creds.expired and creds.refresh_token:
        try:
            print("Refreshing expired token...")
            creds.refresh(Request())
        except Exception as e:
            print(f"Token refresh failed: {e}")
            creds = None

    # Run OAuth flow if needed
    if not creds or not creds.valid:
        if not CREDENTIALS_PATH.exists():
            raise GmailCredentialsNotFoundError(str(CREDENTIALS_PATH))

        print("Opening browser for Gmail authorization...")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes)
        creds = flow.run_local_server(port=0)

    # Save token
    save_token_from_credentials(creds)
    print(f"Token saved to {TOKEN_PATH}")

    # Get user email
    try:
        from googleapiclient.discovery import build
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress", "unknown")
        print(f"Logged in as: {email}")
    except Exception:
        email = "unknown"

    return GmailToken(
        access_token=creds.token,
        refresh_token=creds.refresh_token,
        token_type="Bearer",
        expires_at=creds.expiry if creds.expiry else None,
        scopes=list(creds.scopes) if creds.scopes else [],
    )
