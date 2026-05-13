#!/usr/bin/env python
"""
hooks/telemetry_update.py — statusline telemetry 동적 채움

Owner: aiden-auto plugin (Core Philosophy 흡수)
Trigger:
  PreToolUse  + matcher Task|Agent   → subagent_type / model 추출
  PostToolUse + matcher Task|Agent   → updated_at touch (전환 표시)
  SessionStart                       → circuit-breaker 동기화

State file (host SSOT):
  read+write   ~/.claude/state/telemetry.json
  read         ~/.claude/state/circuit-breaker.json (있으면)

Silent on any failure — statusline must never crash CC.
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()
STATE_DIR = HOME / ".claude" / "state"
TELEMETRY_PATH = STATE_DIR / "telemetry.json"
BREAKER_PATH = STATE_DIR / "circuit-breaker.json"

BREAKER_LIMITS = {
    "architect_reject":  3,
    "pdca_iterator":     5,
    "continuation_loop": 3,
    "auto_recursion":    1,
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


def sync_breaker(state):
    """circuit-breaker.json → telemetry breaker_i/n + pdca_i/n"""
    breaker = read_json(BREAKER_PATH)
    if not breaker:
        return state

    worst_i, worst_n = 0, 1
    for key, lim in BREAKER_LIMITS.items():
        try:
            cur = int(breaker.get(key, 0) or 0)
        except Exception:
            cur = 0
        if lim > 0 and (cur / lim) > (worst_i / worst_n):
            worst_i, worst_n = cur, lim
    state["breaker_i"] = worst_i
    state["breaker_n"] = worst_n

    try:
        state["pdca_i"] = int(breaker.get("pdca_iterator", 0) or 0)
        state["pdca_n"] = BREAKER_LIMITS["pdca_iterator"]
    except Exception:
        pass

    return state


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main():
    event = read_stdin()
    hook = event.get("hook_event_name", "")
    state = read_json(TELEMETRY_PATH)

    if hook == "PreToolUse":
        tool = event.get("tool_name", "")
        if tool in ("Task", "Agent"):
            ti = event.get("tool_input", {}) or {}
            agent = ti.get("subagent_type")
            model = ti.get("model")
            if agent:
                state["agent"] = agent
            if model:
                state["model"] = model

    elif hook == "PostToolUse":
        # 전환 표시만 — agent 유지 (display continuity)
        pass

    elif hook == "SessionStart":
        # 첫 진입 시 breaker 동기화만
        pass

    state = sync_breaker(state)
    state["updated_at"] = now_iso()
    write_atomic(TELEMETRY_PATH, state)


if __name__ == "__main__":
    main()
