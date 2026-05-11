"""
Slack Library Custom Exceptions
"""


class SlackError(Exception):
    """Base Slack error"""
    pass


class SlackAuthError(SlackError):
    """Authentication failed (invalid token, no credentials file)"""
    pass


class SlackRateLimitError(SlackError):
    """Rate limit exceeded"""

    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class SlackAPIError(SlackError):
    """API returned error"""

    def __init__(self, error: str, response: dict = None):
        self.error = error
        self.response = response or {}
        super().__init__(f"Slack API error: {error}")


class SlackChannelNotFoundError(SlackAPIError):
    """Channel not found or not accessible"""

    def __init__(self, channel: str):
        super().__init__("channel_not_found", {"channel": channel})


class SlackTokenRevokedError(SlackAuthError):
    """Token has been revoked (app uninstalled)"""

    def __init__(self):
        super().__init__("Token has been revoked. Run 'python -m lib.slack login' again.")


class SlackCredentialsNotFoundError(SlackAuthError):
    """Credentials file not found"""

    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Credentials file not found: {path}\n"
            "Create a Slack App at https://api.slack.com/apps and save credentials."
        )


class SlackNetworkError(SlackError):
    """Network connection failed"""

    def __init__(self, message: str = "Network connection failed"):
        super().__init__(message)
