#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""goal_loop_state.py — /goal Loop state tracker (F6 결함 해소).

⚠ DEPRECATED (B-018, 2026-05-28): Stop hook 단일화로 미사용.
   /goal 안전절(20턴/200K/5실패)은 goal_stop_evaluator.py 의 check_safety_limits 가
   active-goal-{session}.json 기반으로 단독 수행한다. 본 모듈의 PreToolUse 사전 차단 설계는
   auto_workflow_enforcer 가 호출하지 않아 phantom 이었다 (hook_events.db 발동 0회).
   파일은 재도입 시 참조용으로 보존 ("Removal isn't the answer"). 신규 호출 추가 금지.

⭐ Universal Deployment Premise 정합.

기능:
  · turn counter (Agent() 호출 후 increment)
  · token counter (API usage 누적)
  · fail counter (Agent() result error)
  · safety trip detector (20 turns / 200k tokens / 5 fails)

State file: ~/.claude/state/auto/goal-loop-{session_id}.json

6 기준 자체 평가: 6/6 PASS (path_resolution 활용, idempotent, EXCLUDE state).

PRD: aiden-auto-self-replication.prd.md (F6)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "hooks"))
try:
    from path_resolution import resolve_global_claude  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"

GLOBAL_CLAUDE = resolve_global_claude()
STATE_AUTO = GLOBAL_CLAUDE / "state" / "auto"
STATE_AUTO.mkdir(parents=True, exist_ok=True)

DEFAULT_LIMITS = {
    "turn_limit": 20,
    "token_limit": 200_000,
    "fail_limit": 5,
}


def get_session_id() -> str:
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
    return sid if sid else time.strftime("%Y%m%d-%H%M%S")


def state_path(session_id: str) -> Path:
    return STATE_AUTO / f"goal-loop-{session_id}.json"


def init_state(session_id: str, category: str = "", goal: str = "") -> dict:
    """신규 session state 초기화 (idempotent — 기존 file 있으면 보존)."""
    p = state_path(session_id)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    state = {
        "session_id": session_id,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "category": category,
        "chapter": f"chapter-{category.lower()}" if category else "",
        "current_phase": None,
        "counters": {
            "turn": 0,
            "token_used": 0,
            "fail": 0,
            **DEFAULT_LIMITS,
        },
        "phase_history": [],
        "active_goal": {"summary": goal, "acceptance_criteria": []},
        "pending": [],
        "next_action": None,
        "trip_status": "RUNNING",
        "trip_reason": None,
    }
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    return state


def load_state(session_id: str) -> dict | None:
    p = state_path(session_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def save_state(state: dict) -> None:
    p = state_path(state["session_id"])
    try:
        p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def increment_turn(session_id: str) -> dict:
    """매 Agent() 호출 후 호출. safety trip 검사."""
    state = load_state(session_id)
    if not state:
        state = init_state(session_id)

    state["counters"]["turn"] += 1
    trip = check_safety_trip(state)
    save_state(state)
    return {"state": state, "trip": trip}


def add_token_usage(session_id: str, tokens: int) -> dict:
    state = load_state(session_id)
    if not state:
        state = init_state(session_id)
    state["counters"]["token_used"] += tokens
    trip = check_safety_trip(state)
    save_state(state)
    return {"state": state, "trip": trip}


def increment_fail(session_id: str, reason: str = "") -> dict:
    state = load_state(session_id)
    if not state:
        state = init_state(session_id)
    state["counters"]["fail"] += 1
    state.setdefault("fail_log", []).append({
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reason": reason[:200],
    })
    trip = check_safety_trip(state)
    save_state(state)
    return {"state": state, "trip": trip}


def check_safety_trip(state: dict) -> dict | None:
    """3 safety trip 조건 검사.

    Returns:
        None (정상) 또는 {"reason": "TURN_LIMIT"|"TOKEN_LIMIT"|"FAIL_LIMIT", ...}
    """
    counters = state["counters"]
    if counters["turn"] >= counters["turn_limit"]:
        state["trip_status"] = "TRIPPED"
        state["trip_reason"] = "TURN_LIMIT"
        return {"reason": "TURN_LIMIT", "value": counters["turn"], "limit": counters["turn_limit"]}
    if counters["token_used"] >= counters["token_limit"]:
        state["trip_status"] = "TRIPPED"
        state["trip_reason"] = "TOKEN_LIMIT"
        return {"reason": "TOKEN_LIMIT", "value": counters["token_used"], "limit": counters["token_limit"]}
    if counters["fail"] >= counters["fail_limit"]:
        state["trip_status"] = "TRIPPED"
        state["trip_reason"] = "FAIL_LIMIT"
        return {"reason": "FAIL_LIMIT", "value": counters["fail"], "limit": counters["fail_limit"]}
    return None


def complete_phase(session_id: str, phase: str) -> dict:
    """Phase 완료 시 호출."""
    state = load_state(session_id)
    if not state:
        return {"error": "session not found"}
    state["phase_history"].append({
        "phase": phase,
        "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })
    state["current_phase"] = phase
    save_state(state)
    return state


def report_status(session_id: str) -> dict:
    state = load_state(session_id)
    if not state:
        return {"error": "session not found"}
    return {
        "session_id": session_id,
        "trip_status": state["trip_status"],
        "trip_reason": state.get("trip_reason"),
        "counters": state["counters"],
        "current_phase": state.get("current_phase"),
        "remaining": {
            "turn": state["counters"]["turn_limit"] - state["counters"]["turn"],
            "token": state["counters"]["token_limit"] - state["counters"]["token_used"],
            "fail": state["counters"]["fail_limit"] - state["counters"]["fail"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="/goal Loop state tracker")
    sub = parser.add_subparsers(dest="cmd", required=True)

    s_init = sub.add_parser("init")
    s_init.add_argument("--session", default=get_session_id())
    s_init.add_argument("--category", default="")
    s_init.add_argument("--goal", default="")

    s_turn = sub.add_parser("turn")
    s_turn.add_argument("--session", default=get_session_id())

    s_token = sub.add_parser("token")
    s_token.add_argument("--session", default=get_session_id())
    s_token.add_argument("amount", type=int)

    s_fail = sub.add_parser("fail")
    s_fail.add_argument("--session", default=get_session_id())
    s_fail.add_argument("--reason", default="")

    s_phase = sub.add_parser("phase")
    s_phase.add_argument("--session", default=get_session_id())
    s_phase.add_argument("name")

    s_status = sub.add_parser("status")
    s_status.add_argument("--session", default=get_session_id())

    args = parser.parse_args()

    if args.cmd == "init":
        state = init_state(args.session, args.category, args.goal)
        print(json.dumps(state, indent=2, ensure_ascii=False))
    elif args.cmd == "turn":
        result = increment_turn(args.session)
        print(json.dumps({"turn": result["state"]["counters"]["turn"], "trip": result["trip"]}, indent=2))
    elif args.cmd == "token":
        result = add_token_usage(args.session, args.amount)
        print(json.dumps({"token_used": result["state"]["counters"]["token_used"], "trip": result["trip"]}, indent=2))
    elif args.cmd == "fail":
        result = increment_fail(args.session, args.reason)
        print(json.dumps({"fail": result["state"]["counters"]["fail"], "trip": result["trip"]}, indent=2))
    elif args.cmd == "phase":
        state = complete_phase(args.session, args.name)
        print(json.dumps({"current_phase": state.get("current_phase"), "history_count": len(state["phase_history"])}, indent=2))
    elif args.cmd == "status":
        print(json.dumps(report_status(args.session), indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
