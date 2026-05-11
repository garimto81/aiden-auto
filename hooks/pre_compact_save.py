#!/usr/bin/env python3
"""PreCompact hook: save team and task state before context compaction."""
import glob
import json
import os
import sys
from datetime import datetime, timezone

SNAPSHOT_FILE = "C:/claude/.claude/hooks/.pre_compact_snapshot.json"
HOME = os.path.expanduser("~")
TEAMS_DIR = os.path.join(HOME, ".claude", "teams")
TASKS_DIR = os.path.join(HOME, ".claude", "tasks")


def scan_teams():
    teams = []
    pattern = os.path.join(TEAMS_DIR, "**", "config.json")
    for path in glob.glob(pattern, recursive=True):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                teams.append({"path": path, "name": data.get("name", "unknown")})
        except (json.JSONDecodeError, OSError):
            teams.append({"path": path, "name": "unreadable", "error": str(e) if 'e' in dir() else "parse_error"})
    return teams


def scan_tasks():
    summary = {"total": 0, "completed": 0, "in_progress": 0, "pending": 0}
    if not os.path.isdir(TASKS_DIR):
        return summary
    for entry in os.listdir(TASKS_DIR):
        path = os.path.join(TASKS_DIR, entry)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                status = data.get("status", "pending")
                summary["total"] += 1
                if status in summary:
                    summary[status] += 1
        except (json.JSONDecodeError, OSError):
            summary["total"] += 1
    return summary


def main():
    # Read stdin (hook contract) but we don't need its content
    try:
        sys.stdin.read()
    except Exception:
        pass

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "teams": scan_teams(),
        "tasks_summary": scan_tasks(),
    }

    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)

    sys.stderr.write(f"Pre-compact snapshot saved: {snapshot['tasks_summary']['total']} tasks\n")


if __name__ == "__main__":
    main()
