"""
Gmail Library Error Classes
"""


class GmailError(Exception):
    """Base exception for Gmail errors."""
    pass


class GmailAuthError(GmailError):
    """Authentication error."""
    pass


class GmailCredentialsNotFoundError(GmailError):
    """Credentials file not found."""

    def __init__(self, path: str):
        self.path = path
        super().__init__(
            f"Credentials file not found: {path}\n"
            "Please create the file with your OAuth client credentials.\n"
            "See: https://console.cloud.google.com/apis/credentials"
        )


class GmailRateLimitError(GmailError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int = None):
        self.retry_after = retry_after
        msg = "Gmail API rate limit exceeded."
        if retry_after:
            msg += f" Retry after {retry_after} seconds."
        super().__init__(msg)


class GmailAPIError(GmailError):
    """API error from Gmail."""

    def __init__(self, error: str, status_code: int = None):
        self.error = error
        self.status_code = status_code
        super().__init__(f"Gmail API error: {error}")


class GmailGwsNotFoundError(GmailError):
    """gws CLI not found."""
    pass


class GmailNetworkError(GmailError):
    """Network-related error."""
    pass
