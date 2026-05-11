"""
Calendar CLI entry point.

Usage:
    python -m lib.calendar login
    python -m lib.calendar today
    python -m lib.calendar week
    python -m lib.calendar list --days 14
    python -m lib.calendar create "Meeting" "2026-03-15 14:00"
"""

from .cli import main

if __name__ == "__main__":
    main()
