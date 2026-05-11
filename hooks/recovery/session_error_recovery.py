#!/usr/bin/env python3
"""PostToolUse hook: detect session-related errors (timeout, connection) and guide recovery."""
import json
import sys


SESSION_ERROR_KEYWORDS = ["connection refused", "disconnected", "session expired", "ETIMEDOUT", "ECONNRESET"]


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    error = data.get("error", "") or ""
    if not error:
        return

    error_lower = error.lower()
    if any(kw.lower() in error_lower for kw in SESSION_ERROR_KEYWORDS):
        sys.stderr.write(
            f"Warning: Session error detected: {error[:120]}. "
            "Retry the operation or restart the session.\n"
        )
        json.dump(
            {
                "decision": "block",
                "reason": f"Session error recovery: {error[:200]}. Recommend retry.",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
