---
name: evolve
description: Super skill self-evolution — manual trigger for harvest/compile/sync of aiden-auto super skills against external plugin sources
---

# /evolve — Super Skill 자가 진화 수동 트리거

aiden-auto 12개 super skill의 외부 source(외부 플러그인 SKILL.md) 변경을 감지하여 build-time에 흡수한다. 자동 cron 외에 사용자가 명시 호출할 때 사용.

## 사용법

```bash
/evolve                          # daily cadence dry-run (변경 시뮬레이션만)
/evolve --apply                  # daily cadence + LOW tier 자동 적용
/evolve weekly                   # weekly cadence (MEDIUM draft 생성)
/evolve monthly                  # monthly cadence (winner 재평가 알림 포함)
/evolve <category>               # 단일 카테고리 (tdd, commit, ...)
/evolve --bootstrap              # 미컴파일 카테고리 전체 초기 컴파일
/evolve --rollback <category>    # 마지막 체크포인트로 복원
/evolve --rollback <cat> <date>  # 특정 시각 체크포인트로 복원
/evolve --report                 # daily evolution 보고서 출력

# GitHub Actions cron 100% 수동 재현 (v1.1+)
/evolve --full                   # daily cron 동등 (apply + full-smoke + auto-commit)
/evolve --full-smoke             # Step 4 풀 smoke만 단독 실행 (read-only)
/evolve --apply --auto-commit    # apply + 자동 commit (PR 없음)
/evolve weekly --full            # weekly cron 동등 (MEDIUM draft + auto PR)
/evolve monthly --full           # monthly cron 동등 (winner 재평가 + auto PR)
```

## 흐름

```
사용자 /evolve 호출
    ↓
plugin_marketplace_probe.list_installed_plugins()
    ↓ 26개 외부 플러그인 캐시 디렉터리 인식
sync_engine.detect_drift_all()
    ↓ sources/<cat>.yaml의 version_hash와 현재 hash 비교
tier_classifier.classify(before, after)
    ↓ 각 변경마다 LOW / MEDIUM / HIGH
guard_check
    ├─ circuit_breaker_super.can_evolve(cat)  # 하루 5회 제한
    ├─ checkpoint_manager.create(cat)         # 백업 생성
    └─ smoke_tester.test(cat)                 # 무결성 검사
evolve
    ├─ LOW    → compiler 즉시 적용 → smoke 통과 시 유지, 실패 시 rollback
    ├─ MEDIUM → skills/<cat>/SKILL.md.draft 생성 (사람 승인 대기)
    └─ HIGH   → 알림만 (PR 생성은 GitHub Actions에서)
audit/super-evolution.ndjson append
```

## 옵션 상세

| 옵션 | 동작 |
|------|------|
| (인자 없음) | dry-run, daily cadence, 모든 카테고리 |
| `--apply` | LOW tier 자동 적용 (env `SUPER_EVOLVE_APPLY=1`로도 가능) |
| `weekly` | MEDIUM tier draft까지 생성 |
| `monthly` | winner 재평가 알림 + weekly 동작 포함 |
| `<category>` | 단일 카테고리만 (`tdd`, `commit`, `simplify`, `debug`, `plan`, `check`, `parallel`, `verify`, `skill-create`, `research`, `auto`, `pr`) |
| `--bootstrap` | 미컴파일(version_hash 비어있음) 카테고리 전체 초기 컴파일 |
| `--rollback <cat>` | 마지막 체크포인트로 복원 |
| `--rollback <cat> <YYYYMMDD>` | 특정 시각 체크포인트로 복원 |
| `--report` | daily evolution 보고서 마크다운 출력 |
| `--dry-run` | 강제 dry-run (default) |
| `--full` | `--apply --full-smoke --auto-commit` 통합 (cron 100% 동등) |
| `--full-smoke` | 12개 카테고리 + auto-routing classifier 정확도 smoke (단독 실행 가능, read-only) |
| `--auto-commit` | cadence=daily면 LOW commit, weekly/monthly면 PR 생성 (gh CLI 필요) |

## 안전장치

| 장치 | 동작 |
|------|------|
| **Circuit Breaker** | 하루 동일 카테고리 5회 초과 시 halt + 알림 |
| **Checkpoint** | 적용 직전 `checkpoints/<cat>-<timestamp>.md` 백업 (30일 보존) |
| **Smoke Test** | 적용 후 super skill의 frontmatter·body·attribution 무결성 검사. 실패 시 즉시 rollback |
| **Dry-run default** | `--apply` 또는 env `SUPER_EVOLVE_APPLY=1` 명시 없으면 변경 시뮬레이션만 |
| **Browser OAuth only** | API key 사용 금지 (CLAUDE.md Safety Rule 준수) |

## 실행 명령

내부적으로 `evolution_scheduler.py`를 호출:

```bash
python ${CLAUDE_PLUGIN_ROOT}/lib/super/evolution_scheduler.py \
    --cadence=daily \
    [--apply | --dry-run] \
    [--category=<cat>] \
    [--bootstrap] \
    [--full-smoke] \
    [--auto-commit] \
    [--full]
```

`--full`은 `--apply --full-smoke --auto-commit`의 alias.

## 출력 예시

### dry-run

```
[evolution] cadence=daily apply=False outcomes=3
  - tdd [LOW] applied=False drift=1: dry-run
  - commit [MEDIUM] applied=False drift=2: MEDIUM tier — manual review required
  - debug [LOW] applied=False drift=1: dry-run
```

### --apply

```
[evolution] cadence=daily apply=True outcomes=3
  - tdd [LOW] applied=True drift=1: LOW auto-applied
  - commit [MEDIUM] applied=False drift=2: MEDIUM tier — manual review required
  - debug [LOW] applied=True drift=1: LOW auto-applied

audit/super-evolution.ndjson:
  {"ts":"...","event":"evolve_outcome","cadence":"daily","category":"tdd","tier":"LOW","applied":true,...}
```

### --bootstrap (초기)

```
[evolution] cadence=daily apply=False outcomes=12
  - auto [BOOTSTRAP] applied=False drift=0: dry-run
  - check [BOOTSTRAP] applied=False drift=0: dry-run
  ...
```

## 보고 채널

| 채널 | 용도 |
|------|------|
| stdout | 즉시 outcome 요약 |
| stdout `[smoke]` 라인 | `--full-smoke` 시 12 카테고리 PASS/FAIL + classifier OK/MISS |
| stdout `[commit]` 라인 | `--auto-commit` daily 모드 시 sha + message |
| stdout `[pr]` 라인 | `--auto-commit` weekly/monthly 모드 시 branch + url |
| `aiden-auto/audit/super-evolution.ndjson` | 영속 NDJSON 로그 (`event=smoke_full`, `event=auto_commit`, `event=auto_pr` 포함) |
| `/audit super-evolution` | 누적 보고서 통합 출력 |
| GitHub PR (CI 또는 `--full` weekly/monthly) | MEDIUM/HIGH tier 시 자동 PR |

## 관련

- `/audit super-sync` — 통합 sync 명령 (audit 안에서)
- `/audit super-rollback` — rollback 단축 호출
- `rules/18-super-routing.md` — super skill 라우팅 정책
- `rules/19-super-sync-policy.md` — tier 분류·자동 적용 정책
- `rules/20-evolution-cadence.md` — daily/weekly/monthly cadence 룰
- `.github/workflows/super-evolution.yml` — CI cron
