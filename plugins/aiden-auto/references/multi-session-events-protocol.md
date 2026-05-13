# Multi-Session Events Protocol (v28.2 Section 14)

> **목적**: Multi-session "hanging state" 해소를 위한 file-based event stream + HMAC + idempotency + DLQ 사양.

## 아키텍처

```
state/sessions/{session_id}/
  ├── events.jsonl           ← append-only event stream
  ├── dlq.jsonl              ← 실패 재시도 큐
  ├── checkpoint.json        ← 30분/phase 자동 저장
  ├── summary.json           ← 세션 종료 시 자동 생성
  └── conflicts-{date}.json  ← (해당 시) 충돌 기록

state/sessions/registry-hooks.json  ← 콜백 등록부
state/.hmac-secret                  ← HMAC SHA256 key (mode 0600, .gitignore)
state/.hmac-secret-prev             ← 30일 rotation grace
```

## Event Payload Schema

```json
{
  "schema_version": "1.0",
  "event_id": "E-{session_id_safe}-{ts_ns}-{shorthash}",
  "timestamp": "2026-05-13T11:30:00.000Z",
  "session_id": "aiden-auto:S-20260513T1100-VISUAL-a1b2",
  "parent_task": "active-goal-xyz",
  "status": "INITIATED | IN_PROGRESS | COMPLETED | ERROR",
  "progress_meta": {
    "current_step": 3,
    "total_steps": 5,
    "phase": "phase-2-build",
    "percent": 60
  },
  "payload": {
    "type": "phase_complete | artifact_emitted | error | log | checkpoint",
    "data": { ... }
  },
  "hmac": "sha256:abc123..."
}
```

## 4 Status (사용자 비전 정합)

| Status | 의미 | 발화 시점 |
|--------|------|----------|
| `INITIATED` | 세션 시작 | claude --bg spawn 직후 |
| `IN_PROGRESS` | phase 진행 중 | 매 phase 전이 / 30분마다 / 주요 milestone |
| `COMPLETED` | 정상 완료 | Phase 4 close 성공 + Validation Statement |
| `ERROR` | 실패 / 중단 | unrecoverable error, circuit breaker trip |

## Hook Registration

`state/sessions/registry-hooks.json`:

```json
{
  "schema_version": "1.0",
  "hooks": [
    {
      "hook_id": "H-statusline-default",
      "session_id_pattern": "*",
      "event_filters": ["INITIATED", "IN_PROGRESS", "COMPLETED", "ERROR"],
      "callback_type": "file_watch",
      "callback_target": "${CLAUDE_PLUGIN_ROOT}/hooks/statusline_compose.py",
      "hmac_secret_ref": "env:AIDEN_AUTO_HMAC_SECRET"
    },
    {
      "hook_id": "H-conflict-resolver",
      "session_id_pattern": "*",
      "event_filters": ["ERROR"],
      "callback_type": "exec",
      "callback_target": "python ${CLAUDE_PLUGIN_ROOT}/hooks/conflict_notifier.py"
    }
  ]
}
```

3 callback_type:

| Type | 사용 시점 | 특성 |
|------|----------|------|
| `file_watch` | statusline 등 가벼운 listener | tail -f, 가장 가벼움, 검증 옵셔널 |
| `process_signal` | 즉시성 외부 프로세스 | SIGUSR1 + HMAC 검증 의무 |
| `exec` | 격리 callback | 새 프로세스 + stdin payload + HMAC 검증 의무 |

## Sequence Diagram (사용자 비전 §4 정합)

