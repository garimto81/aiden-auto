# KPI Pluggability (S7) — 사용자 정의 KPI 등록

> **로딩 시점**: Phase 3 VERIFY 진입 직전 — `.claude/auto-config.yml` 존재 시.
> **의존**: `references/tool-integration.md` (S3 자동 도구 발견)와 보완 관계.
> **목적**: S3가 발견 못한 프로젝트별 KPI를 사용자가 명시적으로 등록.

---

## 핵심 원칙

> "S3 = 자동 발견. S7 = 명시 등록. 둘 다 사용 가능. 명시 등록이 우선."

`/auto`의 보편적 우월성 미달 원인 R7 (KPI 비호환) 의 마지막 격차 해결.

---

## 등록 위치

```
프로젝트 루트/
├── .claude/
│   └── auto-config.yml   ← S7 KPI 정의 위치
└── ...
```

S3 자동 발견은 `tools/`, `scripts/` 디렉토리 스캔만. S7는 어떤 위치의 어떤 명령이든 등록 가능.

---

## auto-config.yml schema

```yaml
# 프로젝트별 /auto 설정 (선택)
version: 1.0

# KPI 정의 (Phase 3 VERIFY에서 사용)
kpi_scripts:
  - name: <kpi_name>           # 식별자
    cmd: <shell command>       # 실행 명령
    role: drift_check | kpi | lint | test | build | other
    target: <expression>       # 통과 조건 (예: ">= 90%", "== 0")
    parser: <parser_spec>      # 결과 파싱 방법
    weight: <0.0-1.0>          # 종합 점수 가중치 (default 1.0)
    fail_mode: blocking | advisory  # blocking이면 FAIL시 Phase 3 REJECT

# Profile override (선택)
project_profile: ebs_governance | react_app | python_cli | monorepo | fastapi_backend | generic

# Paradigm default (선택)
default_paradigm: pdca | tdd | bdd | spike | ttd

# Phase override (선택)
phase_overrides:
  Phase_1: skip      # 모든 호출에서 Phase 1 강제 skip
  Phase_4: minimal   # Phase 4 항상 minimal mode
```

## Parser spec 형식

```yaml
# Pattern 1: regex
parser: "regex:PASS\\s+\\|\\s+\\d+\\s+\\|\\s+(\\d+)%"
# stdout에서 첫 번째 capture group 추출

# Pattern 2: jq path
parser: "jq:.summary.passed"
# stdout JSON에서 jq path 추출

# Pattern 3: exit code
parser: "exit_code"
# 0 = PASS, non-zero = FAIL

# Pattern 4: line count
parser: "line_count"
# stdout line 수 (예: lint error 수)

# Pattern 5: custom (Python lambda)
parser: "python:lambda out: out.count('FAIL') == 0"
```

## Target expression 형식

```yaml
target: ">= 90%"      # 숫자 비교 (>=, >, <=, <, ==, !=)
target: "== 0"        # 정확히 0
target: "in [PASS, OK]"  # enum
target: "exit 0"      # exit code 0
target: "not contains FAIL"  # 문자열 미포함
```

## 예시 1: ebs 프로젝트

```yaml
# <project-root>/.claude/auto-config.yml
version: 1.0

project_profile: ebs_governance

kpi_scripts:
  - name: reimplementability
    cmd: python tools/reimplementability_audit.py
    role: kpi
    target: ">= 90%"
    parser: "regex:PASS\\s+\\|\\s+\\d+\\s+\\|\\s+(\\d+)%"
    weight: 1.0
    fail_mode: blocking

  - name: spec_drift
    cmd: python tools/spec_drift_check.py --all --format=json
    role: drift_check
    target: "== 0"
    parser: "jq:[.api, .events, .fsm, .schema, .rfid, .settings, .websocket, .auth] | map(.unknown // 0) | add"
    weight: 1.0
    fail_mode: blocking

  - name: lint
    cmd: ruff check src/ tools/
    role: lint
    target: "exit 0"
    parser: "exit_code"
    weight: 0.5
    fail_mode: blocking

phase_overrides:
  Phase_1: full   # ebs는 PRD/Plan/Design 모두 full mode

default_paradigm: pdca
```

## 예시 2: React Next.js 프로젝트

