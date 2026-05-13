"""
Slack CLI Entry Point

Usage:
    python -m lib.slack [COMMAND] [OPTIONS]

Commands:
    login      Authenticate with Slack via OAuth
    status     Check authentication status
    send       Send a message to a channel
    history    Read message history from a channel
    channels   List all accessible channels
    user       Get user information

Examples:
    python -m lib.slack login
    python -m lib.slack send "#general" "Hello, world!"
    python -m lib.slack history "#general" --limit 20
    python -m lib.slack channels --private
    python -m lib.slack user U01ABCDEF12
"""

from .cli import main

if __name__ == "__main__":
    main()
