#!/usr/bin/env python
"""goal_stop_evaluator.py — v28.2 prompt-based Stop hook for /auto's /goal mechanism

CC 공식 prompt-based Stop hook 패턴 (`/en/hooks#prompt-based-hooks`).
/goal command가 wrapping하는 동일한 메커니즘을 우리가 직접 등록.

Flow:
  매 turn 종료 → 본 hook 발화 → active-goal.json condition vs Claude transcript 매칭
  → continue=true (다음 turn) 또는 continue=false (goal achieved)

Output (CC Stop hook contract):
  stdout: { "continue": true|false, "reason": "..." }
  exit 0
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    hooks/ 폴더 기준: parent = hooks/, parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"

try:
    sys.path.insert(0, str(PLUGIN_ROOT))
    from lib.goal.goal_writer import (
        check_safety_limits,
        increment_counter,
        mark_achieved,
    )
except ImportError:
    check_safety_limits = None
    increment_counter = None
    mark_achieved = None


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def _find_active_goal(session_id: str | None) -> tuple[Path | None, dict | None]:
    if session_id:
        path = STATE_DIR / f"active-goal-{session_id}.json"
        if path.is_file():
            return (path, _read_json(path))
    # fallback: most recent active-goal-*.json
    candidates = list(STATE_DIR.glob("active-goal-*.json"))
    if not candidates:
        return (None, None)
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return (latest, _read_json(latest))


def _evaluate_condition(condition: str, transcript_excerpt: str) -> tuple[bool, str]:
    """Lightweight transcript matching. For full eval, defer to /goal's built-in evaluator.

    This hook does NOT replace /goal's Haiku evaluator — it complements it as
    a safety net: tripping safety clauses + tracking turn count.

    Heuristics:
    - "Validation Statement" 문장 검출 → likely achieved
    - "STAGE CLEAR" or explicit success markers
    - "FAIL" / "ERROR" markers → not achieved
    """
    # Cheap heuristic
    transcript_excerpt_lower = transcript_excerpt.lower()
    success_markers = [
        "validation statement",
        "all pass",
        "goal achieved",
        "✅ pass",
        "stage clear",
        "perfect output gate.*all pass",
    ]
    fail_markers = [
        "❌ fail",
        "perfect output gate.*fail",
        "blocked",
    ]

    has_success = any(m in transcript_excerpt_lower for m in success_markers)
    has_fail = any(m in transcript_excerpt_lower for m in fail_markers)

    if has_success and not has_fail:
        return (True, "transcript contains success markers + Validation Statement")
    if has_fail:
        return (False, "transcript contains FAIL markers — continue iteration")
    return (False, "no terminal markers detected — continue")


def main() -> int:
    # Stop hook input: { session_id, transcript_excerpt, ... }
    try:
        hook_input = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        hook_input = {}

    session_id = hook_input.get("session_id")
    transcript = hook_input.get("transcript_excerpt", "")

    goal_path, goal_data = _find_active_goal(session_id)
    if goal_data is None:
        # No active goal → don't loop (let CC default Stop behavior apply)
        print(json.dumps({"continue": False, "reason": "no active goal"}))
        return 0

    # Increment turn counter
    sid_for_counter = goal_data.get("session_id", session_id or "unknown")
    if increment_counter:
        increment_counter(sid_for_counter, "turn_count", 1)

    # Safety check (turn count, tokens, perfect output fails)
    if check_safety_limits:
        ok, reason = check_safety_limits(sid_for_counter)
        if not ok:
            print(json.dumps({
                "continue": False,
                "reason": f"safety clause tripped: {reason}",
                "achieved": False,
            }))
            return 0

    # Condition evaluation
    condition = goal_data.get("condition", "")
    achieved, eval_reason = _evaluate_condition(condition, transcript)

    if achieved:
        if mark_achieved:
            mark_achieved(sid_for_counter)
        print(json.dumps({
            "continue": False,
            "reason": eval_reason,
            "achieved": True,
        }))
    else:
        print(json.dumps({
            "continue": True,
            "reason": eval_reason,
            "achieved": False,
        }))

    return 0


if __name__ == "__main__":
    sys.exit(main())
