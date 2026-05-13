"""
Calendar Library Error Classes
"""


class CalendarError(Exception):
    """Base exception for Calendar errors."""
    pass


class CalendarAuthError(CalendarError):
    """Authentication error."""
    pass


class CalendarCredentialsNotFoundError(CalendarError):
    """Credentials file not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Credentials file not found: {path}\n"
            "Please create the file with your OAuth client credentials.\n"
            "See: https://console.cloud.google.com/apis/credentials"
        )


class CalendarRateLimitError(CalendarError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        msg = "Calendar API rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)


class CalendarAPIError(CalendarError):
    """API error from Calendar."""

    def __init__(self, error: str, status_code: int = None):
        self.error = error
        self.status_code = status_code
        super().__init__(f"Calendar API error: {error}")


class CalendarGwsNotFoundError(CalendarError):
    """gws CLI not found, falling back to Python API."""
    pass
