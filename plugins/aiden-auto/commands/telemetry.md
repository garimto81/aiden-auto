---
name: telemetry
description: View aiden-auto telemetry — token usage, skill calls, routing accuracy, optimization proposals
---

# /telemetry — aiden-auto Telemetry Dashboard

매 turn 캡처된 사용자 prompt·token·skill 호출·라우팅 메트릭을 조회·분석한다.

## 사용법

```bash
/telemetry                       # 어제 daily 집계 + 핵심 메트릭
/telemetry today                 # 오늘 (실시간)
/telemetry weekly                # 지난 7일 합계
/telemetry monthly               # 이번 달
/telemetry stats                 # 누적 통계 (모든 daily)
/telemetry export <file>         # JSON 또는 CSV로 export
/telemetry purge                 # 30일 초과 raw NDJSON 삭제
/telemetry proposals             # self_optimizer 제안 목록
/telemetry opt-out               # 캡처 영구 중지 (env AIDEN_AUTO_TELEMETRY=0)
```

## 데이터 흐름

```
사용자 prompt 도착
    │
    ▼
UserPromptSubmit hook
    └─▶ telemetry_capture.py
         ├─ secret_redactor.redact(prompt)
         ├─ NDJSON append: audit/telemetry.ndjson
         └─ session state 갱신
    │
    ▼
PreToolUse·PostToolUse·Stop hook (각각 캡처)
    │
    ▼
Daily cron (super-evolution.yml)
    └─▶ telemetry_analyzer.write_daily(yesterday)
         └─ audit/telemetry-daily-YYYYMMDD.json
    │
    ▼
self_optimizer.analyze_daily
    └─ optimization-proposals.ndjson
```

## 캡처 항목

| 항목 | 설명 |
|------|------|
| user prompt 텍스트 | redact 후 2K char 제한 |
| input/output/cache_read/cache_write tokens | CC hook metadata 제공 시 |
| context size | PreToolUse에서 추정 |
| 호출된 skill 목록 | PostToolUse(Skill) |
| skill latency (ms) | PreToolUse → PostToolUse delta |
| outcome | Stop hook 시 session 종합 |

## Privacy

- **모든 데이터 local 저장**, 외부 전송 0
- API key·token·password 패턴 자동 redact (`***`)
- `audit/.gitignore`에 telemetry*·auto-routing.ndjson 추가
- opt-out: `export AIDEN_AUTO_TELEMETRY=0` (env)

## TTL 정책

| 데이터 | 보존 |
|--------|------|
| raw NDJSON (`telemetry.ndjson`) | 30일 |
| daily aggregation (`telemetry-daily-*.json`) | 90일 |
| monthly aggregation (`telemetry-monthly-*.json`) | 365일 |
| optimization proposals | 영구 (수동 정리) |

## 출력 예시 (`/telemetry`)

```
[telemetry] 2026-05-09

▎ Volume
  prompts: 12 | tools: 87 | skill calls: 23

▎ Tokens (estimated)
  input: 45,200 | output: 12,800
  cache_read: 33,100 | cache_write: 8,400
  cache hit ratio: 73%

▎ Top Skills
  aiden-auto:check    9 calls
  aiden-auto:commit   5 calls
  aiden-auto:debug    4 calls

▎ Latency (p95)
  Bash: 1,234 ms | Skill: 8,500 ms | Read: 45 ms

▎ Routing Accuracy
  auto-decided: 10 | bypassed: 2 (slash) | ambiguous: 0
  avg confidence: 0.78

▎ Optimization Proposals (이번 달)
  pending: 2 (1 LOW, 1 MEDIUM, 0 HIGH)
```

## 실행 명령

내부 호출:

```bash
# daily 집계
python ${CLAUDE_PLUGIN_ROOT}/lib/super/telemetry_analyzer.py daily

# self-optimization 제안
python ${CLAUDE_PLUGIN_ROOT}/lib/super/self_optimizer.py propose

# 30일 purge
python ${CLAUDE_PLUGIN_ROOT}/lib/super/telemetry_analyzer.py purge
```

## 관련

- `rules/21-auto-routing.md` — 라우팅 룰
- `commands/audit.md` — `super-status` 서브커맨드 (telemetry 통합 dashboard)
- `commands/evolve.md` — 자가 진화 수동 트리거
- `.github/workflows/super-evolution.yml` — daily cron
