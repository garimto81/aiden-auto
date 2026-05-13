#!/usr/bin/env python
"""PreToolUse Loop Detector — blocks identical tool call patterns repeated 3x.

Tracks a sliding window of the last 5 PreToolUse fingerprints.
Fingerprint = sha256(tool_name + canonical JSON input)[:16].
If the last 3 fingerprints are identical → output block decision.
Uses atomic write (os.replace) to prevent state file corruption.
"""
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path


def _resolve_state_file() -> str:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return str(Path(plugin_root) / "state" / "loop-detector.json")
    return str(Path(__file__).resolve().parent.parent / "state" / "loop-detector.json")


STATE_FILE = _resolve_state_file()
WINDOW_SIZE = 5
BLOCK_THRESHOLD = 3


def load_state() -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"history": [], "updated_at": 0}


def save_state(state: dict) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    # Unique tmp per (pid, thread) — Windows shared-tmp PermissionError 방지
    tmp_path = f"{STATE_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    # Windows os.replace 잠금 시 PermissionError — 짧은 retry 로 흡수
    for attempt in range(5):
        try:
            os.replace(tmp_path, STATE_FILE)
            return
        except PermissionError:
            if attempt == 4:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
            time.sleep(0.005 * (attempt + 1))


def make_fingerprint(tool_name: str, tool_input: dict) -> str:
    canonical = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)
    raw = f"{tool_name}:{canonical}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def main() -> None:
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    tool_name = data.get("tool_name", "") or ""
    tool_input = data.get("tool_input", {}) or {}

    # Exclude read-only and state-free tools to avoid false positives
    if tool_name in ("Read", "Glob", "Grep", "LS"):
        return

    fingerprint = make_fingerprint(tool_name, tool_input)
    state = load_state()
    history: list = state.get("history", [])

    history.append({"fp": fingerprint, "tool": tool_name, "ts": time.time()})
    if len(history) > WINDOW_SIZE:
        history = history[-WINDOW_SIZE:]

    state["history"] = history
    state["updated_at"] = time.time()
    save_state(state)

    if len(history) >= BLOCK_THRESHOLD:
        recent = [h["fp"] for h in history[-BLOCK_THRESHOLD:]]
        if len(set(recent)) == 1:
            json.dump(
                {
                    "decision": "block",
                    "reason": (
                        f"Loop detected: '{tool_name}' repeated {BLOCK_THRESHOLD}x "
                        f"with identical input (fp={fingerprint}). "
                        "Escalate to user — circuit breaker may be bypassed."
                    ),
                },
                sys.stdout,
            )


if __name__ == "__main__":
    main()
