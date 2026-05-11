"""
Slack OAuth 2.0 Authentication

Usage:
    from lib.slack.auth import login, get_token

    # First time: OAuth flow
    token = login()

    # Subsequent: Load from file
    token = get_token()
"""

import json
import socket
import webbrowser
import http.server
import urllib.parse
from pathlib import Path
from datetime import datetime
from typing import Optional

import requests

from .models import SlackCredentials, SlackToken, SlackTeam
from .errors import SlackAuthError, SlackCredentialsNotFoundError


# File paths — __file__ 기반 상대 경로 (이식성)
_BASE = Path(__file__).resolve().parent.parent.parent  # → C:/claude/
CREDENTIALS_PATH = _BASE / "json" / "slack_credentials.json"
TOKEN_PATH = _BASE / "json" / "slack_token.json"
USER_TOKEN_PATH = _BASE / "json" / "slack_user_token.json"

# Default OAuth scopes (Bot Token)
DEFAULT_SCOPES = [
    "chat:write",
    "channels:read",
    "channels:history",
    "groups:read",
    "groups:history",
    "im:write",
    "users:read",
]

# User Token scopes (for features not available to bots)
USER_SCOPES = [
    "chat:write",
    "lists:read",
    "lists:write",
]

# Port range for OAuth callback
PORTS = [8765, 8766, 8767, 8768, 8769, 8770]


def load_credentials() -> SlackCredentials:
    """
    Load OAuth credentials from file.

    Returns:
        SlackCredentials object

    Raises:
        SlackCredentialsNotFoundError: If credentials file not found
    """
    if not CREDENTIALS_PATH.exists():
        raise SlackCredentialsNotFoundError(str(CREDENTIALS_PATH))

    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return SlackCredentials(**data)
    except (json.JSONDecodeError, KeyError) as e:
        raise SlackAuthError(f"Invalid credentials file: {e}")


def get_bot_token_from_credentials() -> Optional[str]:
    """
    Check if bot_token is directly provided in credentials file.

    Returns:
        Bot token string if exists, None otherwise
    """
    if not CREDENTIALS_PATH.exists():
        return None

    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return data.get("bot_token")
    except (json.JSONDecodeError, KeyError):
        return None


def get_user_token_from_credentials() -> Optional[str]:
    """
    Check if user_token is directly provided in credentials file.

    Returns:
        User token string (xoxp-...) if exists, None otherwise
    """
    if not CREDENTIALS_PATH.exists():
        return None

    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
        return data.get("user_token")
    except (json.JSONDecodeError, KeyError):
        return None


def create_token_from_user_token(user_token: str) -> SlackToken:
    """
    Create SlackToken from direct user token.

    Validates token with auth.test API and creates token object.

    Args:
        user_token: User OAuth Token (xoxp-...)

    Returns:
        SlackToken object

    Raises:
        SlackAuthError: If token is invalid
    """
    # Validate token with auth.test
    response = requests.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {user_token}"},
        timeout=10,
    )

    data = response.json()
    if not data.get("ok"):
        raise SlackAuthError(f"Invalid user token: {data.get('error', 'unknown')}")

    team = SlackTeam(
        id=data.get("team_id", ""),
        name=data.get("team", ""),
    )

    return SlackToken(
        access_token=user_token,
        token_type="user",
        scope="",  # Not available from auth.test
        bot_user_id="",
        app_id=data.get("app_id", ""),
        team=team,
        authed_user={"id": data.get("user_id", "")},
        created_at=datetime.now(),
    )


def create_token_from_bot_token(bot_token: str) -> SlackToken:
    """
    Create SlackToken from direct bot token.

    Validates token with auth.test API and creates token object.

    Args:
        bot_token: Bot User OAuth Token (xoxb-...)

    Returns:
        SlackToken object

    Raises:
        SlackAuthError: If token is invalid
    """
    # Validate token with auth.test
    response = requests.post(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {bot_token}"},
        timeout=10,
    )

    data = response.json()
    if not data.get("ok"):
        raise SlackAuthError(f"Invalid bot token: {data.get('error', 'unknown')}")

    team = SlackTeam(
        id=data.get("team_id", ""),
        name=data.get("team", ""),
    )

    return SlackToken(
        access_token=bot_token,
        token_type="bot",
        scope="",  # Not available from auth.test
        bot_user_id=data.get("user_id", ""),
        app_id=data.get("app_id", ""),
        team=team,
        authed_user=None,
        created_at=datetime.now(),
    )


