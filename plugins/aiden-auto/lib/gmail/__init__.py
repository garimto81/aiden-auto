"""
Gmail Integration Library

OAuth 2.0 authentication, email sending/receiving, label management.

Usage:
    from lib.gmail import GmailClient, login, get_token

    # First time: OAuth flow
    login()

    # Create client
    client = GmailClient()

    # Send email
    result = client.send("to@example.com", "Subject", "Body")

    # Read inbox
    emails = client.list_emails(query="is:unread", max_results=10)

    # Get email detail
    email = client.get_email(email_id)

    # List labels
    labels = client.list_labels()

CLI Usage:
    python -m lib.gmail login
    python -m lib.gmail status
    python -m lib.gmail inbox --limit 10
    python -m lib.gmail unread
    python -m lib.gmail read <email_id>
    python -m lib.gmail send "to@example.com" "Subject" "Body"
    python -m lib.gmail labels
    python -m lib.gmail search "from:boss@company.com"
"""

__version__ = "1.0.0"

from .client import GmailClient
from .auth import login, get_token, get_credentials
from .models import (
    GmailCredentials,
    GmailToken,
    GmailMessage,
    GmailLabel,
    GmailThread,
    SendResult,
)
from .errors import (
    GmailError,
    GmailAuthError,
    GmailRateLimitError,
    GmailAPIError,
    GmailCredentialsNotFoundError,
    GmailNetworkError,
)

__all__ = [
    # Version
    "__version__",
    # Client
    "GmailClient",
    # Auth
    "login",
    "get_token",
    "get_credentials",
    # Models
    "GmailCredentials",
    "GmailToken",
    "GmailMessage",
    "GmailLabel",
    "GmailThread",
    "SendResult",
    # Errors
    "GmailError",
    "GmailAuthError",
    "GmailRateLimitError",
    "GmailAPIError",
    "GmailCredentialsNotFoundError",
    "GmailNetworkError",
]
