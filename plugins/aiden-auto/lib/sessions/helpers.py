"""helpers.py — Phase 5B: spawn_with_registration() 통합 helper

session_registry + agent_view_adapter + event_schema 를 하나의 호출로 묶는다.

비유: session_registry 는 '명부', agent_view_adapter 는 '실제 채용 창구',
      event_schema 는 '입사 통보 문서'. 이 helper 는 세 기관을 한 번에 처리하는
      '원스톱 채용 대행사'.

사용 예:
    from lib.sessions.helpers import spawn_with_registration, SpawnOptions

    result = spawn_with_registration(
        parent_task="goal-frontend-redesign",
        kind="VISUAL_INTERACTION",
        condition="redesign homepage",
        options=SpawnOptions(
            scope="frontend",
            goal_title="홈페이지 리디자인",
            estimated_effort_days=3.0,
            user="user@example.com",
        ),
    )
    if result.success:
        print(f"세션 시작됨: {result.session_id}")
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

# 같은 패키지 내 모듈 임포트
from . import event_schema as es
from . import session_registry as sr
from ..adapters import agent_view_adapter as av


@dataclass
class SpawnOptions:
    """spawn_with_registration() 에 전달하는 선택 옵션."""
    scope: str = ""                         # 도메인 범위 (예: "frontend", "backend", "infra")
    goal_title: str = ""                    # 사용자 목표 요약 제목
    estimated_effort_days: float = 0.0      # 예상 소요 일수
    user: str = ""                          # 생성자 식별자 (이메일 등)
    task_description: str = ""              # claude --bg 에 전달할 task 문자열


@dataclass
class SpawnResult:
    """spawn_with_registration() 반환값."""
    success: bool
    session_id: str                         # 신규 or 재사용된 session ID
    reused: bool = False                    # True = 중복 감지, 기존 세션 재사용
    error: str = ""                         # 실패 시 원인


def spawn_with_registration(
    parent_task: str,
    kind: sr.SessionKind,
    condition: str,
    options: SpawnOptions | None = None,
) -> SpawnResult:
    """세션을 등록하고 백그라운드 agent 를 실행한 뒤 INITIATED 이벤트를 발화한다.

    처리 순서:
    1. session_registry 에서 중복 체크 (같은 parent_task + condition_hash)
    2. 중복이면 기존 세션 반환 (spawn 건너뜀)
    3. 신규이면 session 등록 → agent_view_adapter.spawn_background()
    4. spawn 성공 시 INITIATED 이벤트를 events.jsonl 에 기록
    5. 실패 시 session 상태를 FAILED 로 갱신
    """
    opts = options or SpawnOptions()

    # 1-2. 중복 체크
    condition_hash = sr._short_hash(condition, length=16)
    existing = sr.find_duplicate(parent_task, condition_hash)
    if existing:
        return SpawnResult(
            success=True,
            session_id=existing.id,
            reused=True,
        )

    # 3. 신규 세션 등록
    session = sr.register_session(
        parent_task=parent_task,
        kind=kind,
        condition=condition,
        scope=opts.scope,
    )

    # 4. 백그라운드 spawn (task_description 이 없으면 condition 을 task 로 사용)
    task_str = opts.task_description or condition
    spawn_ok, spawn_info = av.spawn_background(
        task=task_str,
        name_prefix=f"{session.id}:",
    )

    if not spawn_ok:
        # spawn 실패 → session 상태 FAILED 로 전환
        sr.update_status(session.id, "FAILED")
        _emit_event(
            session_id=session.id,
            parent_task=parent_task,
            status="ERROR",
            opts=opts,
            extra={"error": spawn_info},
        )
        return SpawnResult(success=False, session_id=session.id, error=spawn_info)

    # 5. INITIATED 이벤트 발화
    _emit_event(
        session_id=session.id,
        parent_task=parent_task,
        status="INITIATED",
        opts=opts,
        extra={"spawn_info": spawn_info},
    )

    return SpawnResult(success=True, session_id=session.id, reused=False)


def _emit_event(
    session_id: str,
    parent_task: str,
    status: es.EventStatus,
    opts: SpawnOptions,
    extra: dict,
) -> None:
    """INITIATED / ERROR 이벤트를 events.jsonl 에 기록한다."""
    created_by = es.SessionCreatedBy(
        user=opts.user or os.environ.get("USER", os.environ.get("USERNAME", "")),
        email=opts.user if "@" in opts.user else "",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    meta = es.SessionMeta(
        created_by=vars(created_by),
        scope=opts.scope,
        goal_title=opts.goal_title,
        estimated_effort_days=opts.estimated_effort_days,
    )
    payload_data = {**meta.to_dict(), **extra}

    ev = es.EventBuilder.create(
        session_id=session_id,
        status=status,
        progress_meta=es.ProgressMeta(current_step=0, total_steps=1, phase="spawn", percent=0),
        payload=es.EventPayload(type="phase_complete", data=payload_data),
        parent_task=parent_task,
    )
    es.append_event(ev)


def get_session_meta_from_events(session_id: str) -> dict:
    """events.jsonl 의 첫 INITIATED 이벤트에서 SessionMeta 를 복원한다.

    /agent-view 에서 scope / goal_title / created_by 를 표시할 때 사용.
    """
    events = es.tail_events(session_id, n=50)
    for ev in events:
        if ev.get("status") == "INITIATED":
            data = ev.get("payload", {}).get("data", {})
            return {
                "scope": data.get("scope", ""),
                "goal_title": data.get("goal_title", ""),
                "estimated_effort_days": data.get("estimated_effort_days", 0.0),
                "created_by": data.get("created_by", {}),
            }
    return {}


if __name__ == "__main__":
    # Smoke test
    result = spawn_with_registration(
        parent_task="smoke-test-goal",
        kind="LOGIC_DATA",
        condition="smoke test condition",
        options=SpawnOptions(
            scope="backend",
            goal_title="Smoke Test 세션",
            estimated_effort_days=0.5,
            user="test@example.com",
            task_description="echo 'smoke test'",
        ),
    )
    print(f"success={result.success}, session_id={result.session_id}, reused={result.reused}, error={result.error!r}")
