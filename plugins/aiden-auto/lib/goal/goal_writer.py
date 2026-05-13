"""goal_writer.py — v28.2 /goal condition 생성 + 안전절 자동 첨가 + active-goal.json 저장

Schema: v1.0 (Section 13.1 정합)

사용:
  from lib.goal.goal_writer import write_goal_from_interview
  path = write_goal_from_interview(session_id, interview_answers)
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    lib/goal/ 기준: parent.parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"

# 안전절 hard-rule (CB Rule 17 정합)
DEFAULT_SAFETY_CLAUSES = [
    "or stop after 20 turns",
    "or stop after 200k tokens consumed",
    "or stop if Perfect Output Gate FAIL 5 times consecutively",
]


def _atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _goal_id(session_id: str, condition: str) -> str:
    h = hashlib.sha256((session_id + condition).encode()).hexdigest()[:8]
    return f"goal-{h}"


def append_safety_clauses(condition: str, custom: list[str] | None = None) -> str:
    """Append safety clauses if not already present."""
    clauses = custom if custom is not None else DEFAULT_SAFETY_CLAUSES
    for clause in clauses:
        if clause not in condition:
            condition = condition.rstrip(". ") + ". " + clause + "."
    return condition


def write_goal_from_interview(
    session_id: str,
    interview_answers: dict,
    raw_user_request: str = "",
) -> Path:
    """Construct goal condition from Deep Interview answers and persist to active-goal-{session_id}.json.

    Args:
        session_id: parent session ID
        interview_answers: dict like {"domain": "...", "acceptance": "...", "style": "..."}
        raw_user_request: original user plaintext (for traceability)

    Returns:
        Path to active-goal-{session_id}.json
    """
    # Compose verifiable condition text
    parts = []
    if domain := interview_answers.get("domain"):
        parts.append(domain)
    if acceptance := interview_answers.get("acceptance"):
        parts.append(acceptance)
    if style := interview_answers.get("style"):
        parts.append(f"스타일: {style}")
    # Production-ready boilerplate
    parts.append("모든 unit test PASS, console error 0건")

    condition = ". ".join(parts) + "."
    condition_with_safety = append_safety_clauses(condition)

    goal_id = _goal_id(session_id, condition_with_safety)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": goal_id,
        "session_id": session_id,
        "condition": condition_with_safety,
        "raw_user_request": raw_user_request,
        "interview_answers": interview_answers,
        "safety_clauses_applied": DEFAULT_SAFETY_CLAUSES,
        "created_at": _now_iso(),
        "achieved": False,
        "achieved_at": None,
        "turn_count": 0,
        "tokens_consumed": 0,
        "perfect_output_fails": 0,
    }

    path = STATE_DIR / f"active-goal-{session_id}.json"
    _atomic_write(path, payload)
    return path


def write_goal_from_explicit(
    session_id: str,
    explicit_condition: str,
    raw_user_request: str = "",
) -> Path:
    """User typed `/goal 'condition'` directly. Skip Deep Interview. Append safety clauses."""
    condition_with_safety = append_safety_clauses(explicit_condition)
    goal_id = _goal_id(session_id, condition_with_safety)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": goal_id,
        "session_id": session_id,
        "condition": condition_with_safety,
        "raw_user_request": raw_user_request,
        "interview_answers": None,
        "safety_clauses_applied": DEFAULT_SAFETY_CLAUSES,
        "created_at": _now_iso(),
        "achieved": False,
        "achieved_at": None,
        "turn_count": 0,
        "tokens_consumed": 0,
        "perfect_output_fails": 0,
    }
    path = STATE_DIR / f"active-goal-{session_id}.json"
    _atomic_write(path, payload)
    return path


def mark_achieved(session_id: str) -> bool:
    """When /goal evaluator confirms condition met."""
    path = STATE_DIR / f"active-goal-{session_id}.json"
    if not path.is_file():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    data["achieved"] = True
    data["achieved_at"] = _now_iso()
    _atomic_write(path, data)
    return True


def increment_counter(session_id: str, field: str, delta: int = 1) -> int:
    """Increment turn_count / perfect_output_fails / tokens_consumed."""
    path = STATE_DIR / f"active-goal-{session_id}.json"
    if not path.is_file():
        return 0
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    data[field] = int(data.get(field, 0)) + delta
    _atomic_write(path, data)
    return data[field]


def check_safety_limits(session_id: str) -> tuple[bool, str | None]:
    """Returns (ok, breach_reason). ok=False means safety clause tripped."""
    path = STATE_DIR / f"active-goal-{session_id}.json"
    if not path.is_file():
        return (True, None)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (True, None)
    if data.get("turn_count", 0) >= 20:
        return (False, "exceeded 20 turns")
    if data.get("tokens_consumed", 0) >= 200_000:
        return (False, "exceeded 200k tokens")
    if data.get("perfect_output_fails", 0) >= 5:
        return (False, "Perfect Output Gate FAIL 5 times")
    return (True, None)


if __name__ == "__main__":
    # Smoke test
    sid = "test-session-001"
    p = write_goal_from_interview(
        session_id=sid,
        interview_answers={
            "domain": "옆에서 보는 2D 평면 레이싱 게임 완성",
            "acceptance": "한 스테이지 클리어 가능 + STAGE CLEAR 메시지",
            "style": "도트 픽셀 아트",
        },
        raw_user_request="레이싱 게임 만들어",
    )
    print(f"Goal written: {p}")
    print(json.dumps(json.loads(p.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
