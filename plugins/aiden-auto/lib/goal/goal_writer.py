"""goal_writer.py — v28.3 /goal condition 생성 + 안전절 자동 첨가 + active-goal.json 저장

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

SCHEMA_VERSION = "1.1"

# Q4 (multi-session 선택) 추천 알고리즘 (intake-interviewer.md 정본 의사코드와 정합)
def recommend_multi_session(task_signals: dict) -> tuple[str, str]:
    """프로젝트 분석 기반 multi-session 단일 추천안 산출.

    Signal 우선순위 (HARD RULE): 1 > 2 > 3 > default. `elif` chain short-circuit.

    Args:
        task_signals: triage가 산출한 dict. 부재 필드는 보수 default(B).
            estimated_lines: int
            has_plan: bool
            independent_tasks_count: int
            long_running_streams: int
            estimated_hours: int|float

    Returns:
        (option_letter, rationale_one_line)
    """
    if task_signals.get("estimated_lines", float("inf")) < 100:
        return ("B", "작업 작음 → 단발 위임")
    elif (task_signals.get("has_plan")
          and task_signals.get("independent_tasks_count", 0) >= 3):
        return ("C", "plan + 독립 task 다수 → 2-stage 리뷰")
    elif (task_signals.get("long_running_streams", 0) >= 3
          and task_signals.get("estimated_hours", 0) >= 8):
        return ("A", "큰 stream 다수 → 진짜 병렬 필요")
    else:
        return ("B", "scope 불확실 → 가장 가벼움")


# 옛 processing_method 숫자 → 신규 A/B/C/D 매핑 (intake-interviewer.md "LEGACY_MAP" 정합)
LEGACY_PROCESSING_METHOD_MAP = {
    "1": "D",  # Claude 자율 → D
    "2": "B",  # Parallel Agent in-session → B
    "3": "A",  # claude agents → A
    "4": "B",  # Background subagent → B (보수 fallback)
    "5": "B",  # Sequential → B (multi-session 아님, 보수 fallback)
}

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
    task_signals: dict | None = None,
) -> Path:
    """Construct goal condition from Deep Interview answers and persist to active-goal-{session_id}.json.

    Schema v1.1 (2026-05-19): adds Q4 multi_session_method + multi_session_method_resolved.
    Q3 field renamed: "style" → "approach" (back-compat: both keys read).

    Args:
        session_id: parent session ID
        interview_answers: dict with keys:
            - domain (Q1): required
            - acceptance (Q2): required
            - approach (Q3): optional, falls back to "style" for back-compat
            - multi_session_method (Q4): "A"/"B"/"C"/"D", default "D"
        raw_user_request: original user plaintext (for traceability)
        task_signals: optional dict for Q4 recommendation (estimated_lines, has_plan, ...)
            Used when multi_session_method == "D" to compute resolved option.

    Returns:
        Path to active-goal-{session_id}.json
    """
    # Compose verifiable condition text (v1.1: includes approach)
    parts = []
    if domain := interview_answers.get("domain"):
        parts.append(domain)
    if acceptance := interview_answers.get("acceptance"):
        parts.append(acceptance)
    # Q3: "approach" (v1.1) with "style" (v1.0) back-compat
    approach_value = interview_answers.get("approach") or interview_answers.get("style")
    if approach_value:
        parts.append(f"접근: {approach_value}")
    # Production-ready boilerplate
    parts.append("모든 unit test PASS, console error 0건")

    condition = ". ".join(parts) + "."
    condition_with_safety = append_safety_clauses(condition)

    # Q4: resolve multi_session_method (D → run recommendation)
    method = interview_answers.get("multi_session_method", "D")
    if method == "D":
        if task_signals:
            resolved, _ = recommend_multi_session(task_signals)
        else:
            resolved = "B"  # 보수 default
    elif method in ("A", "B", "C"):
        resolved = method
    else:
        # 옛 숫자 (1-5) LEGACY_MAP 변환
        resolved = LEGACY_PROCESSING_METHOD_MAP.get(str(method), "B")

    goal_id = _goal_id(session_id, condition_with_safety)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": goal_id,
        "session_id": session_id,
        "condition": condition_with_safety,
        "raw_user_request": raw_user_request,
        "interview_answers": interview_answers,
        "multi_session_method_resolved": resolved,
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
    multi_session_method: str = "D",
    task_signals: dict | None = None,
) -> Path:
    """User typed `/goal 'condition'` directly. Skip Deep Interview. Append safety clauses.

    Schema v1.1 (2026-05-19): adds multi_session_method_resolved (D → recommend).
    """
    condition_with_safety = append_safety_clauses(explicit_condition)

    # Resolve multi_session_method (Q4 spec 정합)
    if multi_session_method == "D":
        if task_signals:
            resolved, _ = recommend_multi_session(task_signals)
        else:
            resolved = "B"
    elif multi_session_method in ("A", "B", "C"):
        resolved = multi_session_method
    else:
        resolved = LEGACY_PROCESSING_METHOD_MAP.get(str(multi_session_method), "B")

    goal_id = _goal_id(session_id, condition_with_safety)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "id": goal_id,
        "session_id": session_id,
        "condition": condition_with_safety,
        "raw_user_request": raw_user_request,
        "interview_answers": None,
        "multi_session_method_resolved": resolved,
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