def build_auth_url(
    credentials: SlackCredentials,
    port: int,
    scopes: list[str] = None,
    user_scopes: list[str] = None,
) -> str:
    """
    Build Slack OAuth authorization URL.

    Args:
        credentials: OAuth app credentials
        port: Local callback server port
        scopes: Bot OAuth scopes (default: DEFAULT_SCOPES)
        user_scopes: User OAuth scopes (for user token features like Lists)

    Returns:
        Authorization URL string
    """
    scopes = scopes or DEFAULT_SCOPES
    redirect_uri = f"http://localhost:{port}/slack/oauth/callback"

    params = {
        "client_id": credentials.client_id,
        "scope": ",".join(scopes),
        "redirect_uri": redirect_uri,
    }

    # Add user_scope for user token features (e.g., lists:read, lists:write)
    if user_scopes:
        params["user_scope"] = ",".join(user_scopes)

    query = urllib.parse.urlencode(params)
    return f"https://slack.com/oauth/v2/authorize?{query}"


def exchange_code(credentials: SlackCredentials, code: str, port: int) -> tuple[SlackToken, Optional[SlackToken]]:
    """
    Exchange authorization code for access token(s).

    Args:
        credentials: OAuth app credentials
        code: Authorization code from callback
        port: Local callback server port

    Returns:
        Tuple of (bot_token, user_token). user_token is None if not requested.

    Raises:
        SlackAuthError: If token exchange fails
    """
    redirect_uri = f"http://localhost:{port}/slack/oauth/callback"

    response = requests.post(
        "https://slack.com/api/oauth.v2.access",
        data={
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "code": code,
            "redirect_uri": redirect_uri,
        }
    )

    data = response.json()

    if not data.get("ok"):
        error = data.get("error", "unknown")
        raise SlackAuthError(f"Token exchange failed: {error}")

    team_data = data.get("team", {})
    team = SlackTeam(
        id=team_data.get("id", ""),
        name=team_data.get("name", ""),
    )

    # Bot token
    bot_token = SlackToken(
        access_token=data["access_token"],
        token_type=data.get("token_type", "bot"),
        scope=data.get("scope", ""),
        bot_user_id=data.get("bot_user_id", ""),
        app_id=data.get("app_id", ""),
        team=team,
        authed_user=data.get("authed_user"),
        created_at=datetime.now(),
    )

    # User token (if user_scope was requested)
    user_token = None
    authed_user = data.get("authed_user", {})
    if authed_user and authed_user.get("access_token"):
        user_token = SlackToken(
            access_token=authed_user["access_token"],
            token_type="user",
            scope=authed_user.get("scope", ""),
            bot_user_id="",
            app_id=data.get("app_id", ""),
            team=team,
            authed_user={"id": authed_user.get("id", "")},
            created_at=datetime.now(),
        )

    return bot_token, user_token


def save_token(token: SlackToken, path: Path = None) -> None:
    """
    Save token to file.

    Args:
        token: SlackToken to save
        path: File path (default: TOKEN_PATH for bot, USER_TOKEN_PATH for user)
    """
    # Determine path based on token type
    if path is None:
        path = USER_TOKEN_PATH if token.token_type == "user" else TOKEN_PATH

    # Ensure directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict
    data = {
        "access_token": token.access_token,
        "token_type": token.token_type,
        "scope": token.scope,
        "bot_user_id": token.bot_user_id,
        "app_id": token.app_id,
        "team": {
            "id": token.team.id,
            "name": token.team.name,
        },
        "authed_user": token.authed_user,
        "created_at": token.created_at.isoformat() if token.created_at else None,
    }

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def find_available_port() -> int:
    """
    Find an available port for OAuth callback server.

    Returns:
        Available port number

    Raises:
        SlackAuthError: If no ports available
    """
    for port in PORTS:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("localhost", port))
                return port
        except OSError:
            continue

    raise SlackAuthError(f"No available ports for OAuth callback (tried {PORTS})")


def get_token() -> Optional[SlackToken]:
    """
    Load token from file or credentials.

    Priority:
    1. bot_token in credentials file (direct token)
    2. token.json file (OAuth token)

    Returns:
        SlackToken if available, None otherwise
    """
    # Priority 1: Check for direct bot_token in credentials
    bot_token = get_bot_token_from_credentials()
    if bot_token:
        try:
            return create_token_from_bot_token(bot_token)
        except SlackAuthError as e:
            import sys
            print(f"[WARN] Bot token validation failed: {e}", file=sys.stderr)

    # Priority 2: Check token file
    if not TOKEN_PATH.exists():
        return None

    try:
        data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))

        team_data = data.get("team", {})
        team = SlackTeam(
            id=team_data.get("id", ""),
            name=team_data.get("name", ""),
        )

        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass

        return SlackToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "bot"),
            scope=data.get("scope", ""),
            bot_user_id=data.get("bot_user_id", ""),
            app_id=data.get("app_id", ""),
            team=team,
            authed_user=data.get("authed_user"),
            created_at=created_at,
        )
    except (json.JSONDecodeError, KeyError):
        return None


class OAuthCallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler for OAuth callback."""

    def log_message(self, format, *args):
        """Suppress logging."""
        pass

    def do_GET(self):
        """Handle OAuth callback."""
        parsed = urllib.parse.urlparse(self.path)

        if parsed.path == "/slack/oauth/callback":
            query = urllib.parse.parse_qs(parsed.query)

            if "code" in query:
                self.server.auth_code = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Login Successful!</h1>"
                    b"<p>You can close this window.</p></body></html>"
                )
            elif "error" in query:
                error = query.get("error", ["unknown"])[0]
                self.server.auth_error = error
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    f"<html><body><h1>Login Failed</h1><p>Error: {error}</p></body></html>".encode()
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing code parameter")
        else:
            self.send_response(404)
            self.end_headers()


def login(port: int = None, include_user_scopes: bool = False) -> SlackToken:
    """
    Perform OAuth flow to get access token.

    If bot_token is directly provided in credentials, use it instead of OAuth.

    Args:
        port: Callback server port (auto-detected if None)
        include_user_scopes: If True, also request user token with lists:read/write

    Returns:
        SlackToken object (bot token)

    Raises:
        SlackAuthError: If login fails
    """
    # Check for direct bot_token first
    bot_token = get_bot_token_from_credentials()
    if bot_token and not include_user_scopes:
        print("Found bot_token in credentials, validating...")
        token = create_token_from_bot_token(bot_token)
        save_token(token)
        print(f"Token saved to {TOKEN_PATH}")
        print(f"Logged in as bot: {token.bot_user_id} in workspace: {token.team.name}")
        return token

    # Load credentials for OAuth
    credentials = load_credentials()

    # Find available port
    if port is None:
        port = find_available_port()

    # Build authorization URL
    user_scopes = USER_SCOPES if include_user_scopes else None
    auth_url = build_auth_url(credentials, port, user_scopes=user_scopes)

    print("Opening browser for Slack authorization...")
    if include_user_scopes:
        print(f"Requesting user scopes: {', '.join(USER_SCOPES)}")
    print(f"If browser doesn't open, visit: {auth_url}")

    # Start local server
    server_address = ("localhost", port)
    httpd = http.server.HTTPServer(server_address, OAuthCallbackHandler)
    httpd.auth_code = None
    httpd.auth_error = None

    # Open browser
    webbrowser.open(auth_url)

    # Wait for callback
    print(f"Waiting for authorization on port {port}...")
    httpd.handle_request()

    # Check result
    if httpd.auth_error:
        raise SlackAuthError(f"Authorization failed: {httpd.auth_error}")

    if not httpd.auth_code:
        raise SlackAuthError("No authorization code received")

    # Exchange code for token
    print("Exchanging code for token...")
    bot_token, user_token = exchange_code(credentials, httpd.auth_code, port)

    # Save bot token
    save_token(bot_token)
    print(f"Bot token saved to {TOKEN_PATH}")
    print(f"Logged in as bot: {bot_token.bot_user_id} in workspace: {bot_token.team.name}")

    # Save user token if obtained
    if user_token:
        save_token(user_token)
        print(f"User token saved to {USER_TOKEN_PATH}")
        print(f"User scopes: {user_token.scope}")

    return bot_token


def get_user_token() -> Optional[SlackToken]:
    """
    Load user token from file or credentials.

    Priority:
    1. user_token in credentials file (direct token)
    2. slack_user_token.json file

    Returns:
        SlackToken if available, None otherwise
    """
    # Priority 1: Check for direct user_token in credentials
    user_token = get_user_token_from_credentials()
    if user_token:
        try:
            return create_token_from_user_token(user_token)
        except SlackAuthError as e:
            import sys
            print(f"[WARN] User token validation failed: {e}", file=sys.stderr)

    # Priority 2: Check token file
    if not USER_TOKEN_PATH.exists():
        return None

    try:
        data = json.loads(USER_TOKEN_PATH.read_text(encoding="utf-8"))

        team_data = data.get("team", {})
        team = SlackTeam(
            id=team_data.get("id", ""),
            name=team_data.get("name", ""),
        )

        created_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"])
            except (ValueError, TypeError):
                pass

        return SlackToken(
            access_token=data["access_token"],
            token_type=data.get("token_type", "user"),
            scope=data.get("scope", ""),
            bot_user_id=data.get("bot_user_id", ""),
            app_id=data.get("app_id", ""),
            team=team,
            authed_user=data.get("authed_user"),
            created_at=created_at,
        )
    except (json.JSONDecodeError, KeyError):
        return None
