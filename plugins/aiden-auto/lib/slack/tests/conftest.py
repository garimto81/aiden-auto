"""
Shared test fixtures for Slack library tests
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime


@pytest.fixture
def mock_slack_response():
    """Factory for creating mock Slack API responses"""
    def _create_response(data: dict, ok: bool = True):
        response = Mock()
        response.data = {"ok": ok, **data}
        response.__getitem__ = lambda self, key: self.data[key]
        response.get = lambda key, default=None: self.data.get(key, default)
        return response
    return _create_response


@pytest.fixture
def mock_webclient(mock_slack_response):
    """Mock slack_sdk WebClient"""
    with patch("lib.slack.client.WebClient") as mock_class:
        mock_client = MagicMock()
        mock_class.return_value = mock_client

        # Default successful responses
        mock_client.chat_postMessage.return_value = mock_slack_response({
            "ts": "1234567890.123456",
            "channel": "C01ABCDEF12",
            "message": {"text": "Hello"}
        })

        mock_client.conversations_history.return_value = mock_slack_response({
            "messages": [
                {"ts": "1234567890.123456", "text": "Hello", "user": "U123"},
                {"ts": "1234567890.123457", "text": "World", "user": "U456"},
            ],
            "has_more": False
        })

        mock_client.conversations_list.return_value = mock_slack_response({
            "channels": [
                {"id": "C123", "name": "general", "is_private": False},
                {"id": "C456", "name": "random", "is_private": False},
            ]
        })

        mock_client.users_info.return_value = mock_slack_response({
            "user": {
                "id": "U123",
                "name": "johndoe",
                "real_name": "John Doe",
                "profile": {"email": "john@example.com"}
            }
        })

        mock_client.auth_test.return_value = mock_slack_response({
            "user_id": "U123",
            "team_id": "T123",
            "bot_id": "B123"
        })

        yield mock_client


@pytest.fixture
def sample_token():
    """Sample SlackToken for testing"""
    from lib.slack.models import SlackToken, SlackTeam

    return SlackToken(
        access_token="xoxb-test-token-123",
        token_type="bot",
        scope="chat:write,channels:read,channels:history",
        bot_user_id="U01TESTBOT",
        app_id="A01TESTAPP",
        team=SlackTeam(id="T01TESTTEAM", name="Test Workspace"),
        created_at=datetime.now()
    )


@pytest.fixture
def sample_credentials():
    """Sample SlackCredentials for testing"""
    from lib.slack.models import SlackCredentials

    return SlackCredentials(
        client_id="123456789.123456789012",
        client_secret="test_secret_abc123"
    )


@pytest.fixture
def mock_token_file(tmp_path, sample_token):
    """Create a temporary token file"""
    import json

    token_file = tmp_path / "slack_token.json"
    token_data = sample_token.model_dump()
    token_data["team"] = {"id": sample_token.team.id, "name": sample_token.team.name}
    token_data["created_at"] = sample_token.created_at.isoformat() if sample_token.created_at else None

    token_file.write_text(json.dumps(token_data))
    return token_file


@pytest.fixture
def mock_credentials_file(tmp_path, sample_credentials):
    """Create a temporary credentials file"""
    import json

    creds_file = tmp_path / "slack_credentials.json"
    creds_file.write_text(json.dumps(sample_credentials.model_dump()))
    return creds_file
