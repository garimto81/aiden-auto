#!/usr/bin/env python3
"""PostToolUse hook: detect Edit tool failures and provide recovery guidance."""
import json
import sys


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "")
    if tool_name != "Edit":
        return

    error = data.get("error", "") or ""
    if not error:
        return

    error_lower = error.lower()
    if "not unique" in error_lower or "not found" in error_lower:
        sys.stderr.write(
            f"Warning: Edit failed: {error}. "
            "Read the file first, then retry with more context.\n"
        )
        json.dump(
            {
                "decision": "block",
                "reason": f"Edit recovery: {error}. Read file first, use more surrounding context.",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
