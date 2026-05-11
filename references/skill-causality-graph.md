# 스킬 인과관계 그래프 (CRITICAL - 절대 보존)

## 1. /auto 5-Tier Discovery + PDCA Orchestrator

```
                    ┌─────────────────────────────────────────────┐
                    │              /auto (v20.1.0)                │
                    │      PDCA Orchestrator (직접 실행)           │
                    └─────────────────────────────────────────────┘
                                        │
              ┌─────────────────────────┼─────────────────────────┐
              ▼                         ▼                         ▼
     작업 인수 있음               작업 인수 없음                Options
     (Phase 1-5 실행)            (자율 발견 모드)              (전처리)
              │                         │                         │
              ▼                   ┌────┴────┐             ┌──────┴──────┐
     Phase 1-5 PDCA          Tier 2 URGENT              │ --gdocs     │
     (아래 상세)             Tier 3 WORK               │ --mockup    │
                             Tier 4 SUPPORT             │ --debate    │
                             Tier 5 AUTO                │ --research  │
                                  │                     │ --daily     │
                             ┌────┴────┐                │ --slack     │
                             │ /debug  │                │ --gmail     │
                             │ /issue  │                └─────────────┘
                             │ /commit │
                             │ /check  │
                             └─────────┘
```

## 2. Phase 1-5 PDCA 체인 (Agent Teams 패턴: TeamCreate → Task(team_name) → SendMessage → TeamDelete)

```
/auto "작업" (또는 /work "작업" → /auto 리다이렉트)
  │
  ├── Phase 0: 옵션 파싱 + 모드 결정
  │   └── --skip-analysis, --no-issue, --strict, --dry-run, --eco
  │
  ├── Phase 1 PLAN: 사전 분석 → 복잡도 판단 → 계획 → 이슈 연동
  │   ├── Step 1.0: TeamCreate → Task(name, team_name, explore, haiku) x2 병렬 [/work 흡수]
  │   ├── Step 1.1: 복잡도 판단 (0-1 LIGHT / 2-3 STANDARD / 4-5 HEAVY)
  │   ├── Step 1.2: 모드별 분기
  │   │   ├── LIGHT: Task(name="planner", team_name, planner, haiku)
  │   │   ├── STANDARD: Task(name="planner", team_name, planner, sonnet)
  │   │   └── HEAVY: Skill(ralplan)
  │   └── Step 1.3: 이슈 연동 [/work 흡수]
  │   └── 산출물: docs/01-plan/{feature}.plan.md
  │
  ├── Phase 2 DESIGN: 모드별 분기 (executor 계열 — architect는 READ-ONLY)
  │   ├── LIGHT: 스킵
  │   ├── STANDARD: Task(name="design-writer", team_name, executor, sonnet)
  │   └── HEAVY: Task(name="design-writer", team_name, executor-high, opus)
  │
  ├── Phase 3 DO: 모드별 분기
  │   ├── LIGHT: Task(name="executor", team_name, executor, sonnet)
  │   └── STANDARD/HEAVY: Skill(ralph) (Ultrawork 내장)
  │
  ├── Phase 4 CHECK: 4단계 검증
  │   ├── Step 4.1: Skill(ultraqa) + 커버리지 80%
  │   ├── Step 4.2: 이중 검증 (STANDARD/HEAVY만)
  │   ├── Step 4.3: E2E 검증 [/work 흡수] (Playwright 존재 시)
  │   └── Step 4.4: TDD 커버리지 보고 [/work 흡수]
  │
  └── Phase 5 ACT: 결과 기반 자동 분기
      ├── gap < 90% → Task(name="iterator", team_name, pdca-iterator) → Phase 4 재실행
      ├── gap >= 90% + APPROVE → Task(name="reporter", team_name, report-generator) → 완료 → TeamDelete()
      └── Architect REJECT → Task(name="fixer", team_name, executor) → Phase 4 재실행
```

## 3. BKIT 에이전트 역할 매핑

| BKIT 에이전트 | PDCA Phase | 역할 |
|--------------|:----------:|------|
| `gap-detector` | Phase 4 CHECK | 설계-구현 일치도 90% 검증 |
| `pdca-iterator` | Phase 5 ACT | gap < 90% 시 자동 개선 (최대 5회) |
| `code-analyzer` | Phase 4 CHECK | 코드 품질 분석 |
| `report-generator` | Phase 5 ACT | 완료 보고서 생성 |

**`/work`는 `/auto`로 통합 완료 (v19.0).** 별도 그래프 불필요.

**이 인과관계가 무너지면 `/auto`의 PDCA + Discovery 시스템 전체가 작동하지 않음**
