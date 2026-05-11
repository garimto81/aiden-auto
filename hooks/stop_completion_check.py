#!/usr/bin/env python3
"""Stop hook: block session end if tasks are still incomplete.

NOTE: SDK block behavior unverified for Stop event.
The 'block' decision may not prevent session end in all SDK versions.
"""
import json
import os
import sys

HOME = os.path.expanduser("~")
TASKS_DIR = os.path.join(HOME, ".claude", "tasks")


def main():
    # Read stdin (hook contract)
    try:
        sys.stdin.read()
    except Exception:
        pass

    incomplete = []
    if not os.path.isdir(TASKS_DIR):
        return

    for entry in os.listdir(TASKS_DIR):
        path = os.path.join(TASKS_DIR, entry)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                status = data.get("status", "")
                if status in ("in_progress", "pending"):
                    subject = data.get("subject", entry)
                    incomplete.append(subject)
        except (json.JSONDecodeError, OSError):
            continue

    if incomplete:
        names = ", ".join(incomplete[:5])
        suffix = f" (+{len(incomplete)-5} more)" if len(incomplete) > 5 else ""
        sys.stderr.write(
            f"Warning: {len(incomplete)} tasks still incomplete: {names}{suffix}\n"
        )
        json.dump(
            {"decision": "block", "reason": f"Incomplete tasks detected: {len(incomplete)} remaining"},
            sys.stdout,
        )


if __name__ == "__main__":
    main()