```
  User       /auto      multi-session-     session         events.jsonl     statusline
  / UI       Lead       router             agent           (per-session)
   |          |             |                 |                 |                |
   |--평문--->|             |                 |                 |                |
   |          |--spawn----->|                 |                 |                |
   |          |             |--claude --bg -->|                 |                |
   |          |             |                 |--append INITIATED->|              |
   |          |             |                 |                 |                |
   |          |             |  ... phase 1 작업 ...                 |              |
   |          |             |                 |--append IN_PROGRESS->|             |
   |          |             |                 |   (60% 진행)        |              |
   |          |             |                 |                 |                |
   |          |             |   file watcher (callback_type=file_watch)            |
   |          |             |                                  |--read tail-->     |
   |          |             |                                                "sessions:1A 60%"
   |          |             |                 |                 |                |
   |          |             |  ... 계속 작업 ...                  |                |
   |          |             |                 |--append COMPLETED->|               |
   |          |             |                                                "sessions:0 goal:reached"
   |          |<------------|<--read events---|                 |                |
   |          |   완료 인지                                                        |
   |<--보고---|             |                 |                 |                |
```

## Error Handling — Exponential Backoff

```
event 발화 callback 실패:
  1차 재시도 1초 후
  2차 2초 후
  3차 4초 후
  4차 8초 후 (총 15초)
  5차 실패 → dlq.jsonl 추가
       |
       v
  event_consumer_dlq.py (1h 주기) 재시도
  → MAX_RETRIES (5) 초과 시 expired 마킹
```

events.jsonl append 자체는 절대 실패 안 됨 (fsync). 재시도는 callback 측에만.

## HMAC 서명 (Section 14.6)

- Algorithm: HMAC-SHA256
- 서명 대상: `{event_id}|{session_id}|{status}|{timestamp}` (payload.data 제외 — 비용 회피)
- Secret 저장:
  - 환경변수 `AIDEN_AUTO_HMAC_SECRET` (기본)
  - 없으면 `state/.hmac-secret` 자동 생성 (file mode 0600)
  - `.gitignore` 등록 의무
- Rotation: 30일마다 새 secret 생성, 기존은 `.hmac-secret-prev`로 이동 (검증 측 grace)

## Constraint Checklist 구현

| 비전 제약 | 구현 |
|-----------|------|
| **Non-Blocking** | events.jsonl append ~ms (fsync). callback async/exec 비차단 |
| **Idempotency** | event_id 유일성 (session_id + ns timestamp + shorthash) + consumer cache TTL 1h |
| **Security** | HMAC-SHA256 + secret rotation + 검증 의무 (exec/signal) |

## Pseudocode 예 (Python)

```python
# agents/iteration/iteration-runner.md 호출 패턴
from lib.sessions.event_schema import EventBuilder, ProgressMeta, EventPayload
from hooks.event_dispatcher import dispatch_event

def on_phase_transition(session_id, parent_task, from_phase, to_phase, current_step, total_steps):
    ev = EventBuilder.create(
        session_id=session_id,
        parent_task=parent_task,
        status="IN_PROGRESS",
        progress_meta=ProgressMeta(
            current_step=current_step,
            total_steps=total_steps,
            phase=to_phase,
            percent=int(current_step / total_steps * 100),
        ),
        payload=EventPayload(type="phase_complete", data={"from": from_phase, "to": to_phase}),
    )
    dispatch_event(ev, blocking=False)

def on_session_complete(session_id, parent_task, final_artifacts):
    ev = EventBuilder.create(
        session_id=session_id,
        parent_task=parent_task,
        status="COMPLETED",
        progress_meta=ProgressMeta(current_step=5, total_steps=5, percent=100, phase="phase-4-close"),
        payload=EventPayload(type="artifact_emitted", data={"artifacts": final_artifacts}),
    )
    dispatch_event(ev, blocking=False)
```

## events.jsonl Rotation (Section 10 Risk #13)

- 10000 lines OR 50MB 초과 시 → `events.{N}.jsonl.gz` 압축 아카이브
- 90일 후 아카이브 자동 삭제
- 현재 events.jsonl은 항상 fresh

## 관련

- `lib/sessions/event_schema.py` — Schema + HMAC + path helpers
- `hooks/event_dispatcher.py` — append + callback + DLQ 발생
- `hooks/event_consumer_dlq.py` — 1h 주기 DLQ 재시도
- `hooks/statusline_compose.py` — events.jsonl tail (file_watch consumer)
- `lib/sessions/session_registry.py` — registry-hooks.json 등록 API
- Plan Section 14 — 전체 사양
