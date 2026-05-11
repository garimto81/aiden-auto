"""
Gmail API Client — gws CLI wrapper + Python API fallback

Primary: subprocess → gws gmail (structured JSON output)
Fallback: Python Gmail API (when gws unavailable)

Usage:
    from lib.gmail import GmailClient

    client = GmailClient()
    emails = client.list_emails(query="is:unread", max_results=10)
"""

import base64
import json
import shutil
import subprocess
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from googleapiclient.errors import HttpError

from .auth import get_credentials, TOKEN_PATH
from .models import GmailMessage, GmailLabel, GmailThread, GmailAttachment, SendResult
from .errors import (
    GmailError, GmailAuthError, GmailAPIError,
    GmailRateLimitError, GmailGwsNotFoundError,
)


class GmailClient:
    """Gmail API client with gws CLI + Python API fallback."""

    def __init__(self, credentials=None, prefer_gws: bool = True):
        """
        Initialize Gmail client.

        Args:
            credentials: Optional Google Credentials object
            prefer_gws: If True, try gws CLI first (default: True)
        """
        self._gws_available = prefer_gws and shutil.which("gws") is not None
        self._service = None

        if credentials is None:
            credentials = get_credentials()

        if credentials is None and not self._gws_available:
            raise GmailAuthError(
                f"Not authenticated. Run 'python -m lib.gmail login' first.\n"
                f"Token file not found: {TOKEN_PATH}"
            )

        self.credentials = credentials

    @property
    def service(self):
        """Lazy-init Google Gmail API service."""
        if self._service is None:
            from googleapiclient.discovery import build
            self._service = build("gmail", "v1", credentials=self.credentials)
        return self._service

    # ── gws CLI helpers ───────────────────────────────────────

    def _gws_call(self, resource: str, method: str, params: dict = None) -> dict:
        """
        Call gws CLI and return parsed JSON.

        Args:
            resource: API resource (e.g., "gmail.users.messages")
            method: API method (e.g., "list")
            params: API parameters

        Returns:
            Parsed JSON response

        Raises:
            GmailGwsNotFoundError: If gws not found
            GmailAPIError: If gws call fails
        """
        if not self._gws_available:
            raise GmailGwsNotFoundError("gws CLI not found")

        cmd = ["gws"] + resource.split(".") + [method]
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
                raise GmailAPIError(
                    f"gws command failed: {result.stderr.strip()}",
                    status_code=result.returncode,
                )

            return json.loads(result.stdout)
        except FileNotFoundError:
            self._gws_available = False
            raise GmailGwsNotFoundError("gws CLI not found")
        except json.JSONDecodeError as e:
            raise GmailAPIError(f"Failed to parse gws output: {e}")
        except subprocess.TimeoutExpired:
            raise GmailAPIError("gws command timed out (30s)")

    # ── Public API ────────────────────────────────────────────

    def get_profile(self) -> dict:
        """
        Get current user's profile.

        Returns:
            Profile dict with emailAddress, messagesTotal, threadsTotal
        """
        if self._gws_available:
            try:
                return self._gws_call("gmail.users", "getProfile", {"userId": "me"})
            except GmailGwsNotFoundError:
                pass

        try:
            return self.service.users().getProfile(userId="me").execute()
        except HttpError as e:
            self._handle_error(e)

    def validate_token(self) -> bool:
        """
        Validate current token by making a simple API call.

        Returns:
            True if token is valid, False otherwise
        """
        try:
            self.get_profile()
            return True
        except GmailError:
            return False

    def list_history(
        self,
        start_history_id: str,
        history_types: Optional[List[str]] = None,
        label_id: Optional[str] = None,
        max_results: int = 100,
    ) -> dict:
        """
        List history of changes since a given historyId.

        Args:
            start_history_id: Start historyId (from get_profile())
            history_types: Filter types (e.g., ["messageAdded", "labelAdded"])
            label_id: Filter by label ID
            max_results: Maximum history records

        Returns:
            Dict with 'history' list and 'historyId' (latest)
        """
        params = {
            "userId": "me",
            "startHistoryId": start_history_id,
            "maxResults": max_results,
        }
        if history_types:
            params["historyTypes"] = history_types
        if label_id:
            params["labelId"] = label_id

        if self._gws_available:
            try:
                return self._gws_call("gmail.users.history", "list", params)
            except GmailGwsNotFoundError:
                pass

        try:
            return self.service.users().history().list(**params).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return {"history": [], "historyId": start_history_id}
            self._handle_error(e)

    def get_message_metadata(self, message_id: str) -> dict:
        """
        Get message metadata only (no body, faster).

        Args:
            message_id: Message ID

        Returns:
            Dict with id, threadId, labelIds, snippet, historyId
        """
        if self._gws_available:
            try:
                return self._gws_call("gmail.users.messages", "get", {
                    "userId": "me",
                    "id": message_id,
                    "format": "metadata",
                    "metadataHeaders": ["From", "To", "Subject", "Date"],
                })
            except GmailGwsNotFoundError:
                pass

        try:
            return self.service.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            ).execute()
        except HttpError as e:
            self._handle_error(e)

    def list_emails(
        self,
        query: str = "",
        max_results: int = 10,
        label_ids: List[str] = None,
        include_spam_trash: bool = False,
    ) -> List[GmailMessage]:
        """
        List emails matching query.

        Args:
            query: Gmail search query (e.g., "is:unread", "from:boss@company.com")
            max_results: Maximum number of emails to return
            label_ids: Filter by label IDs (e.g., ["INBOX", "UNREAD"])
            include_spam_trash: Include spam and trash

        Returns:
            List of GmailMessage objects
        """
        params = {
            "userId": "me",
            "maxResults": max_results,
            "includeSpamTrash": include_spam_trash,
        }
        if query:
            params["q"] = query
        if label_ids:
            params["labelIds"] = label_ids

        if self._gws_available:
            try:
                data = self._gws_call("gmail.users.messages", "list", params)
                messages = data.get("messages", [])
                return [self.get_email(msg["id"]) for msg in messages]
            except GmailGwsNotFoundError:
                pass

        try:
            results = self.service.users().messages().list(**params).execute()
            messages = results.get("messages", [])

            return [self.get_email(msg["id"]) for msg in messages]
        except HttpError as e:
            self._handle_error(e)

    def get_email(self, email_id: str) -> GmailMessage:
        """
        Get full email details.

        Args:
            email_id: Email ID

        Returns:
            GmailMessage object
        """
        if self._gws_available:
            try:
                msg = self._gws_call("gmail.users.messages", "get", {
                    "userId": "me",
                    "id": email_id,
                    "format": "full",
                })
                return self._parse_message(msg)
            except GmailGwsNotFoundError:
                pass

        try:
            msg = self.service.users().messages().get(
                userId="me",
                id=email_id,
                format="full"
            ).execute()

            return self._parse_message(msg)
        except HttpError as e:
            self._handle_error(e)

    def get_thread(self, thread_id: str) -> GmailThread:
        """
        Get email thread (conversation).

        Args:
            thread_id: Thread ID

        Returns:
            GmailThread object
        """
        if self._gws_available:
            try:
                thread = self._gws_call("gmail.users.threads", "get", {
                    "userId": "me",
                    "id": thread_id,
                    "format": "full",
                })
                messages = [
                    self._parse_message(msg)
                    for msg in thread.get("messages", [])
                ]
                return GmailThread(
                    id=thread["id"],
                    snippet=thread.get("snippet", ""),
                    messages=messages,
                )
            except GmailGwsNotFoundError:
                pass

        try:
            thread = self.service.users().threads().get(
                userId="me",
                id=thread_id,
                format="full"
            ).execute()

            messages = [
                self._parse_message(msg)
                for msg in thread.get("messages", [])
            ]

            return GmailThread(
                id=thread["id"],
                snippet=thread.get("snippet", ""),
                messages=messages,
            )
        except HttpError as e:
            self._handle_error(e)

    def send(
        self,
        to: str,
        subject: str,
        body: str,
        cc: str = None,
        bcc: str = None,
        html: bool = False,
    ) -> SendResult:
        """
        Send an email.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body (plain text or HTML)
            cc: CC recipients (comma-separated)
            bcc: BCC recipients (comma-separated)
            html: If True, body is HTML

        Returns:
            SendResult object
        """
        try:
            if html:
                message = MIMEMultipart("alternative")
                message.attach(MIMEText(body, "html"))
            else:
                message = MIMEText(body)

            message["to"] = to
            message["subject"] = subject

            if cc:
                message["cc"] = cc
            if bcc:
                message["bcc"] = bcc

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            result = self.service.users().messages().send(
                userId="me",
                body={"raw": raw}
            ).execute()

            return SendResult(
                id=result["id"],
                thread_id=result.get("threadId", result["id"]),
            )
        except HttpError as e:
            self._handle_error(e)

    def reply(
        self,
        email_id: str,
        body: str,
        html: bool = False,
    ) -> SendResult:
        """
        Reply to an email.

        Args:
            email_id: Original email ID
            body: Reply body
            html: If True, body is HTML

        Returns:
            SendResult object
        """
        original = self.get_email(email_id)

        # Build reply subject
        subject = original.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"

        # Reply to sender
        to = original.sender

        # Create message
        if html:
            message = MIMEMultipart("alternative")
            message.attach(MIMEText(body, "html"))
        else:
            message = MIMEText(body)

        message["to"] = to
        message["subject"] = subject
        message["In-Reply-To"] = email_id
        message["References"] = email_id

        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

        try:
            result = self.service.users().messages().send(
                userId="me",
                body={
                    "raw": raw,
                    "threadId": original.thread_id,
                }
            ).execute()

            return SendResult(
                id=result["id"],
                thread_id=result.get("threadId", result["id"]),
            )
        except HttpError as e:
            self._handle_error(e)

    def list_labels(self) -> List[GmailLabel]:
        """
        List all labels.

        Returns:
            List of GmailLabel objects
        """
        if self._gws_available:
            try:
                data = self._gws_call("gmail.users.labels", "list", {"userId": "me"})
                labels = data.get("labels", [])
                return [
                    GmailLabel(
                        id=label["id"],
                        name=label["name"],
                        type=label.get("type", "user"),
                        messages_total=label.get("messagesTotal", 0),
                        messages_unread=label.get("messagesUnread", 0),
                    )
                    for label in labels
                ]
            except GmailGwsNotFoundError:
                pass

        try:
            results = self.service.users().labels().list(userId="me").execute()
            labels = results.get("labels", [])

            return [
                GmailLabel(
                    id=label["id"],
                    name=label["name"],
                    type=label.get("type", "user"),
                    messages_total=label.get("messagesTotal", 0),
                    messages_unread=label.get("messagesUnread", 0),
                )
                for label in labels
            ]
        except HttpError as e:
            self._handle_error(e)

    def modify_labels(
        self,
        email_id: str,
        add_labels: List[str] = None,
        remove_labels: List[str] = None,
    ) -> GmailMessage:
        """
        Modify email labels.

        Args:
            email_id: Email ID
            add_labels: Labels to add
            remove_labels: Labels to remove

        Returns:
            Updated GmailMessage
        """
        try:
            body = {}
            if add_labels:
                body["addLabelIds"] = add_labels
            if remove_labels:
                body["removeLabelIds"] = remove_labels

            self.service.users().messages().modify(
                userId="me",
                id=email_id,
                body=body
            ).execute()

            return self.get_email(email_id)
        except HttpError as e:
            self._handle_error(e)

    def mark_as_read(self, email_id: str) -> GmailMessage:
        """Mark email as read."""
        return self.modify_labels(email_id, remove_labels=["UNREAD"])

    def mark_as_unread(self, email_id: str) -> GmailMessage:
        """Mark email as unread."""
        return self.modify_labels(email_id, add_labels=["UNREAD"])

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download attachment binary data.

        Args:
            message_id: Gmail message ID
            attachment_id: Attachment ID (from GmailAttachment.id)

        Returns:
            bytes: Decoded binary data

        Raises:
            GmailAPIError: API call failure
        """
        try:
            result = self.service.users().messages().attachments().get(
                userId="me", messageId=message_id, id=attachment_id
            ).execute()
            return base64.urlsafe_b64decode(result["data"])
        except HttpError as e:
            self._handle_error(e)

    def archive(self, email_id: str) -> GmailMessage:
        """Archive email (remove from inbox)."""
        return self.modify_labels(email_id, remove_labels=["INBOX"])

    def trash(self, email_id: str) -> None:
        """Move email to trash."""
        try:
            self.service.users().messages().trash(userId="me", id=email_id).execute()
        except HttpError as e:
            self._handle_error(e)

    def _parse_message(self, msg: dict) -> GmailMessage:
        """
        Parse Gmail API message into GmailMessage.

        Args:
            msg: Raw message from API

        Returns:
            GmailMessage object
        """
        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        # Parse date
        date = None
        if "date" in headers:
            try:
                from email.utils import parsedate_to_datetime
                date = parsedate_to_datetime(headers["date"])
            except Exception:
                pass

        # Get body
        body_text, body_html = self._extract_body(msg.get("payload", {}))

        # Get attachments
        attachments = self._extract_attachments(msg.get("payload", {}))

        # Parse labels
        labels = msg.get("labelIds", [])
        is_unread = "UNREAD" in labels

        # Parse recipients
        to_list = [addr.strip() for addr in headers.get("to", "").split(",") if addr.strip()]
        cc_list = [addr.strip() for addr in headers.get("cc", "").split(",") if addr.strip()]

        return GmailMessage(
            id=msg["id"],
            thread_id=msg["threadId"],
            subject=headers.get("subject", ""),
            sender=headers.get("from", ""),
            to=to_list,
            cc=cc_list,
            date=date,
            snippet=msg.get("snippet", ""),
            body_text=body_text,
            body_html=body_html,
            labels=labels,
            is_unread=is_unread,
            has_attachments=len(attachments) > 0,
            attachments=attachments,
        )

    def _extract_body(self, payload: dict) -> tuple[str, str]:
        """Extract text and HTML body from payload."""
        body_text = ""
        body_html = ""

        def process_part(part):
            nonlocal body_text, body_html

            mime_type = part.get("mimeType", "")
            body = part.get("body", {})
            data = body.get("data")

            if data:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
                if mime_type == "text/plain":
                    body_text = decoded
                elif mime_type == "text/html":
                    body_html = decoded

            # Process nested parts
            for sub_part in part.get("parts", []):
                process_part(sub_part)

        process_part(payload)
        return body_text, body_html

    def _extract_attachments(self, payload: dict) -> List[GmailAttachment]:
        """Extract attachments from payload."""
        attachments = []

        def process_part(part):
            if part.get("filename"):
                body = part.get("body", {})
                attachments.append(GmailAttachment(
                    id=body.get("attachmentId", ""),
                    filename=part["filename"],
                    mime_type=part.get("mimeType", "application/octet-stream"),
                    size=body.get("size", 0),
                ))

            for sub_part in part.get("parts", []):
                process_part(sub_part)

        process_part(payload)
        return attachments

    def _handle_error(self, error: HttpError):
        """Convert HttpError to appropriate GmailError."""
        status = error.resp.status

        if status == 401:
            raise GmailAuthError("Authentication failed. Token may be expired. Run 'python -m lib.gmail login'")
        elif status == 429:
            raise GmailRateLimitError()
        elif status == 403:
            raise GmailAPIError("Permission denied. Check API scopes.", status_code=status)
        else:
            raise GmailAPIError(str(error), status_code=status)
