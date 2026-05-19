#!/usr/bin/env python
"""goal_stop_evaluator.py — v28.3 prompt-based Stop hook for /auto's /goal mechanism

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

# Multi-path STATE_DIR 검색 (정본 호출 / plugin cache 호출 양쪽 지원)
# Root cause (2026-05-19): 정본 ~/.claude/hooks/ 에서 호출 시 PLUGIN_ROOT fallback
# 이 ~/.claude/ 로 도출 → ~/.claude/state/ 검색 → active-goal 미존재.
# 실제 active-goal 은 plugin cache state 에 있음.
# v2 정정 (W4): plugin 버전 번호 하드코딩 제거 → glob 패턴 으로 동적 해소.
def _discover_plugin_state_dirs() -> list[Path]:
    """plugin cache 의 모든 버전 디렉토리 동적 검색."""
    base = Path.home() / ".claude" / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"
    if not base.is_dir():
        return []
    # 각 버전 디렉토리의 state/ 폴더 수집 (예: 28.3.0/state, 28.4.0/state, ...)
    return [v / "state" for v in base.iterdir() if v.is_dir()]

STATE_DIR_CANDIDATES = [
    PLUGIN_ROOT / "state",  # plugin cache 또는 명시 PLUGIN_ROOT (1순위)
    *_discover_plugin_state_dirs(),  # 동적 plugin 버전 모두 (2순위)
    Path.home() / ".claude" / "state",  # 정본 fallback (3순위)
]

def _find_state_dir() -> Path:
    """active-goal-*.json 이 존재하는 첫 디렉토리 반환. 없으면 첫 후보."""
    for d in STATE_DIR_CANDIDATES:
        if d.is_dir() and any(d.glob("active-goal-*.json")):
            return d
    return STATE_DIR_CANDIDATES[0]

STATE_DIR = _find_state_dir()

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
        # No active goal → silent (CC 기본 종료 동작, prevent continuation 신호 X)
        # Root cause fix (2026-05-19): 이전엔 continue=false 출력 → CC가 "block"으로 해석.
        # 이제 stdout 비워서 CC가 자연 종료하도록.
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
