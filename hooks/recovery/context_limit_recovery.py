#!/usr/bin/env python3
"""PostToolUse hook: detect context/token limit errors and recommend compaction."""
import json
import sys


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    error = data.get("error", "") or ""
    if not error:
        return

    error_lower = error.lower()
    if "context limit" in error_lower or "context window" in error_lower or "token limit" in error_lower:
        sys.stderr.write(
            "Warning: Context limit approaching. Auto-compaction recommended.\n"
        )
        json.dump(
            {
                "decision": "block",
                "reason": "Context limit recovery: recommend compaction",
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
