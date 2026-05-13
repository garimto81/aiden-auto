# Multi-Session Bridge (v28.2)

> **목적**: /auto가 Phase 0 plan에서 splittable 패턴 감지 시 글로벌 `~/.claude/skills/orchestrator/` v10.3+로 위임. agent-view (`claude --bg`, `claude agents`) 사용 가이드. **orchestrator 재구현 금지**.

## Required Version

```yaml
requires:
  orchestrator: ">= v10.3"
  claude_code: ">= v2.1.139"  # agent-view 최소 버전
```

미달 시 `multi-session-router`가 fallback (orchestrator 직접 호출 안 함, 사용자에게 안내).

## Session Type Classification

| 클래스 | 대상 | 검증 방식 |
|--------|------|----------|
| **LOGIC_DATA** | 백엔드 / 라이브러리 / API / CLI / 문서 (.md/.pdf/.txt) / 데이터 분석 | unit tests + log + status code + checksum (스크린샷 금지) |
| **VISUAL_INTERACTION** | Web UI / Mobile App / 시각화 컴포넌트 / 사용자 인터페이스 | Playwright 스크린샷 ≥3장 |

판정 책임: `multi-session-router` 1회 (재판정 금지).
사용자 우회: `!visual` / `!logic`.

## Session Metadata Schema

```yaml
session:
  schema_version: "1.0"
  id: "aiden-auto:S-{timestamp}-{kind}-{shorthash}"
  parent_task: "{active-goal.json id}"
  kind: "LOGIC_DATA" | "VISUAL_INTERACTION"
  status: "ACTIVE" | "SUSPENDED" | "COMPLETED" | "FAILED"
  worktree: ".claude/worktrees/{session.id}/"
  created_at: ISO8601
  artifacts_dir: "state/sessions/{session.id}/"
```

전역 인덱스: `state/active-sessions.json`. 매 status 전이 시 갱신.

## Cross-Session Communication

### Artifact Summary 자동 전달

| 시점 | 동작 |
|------|------|
| LOGIC_DATA 세션 종료 시 | `state/sessions/{id}/summary.json` 자동 생성. `outputs[]` + `key_decisions[]` + `consumed_quota` 포함 |
| VISUAL_INTERACTION 세션 시작 시 | parent_task 일치하는 다른 active session의 summary.json 자동 로드 |
| 참조 문법 | `Session-{id}/output.csv` 형태로 다른 세션 산출물 명시 |

### Conflict Resolution

동일 active-goal에서 2 세션이 충돌 산출물(같은 파일 다른 내용) 발생 시:
- `state/sessions/conflicts-{date}.json` 기록
- statusline `sessions:NA!` (느낌표 = conflict)
- Phase 4 close 전 사용자 1회 결정 요청 (예외: 데이터 충돌은 파괴적이라 사용자 결정 정당)

## Auto-Launch (3초 timeout)

```
3개 독립 stream 감지. 자동 분할 실행합니다.
  Stream 1 [VISUAL_INTERACTION] frontend (React 컴포넌트)
  Stream 2 [LOGIC_DATA]         backend  (FastAPI endpoints)
  Stream 3 [LOGIC_DATA]         infra    (Terraform IaC)
취소하려면 N 입력. (3초 후 자동 진행)
```

timeout 환경변수: `AIDEN_AUTO_MS_TIMEOUT` (1-30초, 기본 3초).

## Multi-CC 안전 (Section 4.6 정합)

조사 결과: **SUPPORTED_WITH_CARE** — 여러 CC 인스턴스가 동시 agent-view 사용 가능.

| 사실 | 결과 |
|------|------|
| supervisor daemon | per-user 단일 (모든 CC 공유) |
| state 저장 | `~/.claude/jobs/`, `~/.claude/daemon/` 글로벌 |
| 자동 dedup | **없음** — 우리가 체크 필요 |
| 쿼타 | 글로벌 공유 (N×M 소모) |
| worktree | git 레벨 격리 (안전) |
| 격리 옵션 | `CLAUDE_CONFIG_DIR` env 사용 시 별도 supervisor |

### 5가지 안전 조치 (hard-rule)

1. **Session name prefix**: 모든 spawn된 세션은 `aiden-auto:S-{timestamp}-{kind}-{shorthash}` — agent-view 시각 구분
2. **Spawn 전 중복 체크**: `session_registry.py`가 active-sessions.json + supervisor roster 비교, 동일 condition+parent_task 재사용
3. **Worktree 정리**: `git worktree list`로 stale 확인, orphan 자동 정리 (사용자 1회 확인)
4. **쿼타 합산**: quota-advisor가 quota-cache + `claude jobs list` 합산
5. **격리 모드**: 완전 분리 원할 시 `CLAUDE_CONFIG_DIR=~/.claude-aiden-auto claude` 사용

## Best Practices (hard-rule)

1. **Minimize Redundancy** — multi-session-router가 sub-task 중복 시 1 stream으로 합침
2. **Clear Checkpointing** — 각 세션 30분/phase 전이 시 `state/sessions/{id}/checkpoint.json` 자동
3. **Conflict Resolution** — conflicts-{date}.json + statusline `!` 토큰 + 사용자 결정

## Agent View 명령 참조

| 명령 | 용도 |
|------|------|
| `claude --bg "<task>"` | 백그라운드 세션 spawn |
| `claude agents` | 활성 세션 테이블 (peek/attach/stop) |
| `claude respawn --all` | 중단된 세션 재개 |
| `claude jobs list` | 세션 목록 (스크립트 가독) |

## 관련

- `agents/meta/multi-session-router.md` — 판정 agent
- `lib/sessions/session_registry.py` — registry + 중복 체크
- `lib/sessions/event_schema.py` — events.jsonl schema (Section 14)
- `~/.claude/skills/orchestrator/SKILL.md` v10.3 — 글로벌 orchestrator (재구현 금지)
- Plan Section 4 + 4.6 — 전체 사양
