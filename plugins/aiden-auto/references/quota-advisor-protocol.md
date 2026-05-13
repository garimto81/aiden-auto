# Quota Advisor Protocol (v28.2)

> **목적**: 쿼타 운영의 Executor → Advisor 2-tier 결정 프로토콜. Anthropic advisor-tool API beta 활용.

## 4-Verdict 사양

| Verdict | 의미 | 동작 | 사용자 가시성 |
|---------|------|------|--------------|
| `PROCEED` | 쿼타 여유, 변화 없음 | 작업 그대로 진행 | 없음 (조용히 통과) |
| `DOWNGRADE_ECO` | eco 강등 권장 | `config/eco-modes.yml` 다음 단계 자동 적용 | statusline `mode:eco` 토큰 변화 |
| `DEFER` | 작업 연기 권유 (선택) | 1줄 안내 ("쿼타 88% — reset 03:00Z. 진행?"). 비차단 | 1줄 메시지 |
| `BLOCK` | 진행 차단 | exit 2 + 사유 stdout. `!override` 명시만 우회 | 명확한 BLOCK 메시지 |

## Verdict 결정 흐름

```
+------------------+
| quota-executor   |  3-질문 (≤100ms)
| (haiku)          |
+--------+---------+
         |
         v
   verdict?
         |
    +----+----+----+
    |    |    |    |
    v    v    v    v
PROCEED DOWN ESCALATE  (그 외 미정)
   |     |        |
   |     |        v
   |     |   +--------+
   |     |   | quota- |  5-질문 정가중
   |     |   | advisor|  (opus 4.7 advisor-tool sub-inference)
   |     |   |(sonnet)|
   |     |   +---+----+
   |     |       |
   |     |   weighted_score
   |     |       |
   |     |    +--+---+----+----+
   |     |    |  |   |    |    |
   |     |    v  v   v    v    v
   |     |  <25 25-49 50-74 ≥75
   |     |   |   |    |    |
   |     |   PROCEED DOWN DEFER BLOCK
   |     |   |   |    |    |
   v     v   v   v    v    v
quota_pretool_gate.py가 적용
   - PROCEED → 무동작
   - DOWNGRADE_ECO → active_eco_mode 다음 단계
   - DEFER → 사용자 1줄 알림
   - BLOCK → exit 2
```

## Eco-Mode 자동 다운그레이드 매트릭스

`config/eco-modes.yml`의 `auto_downgrade_thresholds:`:

| 신호 | 적용 모드 |
|------|----------|
| `five_h_pct >= 70` AND active=default | `eco` |
| `weekly_pct >= 85` | `eco-2` |
| `weekly_pct >= 95` | `eco-3` |

Circuit Breaker quota_downgrade 카운터: 한 세션에서 5회 초과 시 자동 시도 차단 + 사용자 에스컬.

## Advisor-Tool API 호출 사양

| 항목 | 값 |
|------|------|
| Endpoint | Anthropic Messages API (post existing call) |
| Header | `anthropic-beta: advisor-tool-2026-03-01` |
| Executor model | sonnet (quota-advisor agent) |
| Advisor model | `claude-opus-4-7` (mandatory) |
| Sub-inference type | `advisor_20260301` |
| Cache | system prompt에 5min TTL (`caching: {type: ephemeral, ttl: "5m"}`) |
| Fallback | header 회전 감지 시 executor-only verdict + harness-watcher 알람 |

## Schema (state files)

### `state/quota-advisor-pending.flag` (executor 작성, advisor 픽업)

```json
{
  "schema_version": "1.0",
  "session_id": "...",
  "signals": { ... 3 questions ... },
  "snapshot": { ... usage cache ... },
  "ts": "2026-05-13T12:00:00Z"
}
```

### `state/quota-decisions-{date}.json` (append-only)

```json
[
  { "tier": "executor", "verdict": "PROCEED", ... },
  { "tier": "advisor", "verdict": "DOWNGRADE_ECO", "weighted_score": 38, ... }
]
```

## 사용자 우회

- `!override` 명시 시 모든 verdict 무시 (위험 인지 사용자)
- `!eco-only` 명시 시 advisor 호출 안 함, executor의 DOWNGRADE_ECO만 허용

## 관련

- `agents/meta/quota-executor.md`
- `agents/meta/quota-advisor.md`
- `hooks/quota_pretool_gate.py`
- `config/eco-modes.yml`
- Plan Section 3
