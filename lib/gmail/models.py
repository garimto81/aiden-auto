"""
Gmail Library Pydantic Models
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, computed_field


class GmailCredentials(BaseModel):
    """OAuth credentials from desktop_credentials.json"""

    client_id: str
    client_secret: str
    project_id: Optional[str] = None
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    redirect_uris: List[str] = ["http://localhost"]


class GmailToken(BaseModel):
    """OAuth token stored in gmail_token.json"""

    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: List[str] = []

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if not self.expires_at:
            return False
        return datetime.now() >= self.expires_at


class GmailAttachment(BaseModel):
    """Email attachment."""

    id: str
    filename: str
    mime_type: str
    size: int = 0


class GmailMessage(BaseModel):
    """Gmail message."""

    id: str
    thread_id: str
    subject: str = ""
    sender: str = ""  # From header
    to: List[str] = []
    cc: List[str] = []
    date: Optional[datetime] = None
    snippet: str = ""
    body_text: str = ""
    body_html: str = ""
    labels: List[str] = []
    is_unread: bool = False
    has_attachments: bool = False
    attachments: List[GmailAttachment] = []

    @computed_field
    @property
    def permalink(self) -> str:
        """Generate Gmail web URL."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.id}"


class GmailLabel(BaseModel):
    """Gmail label."""

    id: str
    name: str
    type: str = "user"  # system or user
    messages_total: int = 0
    messages_unread: int = 0

    @computed_field
    @property
    def is_system(self) -> bool:
        """Check if this is a system label."""
        return self.type == "system"


class GmailThread(BaseModel):
    """Gmail thread (conversation)."""

    id: str
    snippet: str = ""
    messages: List[GmailMessage] = []

    @computed_field
    @property
    def message_count(self) -> int:
        """Number of messages in thread."""
        return len(self.messages)


class SendResult(BaseModel):
    """Result of sending an email."""

    id: str
    thread_id: str

    @computed_field
    @property
    def permalink(self) -> str:
        """Generate Gmail web URL."""
        return f"https://mail.google.com/mail/u/0/#sent/{self.id}"
