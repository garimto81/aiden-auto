# Adaptive Framework Integration Protocol (v28.2 Section 13)

> **Core Objective**: /goal과 외부 6+ harness framework가 진화해도 aiden-auto 코어가 무너지지 않도록 schema-agnostic + real-time + backward-compat + feature flag auto-enable.

## 5 패턴

### 1. Schema Versioning

모든 state 파일에 `schema_version` 의무화:

| State 파일 | 현재 schema |
|-----------|-------------|
| `state/active-goal-{sid}.json` | v1.0 |
| `state/active-sessions.json` | v1.0 |
| `state/quota-decisions-{date}.json` | v1.0 |
| `state/circuit-breaker.json` | v1.0 |
| `state/cc-auth-decisions-{date}.json` | v1.0 |
| `state/sessions/{id}/summary.json` | v1.0 |
| `state/sessions/{id}/checkpoint.json` | v1.0 |
| `state/sessions/{id}/events.jsonl` | v1.0 |
| `state/sessions/registry-hooks.json` | v1.0 |
| `config/feature-flags.yml` | v1.0 |

### 2. Adapter Layer

`lib/adapters/`:

| Adapter | 격리 대상 | SUPPORTED_VERSIONS |
|---------|----------|-------------------|
| `goal_adapter.py` | CC /goal + Stop hook | `2.0+` |
| `advisor_tool_adapter.py` | advisor-tool API beta | `advisor-tool-2026-03-01` |
| `agent_view_adapter.py` | claude --bg / claude agents | `2.1.139+` |
| `orchestrator_adapter.py` | 글로벌 orchestrator | `v10.3+` |

**원칙**:
- Feature detection > 가정 (`if "new_field" in response: use_new()`)
- try/except 필수 → graceful degradation
- 버전 매트릭스 명시 (`SUPPORTED_VERSIONS = [...]`)
- Fallback chain (새 기능 → 이전 → 안전 기본값)

### 3. Real-time Ingestion (4 trigger)

`harness-watcher`:

| Trigger | 발동 시점 |
|---------|----------|
| `on_daily_cron` (기존) | 매일 00:00 UTC |
| `on_demand_request` (NEW) | `/auto harness refresh` 또는 평문 "harness 갱신" |
| `on_adapter_failure_signal` (NEW) | adapter가 `400 unknown beta` 등 framework drift 감지 시 |
| `on_post_framework_command` (NEW, light mode) | `claude jobs`, `/goal` 직후 cache TTL 5min |

real-time burn 방지:
- light mode TTL 5min
- full mode TTL 60min
- on-demand는 강제 full

### 4. Backward Compatibility

```
v1.0 (current) → v1.1 → v1.2 → v1.3 (current)
                              ↑
                              N-1 (v1.2) 호환: 자동 마이그레이션
                              N-2 (v1.1) deprecated: 경고만 작동
                              N-3 (v1.0) blocked: 강제 마이그레이션
```

Migration 스크립트: `lib/adapters/migrations/{from}_to_{to}.py`
harness-applier가 schema bump PR 시 migration도 함께 작성.

`harness-critic` 6번째 질문 (NEW, 5% weight):

```
6. Backward compatibility (5%):
   0 = breaks N-1 adapter contract
   5 = N-1 호환 OK, N-2 일부 깨짐
   10 = N-1, N-2 모두 호환
```

### 5. Feature Flag Auto-Enable

`config/feature-flags.yml`:

```yaml
flags:
  goal_v2_multi_condition:
    enabled: false
    auto_enable_when: "framework_version >= 2.5.0 AND stability == 'stable'"
    rollback_signal: "error_rate > 5% in 24h"
```

`harness-applier`가 안정성 detect 시 → flag을 `enabled: true`로 PR 생성. rollback signal trip 시 즉시 OFF PR.

## 흐름

```
  외부 framework 새 release
       |
       v
  harness-watcher (daily 또는 first-fail)
       |
       v
  변경 점 감지 → harness-critic
       |
       v
  6 질문 정가중 평가
       |
   +---+---+
   APPROVE  REJECT/NEEDS_INFO
   |        |
   v        v
  applier  보고만 종료
   |
   v
  Adapter 수정 (코어 무변경)
  + migration 스크립트 작성
  + feature flag 평가
   |
   v
  PR 자동 생성 (사용자 검토 1회)
   |
   v
  merge 후 다음 daily cycle부터 활용
```

## 위험 완화

| 위험 | 완화 |
|------|------|
| Adapter 누적 부담 | 200줄 hard-rule + facade only, 비즈니스 로직 금지 |
| First-fail trigger 폭주 | 1/session/framework 제한 + cache TTL |
| Feature flag 오판 | rollback_signal 의무 + 24h 모니터링 |

## 관련

- `lib/adapters/__init__.py` — registry + health_check
- `lib/adapters/*.py` — 격리 adapters
- `agents/meta/harness-watcher.md` — 4 trigger
- `agents/meta/harness-critic.md` — 6 질문
- `agents/meta/harness-applier.md` — feature flag auto-enable
- `config/feature-flags.yml` — flag 등록부
- Plan Section 13 — 전체 사양
