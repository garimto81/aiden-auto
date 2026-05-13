"""
Slack Integration Library

Browser OAuth authentication, message sending/receiving, channel management.

Usage:
    from lib.slack import SlackClient, login, get_token

    # First time: OAuth flow
    login()

    # Create client (bot token)
    client = SlackClient()

    # Send message
    result = client.send_message("#general", "Hello!")

    # Read history
    messages = client.get_history("#general", limit=10)

    # List channels
    channels = client.list_channels(include_private=True)

User Token (for Slack Lists API):
    from lib.slack import SlackUserClient

    # First time: OAuth with user scopes
    # python -m lib.slack login --user

    # Create client with user token
    client = SlackUserClient()

    # Create Slack List
    result = client.create_list("My List", "Description")

CLI Usage:
    python -m lib.slack login           # Bot token only
    python -m lib.slack login --user    # Bot + User token (for Lists API)
    python -m lib.slack send "#general" "Hello!"
    python -m lib.slack history "#general"
    python -m lib.slack channels
"""

__version__ = "1.0.0"

from .client import SlackClient, SlackUserClient, RateLimiter, load_token
from .auth import login, get_token, get_user_token, load_credentials, save_token
from .models import (
    SlackCredentials,
    SlackTeam,
    SlackToken,
    SlackMessage,
    SlackChannel,
    SlackUser,
    SendResult,
)
from .errors import (
    SlackError,
    SlackAuthError,
    SlackRateLimitError,
    SlackAPIError,
    SlackChannelNotFoundError,
    SlackTokenRevokedError,
    SlackCredentialsNotFoundError,
    SlackNetworkError,
)

__all__ = [
    # Version
    "__version__",
    # Client
    "SlackClient",
    "SlackUserClient",
    "RateLimiter",
    "load_token",
    # Auth
    "login",
    "get_token",
    "get_user_token",
    "load_credentials",
    "save_token",
    # Models
    "SlackCredentials",
    "SlackTeam",
    "SlackToken",
    "SlackMessage",
    "SlackChannel",
    "SlackUser",
    "SendResult",
    # Errors
    "SlackError",
    "SlackAuthError",
    "SlackRateLimitError",
    "SlackAPIError",
    "SlackChannelNotFoundError",
    "SlackTokenRevokedError",
    "SlackCredentialsNotFoundError",
    "SlackNetworkError",
]