```yaml
# .claude/auto-config.yml
version: 1.0
project_profile: react_app

kpi_scripts:
  - name: lighthouse
    cmd: npx lighthouse-ci autorun
    role: kpi
    target: ">= 90"
    parser: "regex:Performance:\\s+(\\d+)"
    weight: 1.0
    fail_mode: advisory   # 성능 떨어져도 머지 가능

  - name: bundle_size
    cmd: npm run build && du -k .next/ | tail -1 | cut -f1
    role: kpi
    target: "< 5000"   # 5MB 미만
    parser: "regex:^(\\d+)"
    weight: 0.5
    fail_mode: advisory

  - name: typescript
    cmd: npx tsc --noEmit
    role: lint
    target: "exit 0"
    parser: "exit_code"
    weight: 1.0
    fail_mode: blocking

  - name: e2e
    cmd: npx playwright test --reporter=json
    role: test
    target: ">= 0"   # 자동 fail count parsing
    parser: "jq:.stats.unexpected"
    weight: 1.0
    fail_mode: blocking
```

## Phase 3 VERIFY 통합 흐름

```
Phase 3 진입 시:

1. .claude/auto-config.yml 로드 시도
2. IF 파일 존재:
     - kpi_scripts 모두 실행
     - 각 결과 parser로 추출 → target과 비교
     - blocking fail 1개 이상 → Phase 3 REJECT (Phase 0.5 Case 3 진입)
     - advisory fail은 보고서에 기록만
   ELSE:
     - S3 자동 발견 도구 사용 (현재 v25.7 동작)
3. 종합 점수:
     - 모든 blocking PASS + advisory PASS → /auto gap = 100%
     - blocking PASS + advisory 일부 FAIL → /auto gap = 80-95% (architect APPROVE 가능)
     - blocking FAIL → /auto gap = <80% (REJECT)
```

## 우선순위

```
S7 auto-config.yml 등록됨:
  → 명시 등록만 사용 (S3 자동 발견 무시)
  → 단 S3가 발견한 도구 중 등록 안 된 것은 advisory로 추가

S7 미등록:
  → S3 자동 발견 사용 (v25.7 동작)
  → S3도 비어있으면 일반 qa-tester (v25.6 동작)
```

## 사용자 옵션

```bash
# auto-config.yml 일시 무시
/auto --no-config "..."

# 특정 KPI만 실행
/auto --kpi=reimplementability "..."

# advisory를 blocking으로 강제 변환
/auto --strict "..."
```

## 출력 표준

Phase 3 끝에서 KPI 결과 표:

```
═══ Phase 3: VERIFY 결과 (S7 KPI Pluggability) ═══
auto-config.yml 로드: ✓ (3 blocking + 1 advisory KPI)

KPI 결과:
  ✓ reimplementability:  92% (target ≥ 90%) — blocking PASS
  ✓ spec_drift:          0   (target == 0) — blocking PASS
  ✓ lint:                exit 0 — blocking PASS
  ⚠ bundle_size:         5400 KB (target < 5000 KB) — advisory FAIL

종합: 3/3 blocking PASS, 1 advisory FAIL → APPROVE (with warning)
═══════════════════════════════════════════════
```

## auto-config.yml 자동 생성 (편의)

`/auto --init-config` 옵션으로 template 생성:

```bash
/auto --init-config
```

```
~/.claude/auto-config.yml 생성됨:
  - Phase -1에서 발견한 tools_registry를 kpi_scripts 초안으로
  - 사용자가 target/parser/weight 채워서 사용
```

## 보안 고려

`auto-config.yml`은 임의 명령 실행 가능. 따라서:

| 안전 장치 | 정책 |
|----------|------|
| 파일 위치 제한 | 프로젝트 루트의 `.claude/` 만 인정 |
| 명령 검증 | tool_validator.py hook에서 위험 패턴 차단 (`rm -rf`, `eval`, ...) |
| 사용자 confirm | 첫 사용 시 1회 confirm (이후 동일 hash 자동 trust) |

## 본 등록 시스템의 핵심 가치

S3 자동 발견 + S7 명시 등록 결합으로 KPI 통합 완전. 직전 critic 보고서 R7 (KPI 비호환) 완전 해결. 프로젝트 자체가 신경 쓰는 모든 metric을 /auto가 인지.
