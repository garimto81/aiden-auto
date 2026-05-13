#!/usr/bin/env python
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
import threading
import time
from pathlib import Path


def _resolve_state_file() -> str:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return str(Path(plugin_root) / "state" / "circuit-breaker.json")
    # Fallback: __file__ 기반 — hooks/ 의 부모 = plugin root
    return str(Path(__file__).resolve().parent.parent / "state" / "circuit-breaker.json")


STATE_FILE = _resolve_state_file()
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
    # Unique tmp per (pid, thread) — Windows shared-tmp PermissionError 방지
    tmp_path = f"{STATE_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    # Windows os.replace 는 target 잠금 시 PermissionError — 짧은 retry 로 흡수
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


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    cb = load_state()
    now = time.time()
    error = data.get("error", "") or ""

    # Troubleshooting guide (v28.3 FR-005)
    _TROUBLESHOOT = (
        " — 해결책: 1) /reset-breaker 로 즉시 리셋 / 2) 24h 후 자동 HALF_OPEN / "
        "3) 근본 원인 미해결 시 실패 로그 확인. 상세: commands/reset-breaker.md"
    )

    # State transitions
    if cb["state"] == "OPEN":
        if now - cb["last_failure"] >= OPEN_TIMEOUT:
            cb["state"] = "HALF_OPEN"
        else:
            save_state(cb)
            json.dump(
                {"decision": "block", "reason": f"Circuit breaker OPEN (backoff {cb['backoff']}s)" + _TROUBLESHOOT},
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
                {"decision": "block", "reason": f"Circuit breaker OPEN after {cb['failures']} failures" + _TROUBLESHOOT},
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
