#!/usr/bin/env python3
"""State-file based Circuit Breaker hook.

States: CLOSED (normal) -> OPEN (blocked) -> HALF_OPEN (testing)
- CLOSED: failures >= 3 -> OPEN
- OPEN: after 30s -> HALF_OPEN
- HALF_OPEN: success -> CLOSED / failure -> OPEN
Exponential backoff: 1s, 2s, 4s recorded in state file.
"""
import json
import os
import sys
import time

STATE_FILE = "C:/claude/.claude/hooks/.circuit_breaker_state.json"
FAILURE_THRESHOLD = 3
OPEN_TIMEOUT = 30  # seconds


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    return {"state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    cb = load_state()
    now = time.time()
    error = data.get("error", "") or ""

    # State transitions
    if cb["state"] == "OPEN":
        if now - cb["last_failure"] >= OPEN_TIMEOUT:
            cb["state"] = "HALF_OPEN"
        else:
            save_state(cb)
            json.dump(
                {"decision": "block", "reason": f"Circuit breaker OPEN (backoff {cb['backoff']}s)"},
                sys.stdout,
            )
            return

    if error:
        cb["failures"] = cb.get("failures", 0) + 1
        cb["last_failure"] = now
        if cb["state"] == "HALF_OPEN" or cb["failures"] >= FAILURE_THRESHOLD:
            cb["state"] = "OPEN"
            cb["backoff"] = min(cb.get("backoff", 1) * 2, 4)
            save_state(cb)
            json.dump(
                {"decision": "block", "reason": f"Circuit breaker OPEN after {cb['failures']} failures"},
                sys.stdout,
            )
            return
    else:
        if cb["state"] == "HALF_OPEN":
            cb["state"] = "CLOSED"
            cb["failures"] = 0
            cb["backoff"] = 1

    save_state(cb)


if __name__ == "__main__":
    main()
