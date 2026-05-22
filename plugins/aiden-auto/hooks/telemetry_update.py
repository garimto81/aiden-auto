#!/usr/bin/env python
"""
hooks/telemetry_update.py — line 1 process chain (v4.2).

v4.2 additions over v4.1:
  - Background detection: run_in_background=true → suffix '⟳' on tag
  - SubagentStop: marks most-recent 'Agent:*⟳' as 'Agent:*✓' in-place
  - Dedup: same tag pushed within 500ms is skipped (avoids double-fire
    when both plugin hook + user-settings hook trigger for Task|Agent)

Per-session isolation: ~/.claude/state/telemetry-{session_id}.json

Trigger (combined plugin + user-settings registration):
  PreToolUse   → classify tool_name → push process tag (⟳ if bg)
  PostToolUse  → push 'Deliberating' (if last != 'Deliberating')
  SubagentStop → mark most-recent 'Agent:*⟳' → 'Agent:*✓';
                 if last tag is 'Awaiting' and no ⟳ remain, transition to 'Idle'
  Stop         → if any ⟳ in queue → 'Awaiting' (bg still running),
                 else → 'Idle' (truly idle)
  SessionStart → no-op

Silent on any failure — statusline must never crash CC.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
STATE_DIR = HOME / ".claude" / "state"

QUEUE_MAX = 6
DEDUP_WINDOW_MS = 500
SESSION_SAFE = re.compile(r"[^A-Za-z0-9_-]")

PROCESS_TAGS = {
    "Read": "Reading",
    "Edit": "Editing",
    "Write": "Editing",
    "MultiEdit": "Editing",
    "NotebookEdit": "Editing",
    "NotebookRead": "Reading",
    "Grep": "Searching",
    "Glob": "Searching",
    "Bash": "Bash",
    "PowerShell": "Bash",
    "BashOutput": "BashOutput",
    "KillShell": "KillShell",
    "Monitor": "Monitor",
    "TodoWrite": "Todo",
    "TaskCreate": "Todo",
    "TaskUpdate": "Todo",
    "TaskList": "Todo",
    "TaskGet": "Todo",
    "TaskOutput": "Todo",
    "TaskStop": "Todo",
    "WebFetch": "Web",
    "WebSearch": "Web",
    "ExitPlanMode": "Plan",
    "EnterPlanMode": "Plan",
    "EnterWorktree": "Worktree",
    "ExitWorktree": "Worktree",
    "ToolSearch": "ToolSearch",
    "Skill": "Skill",
    "AskUserQuestion": "Asking",
    "ScheduleWakeup": "Schedule",
    "PushNotification": "Notify",
    "RemoteTrigger": "Remote",
    "SendMessage": "Send",
}


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_atomic(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(str(tmp), str(path))
    except Exception:
        pass


def read_stdin():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw else {}
    except Exception:
        return {}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_ms():
    return int(time.time() * 1000)


def safe_session(session_id):
    if not session_id:
        return "default"
    cleaned = SESSION_SAFE.sub("_", str(session_id))
    return cleaned or "default"


def session_path(session_id):
    return STATE_DIR / f"telemetry-{safe_session(session_id)}.json"


def classify_tool(tool_name, tool_input):
    if tool_name in ("Task", "Agent"):
        sub = (tool_input or {}).get("subagent_type", "agent")
        return f"Agent:{sub}"
    if tool_name and tool_name.startswith("mcp__"):
        return "MCP"
    return PROCESS_TAGS.get(tool_name, tool_name.lower() if tool_name else "tool")


def mark_most_recent_bg_done(queue):
    """Find the most-recent 'Agent:*⟳' tag and mark as completed (✓)."""
    for i in range(len(queue) - 1, -1, -1):
        tag = queue[i]
        if tag.endswith("⟳") and tag.startswith("Agent"):
            queue[i] = tag[:-1] + "✓"
            return True
    return False


def main():
    event = read_stdin()
    hook = event.get("hook_event_name", "")
    session_id = event.get("session_id", "")
    path = session_path(session_id)
    state = read_json(path)
    queue = list(state.get("processes", []))

    new_tag = None

    if hook == "PreToolUse":
        tool_name = event.get("tool_name", "")
        tool_input = event.get("tool_input") or {}
        bg = bool(tool_input.get("run_in_background"))
        tag = classify_tool(tool_name, tool_input)
        if bg:
            tag = f"{tag}⟳"
        new_tag = tag
    elif hook == "PostToolUse":
        if not queue or queue[-1] != "Deliberating":
            new_tag = "Deliberating"
    elif hook == "SubagentStop":
        # Mark most recent Agent:*⟳ as ✓
        mark_most_recent_bg_done(queue)
        # If trailing tag is 'Awaiting' and no more ⟳ in queue → auto-transition to Idle
        if queue and queue[-1] == "Awaiting":
            if not any(t.endswith("⟳") for t in queue):
                queue[-1] = "Idle"
    elif hook == "Stop":
        # Claude response finished. If background work still running → 'Awaiting',
        # otherwise truly idle waiting for user input → 'Idle'.
        has_bg = any(t.endswith("⟳") for t in queue)
        target = "Awaiting" if has_bg else "Idle"
        if queue and queue[-1] == "Deliberating":
            queue[-1] = target
        elif not queue or queue[-1] != target:
            new_tag = target
    # SessionStart and others: no-op

    # Dedup: same tag pushed within DEDUP_WINDOW_MS is skipped
    skip = False
    if new_tag:
        last_ms = state.get("last_push_at_ms", 0)
        last_tag = queue[-1] if queue else None
        if last_tag == new_tag and (now_ms() - last_ms) < DEDUP_WINDOW_MS:
            skip = True

    if new_tag and not skip:
        queue.append(new_tag)
        queue = queue[-QUEUE_MAX:]
        state["last_push_at_ms"] = now_ms()

    state["processes"] = queue
    state["session_id"] = session_id or "default"
    state["updated_at"] = now_iso()
    write_atomic(path, state)


if __name__ == "__main__":
    main()
