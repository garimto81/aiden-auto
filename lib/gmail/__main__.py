"""
Gmail CLI entry point.

Usage:
    python -m lib.gmail login
    python -m lib.gmail inbox
    python -m lib.gmail unread
    python -m lib.gmail read <email_id>
    python -m lib.gmail send "to@example.com" "Subject" "Body"
"""

from .cli import main

if __name__ == "__main__":
    main()
