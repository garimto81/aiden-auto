#!/usr/bin/env python
"""Super Harness Framework v3.2 — Stage 3 Verification Retry Loop.

Triggered when Stage 3 QA Verification fails (3a/3b/3c/3d).

Flow:
  retry_count > 3 → Circuit breaker (escalate to user, receipt outcome="bad")
  retry_count ≤ 3 → Stage 2 auto retry with feedback + advisor-tool call

Status: STUB v0.1 — minimal state tracking. Real retry orchestration is
handled by the pipeline_dispatch hook + advisor-tool API.
PRD reference: C:\\claude\\docs\\00-prd\\super-harness-framework.prd.md §8
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", "C:/claude")
STATE_DIR = Path(PROJECT_DIR) / ".claude" / "state"
RETRY_STATE = STATE_DIR / "stage-3-retry-state.json"
CIRCUIT_BREAKER_LOG = STATE_DIR / "circuit-breaker-events.jsonl"

CB_LIMIT = 3


def load_state(session_id: str) -> dict:
    if not RETRY_STATE.exists():
        return {}
    try:
        return json.loads(RETRY_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    RETRY_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                           encoding="utf-8")


def log_circuit_breaker(session_id: str, retry_count: int, reason: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "session_id": session_id,
        "retry_count": retry_count,
        "reason": reason,
        "action": "escalate_to_user",
    }
    with CIRCUIT_BREAKER_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def handle_stage_3_failure(session_id: str, failure_reason: str) -> dict:
    """Increment retry counter, decide CB trip vs retry.

    Returns:
      {"action": "retry" | "circuit_breaker", "retry_count": N, ...}
    """
    state = load_state(session_id)
    session_state = state.get(session_id, {"retry_count": 0, "failures": []})
    session_state["retry_count"] += 1
    session_state["failures"].append({
        "date": datetime.now().isoformat(),
        "reason": failure_reason,
    })

    if session_state["retry_count"] > CB_LIMIT:
        log_circuit_breaker(session_id, session_state["retry_count"],
                            failure_reason)
        result = {
            "action": "circuit_breaker",
            "retry_count": session_state["retry_count"],
            "escalate": True,
        }
    else:
        result = {
            "action": "retry",
            "retry_count": session_state["retry_count"],
            "trigger_advisor": True,  # advisor-tool 호출 권장
            "feedback": failure_reason,
        }

    state[session_id] = session_state
    save_state(state)
    return result


def main() -> int:
    """Hook entry: read JSON from stdin, return verdict."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    session_id = payload.get("session_id", "unknown")
    failure_reason = payload.get("failure_reason", "unspecified")
    result = handle_stage_3_failure(session_id, failure_reason)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
