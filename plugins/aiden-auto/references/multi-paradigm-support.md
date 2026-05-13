# Multi-Paradigm Support (S6) — PDCA 외 작업 패러다임 지원

> **로딩 시점**: Phase 0 INIT의 옵션 파싱 단계 — `--paradigm` 옵션 감지 시.
> **default**: PDCA (옵션 없으면 현재 동작 유지).
> **목적**: PDCA 부적합 작업 유형 (보안 감사, 탐색, 행위 명세 등) 별도 흐름 제공.

---

## 핵심 원칙

> "PDCA = 일반 기능 구현·수정 sweet spot. 다른 작업은 다른 패러다임. 사용자 옵션으로 명시 선택."

`/auto`의 보편적 우월성 미달 원인 R6 (Adaptive 부재) 해결.

---

## 5개 Paradigm

### Paradigm 1: `pdca` (default, 기존 동작)

**적용 작업**: 일반 기능 구현, 버그 fix, 리팩토링, 문서 갱신.

**흐름**: Plan → Build → Verify → Close (현재 v25.6+).

**옵션**: 없음 (default).

---

### Paradigm 2: `tdd` (Test-Driven Development)

**적용 작업**: 단위 테스트 작성 가치 큰 작업, 회귀 위험 큰 코드, 라이브러리 함수 신설.

**흐름**:
```
[옵션 --paradigm=tdd]
  ↓
Phase 0: INIT (복잡도, profile)
  ↓
Phase 1: PLAN (mini) — 인터페이스 + 케이스 정의 (PRD 생략)
  ↓
Phase 2a: WRITE FAILING TEST (Red)
  - executor → tests/test_<feature>.py 작성
  - pytest 실행 → FAIL 확인
  - FAIL 안 나면 stop (테스트가 의미 없음)
  ↓
Phase 2b: MINIMAL IMPLEMENTATION (Green)
  - executor → 최소 구현으로 테스트 통과
  - pytest 실행 → PASS 확인
  ↓
Phase 2c: REFACTOR
  - architect → 코드 개선 (테스트는 PASS 유지)
  ↓
Phase 3: VERIFY (full test + lint + type check)
  ↓
Phase 4: CLOSE
```

**KPI**: 작성된 테스트 수, coverage %, mutation score (있으면).

**호출**: `/auto --paradigm=tdd "Add user.validate() function"`.

---

### Paradigm 3: `bdd` (Behavior-Driven Development)

**적용 작업**: 사용자 시나리오 기반 기능, e2e 중심 작업, 대시보드/UX.

**흐름**:
```
Phase 0: INIT
  ↓
Phase 1: SCENARIO WRITING
  - executor → features/<name>.feature (Gherkin: Given/When/Then)
  - 또는 e2e spec (Playwright: describe/it)
  ↓
Phase 2: STEP DEFINITIONS
  - executor → 시나리오 step 매핑 코드
  - 시나리오 실행 → FAIL 확인 (Step 빈 상태)
  ↓
Phase 3a: IMPLEMENT (시나리오 통과까지)
  - executor → 점진적 구현
  - 각 step PASS 확인
  ↓
Phase 3b: VERIFY (전체 시나리오 PASS + screenshot)
  ↓
Phase 4: CLOSE
```

**KPI**: 시나리오 통과 수, e2e 안정성.

**호출**: `/auto --paradigm=bdd "사용자가 로그인 후 대시보드 진입"`.

---

### Paradigm 4: `spike` (Exploratory)

**적용 작업**: 기술 가능성 탐색, 성능 한계 측정, 새 라이브러리 평가, 미지의 문제 분석.

**흐름**:
```
Phase 0: INIT (단, 복잡도 산정 생략 — 탐색이라 미지)
  ↓
Phase 1: HYPOTHESIS
  - executor → 가설 + 검증 방법 명문화
  - 예상 outcome (PASS/FAIL 양쪽)
  ↓
Phase 2: PROTOTYPE (TIME-BOXED)
  - executor → 최소 구현 (코드 quality 무시)
  - timeout 명시 (default 30분)
  ↓
Phase 3: MEASURE
  - 가설 검증 결과 측정
  - 기록: 결론 (가설 PASS/FAIL/UNKNOWN), 학습 사항
  ↓
Phase 4: DECIDE
  - 결과 보고: docs/spikes/<name>.md
  - 다음 단계 권고 (정식 구현 / 폐기 / 추가 spike)
  - 코드는 archive (main 머지 금지 default)
```

**KPI**: 가설 결론 명확성, 시간 준수, 학습 사항 정리.

**호출**: `/auto --paradigm=spike "FastAPI vs Flask 성능 비교"`.

**중요 차이**: PDCA와 달리 Spike는 **결과물 = 학습**. 코드 머지가 목적 아님.

---

### Paradigm 5: `ttd` (Threat-Driven Development, 보안 감사)

**적용 작업**: 보안 감사, 신규 인증/권한 코드, 외부 API 통합, 데이터 처리 보안 검증.

**흐름**:
```
Phase 0: INIT
  ↓
Phase 1: THREAT MODEL
  - architect → STRIDE 분석
    (Spoofing/Tampering/Repudiation/Information disclosure/Denial of service/Elevation of privilege)
  - 각 위협별 mitigation 명시
  ↓
Phase 2: SECURE IMPLEMENT
  - executor → mitigation 적용 코드
  - secret 처리, input validation, output encoding 강제
  ↓
Phase 3a: SECURITY VERIFY
  - qa-tester → 자동 보안 스캔 (semgrep, bandit, npm audit 등)
  - architect → 위협 모델별 mitigation 검증
  ↓
Phase 3b: PENTEST CHECKLIST
  - OWASP Top 10 체크
  - HIPAA/PCI DSS 등 컴플라이언스 (해당 시)
  ↓
Phase 4: CLOSE (보안 보고서 + 잔여 위험 명시)
```

**KPI**: 위협 mitigation 비율, 보안 스캔 PASS, 컴플라이언스 체크 PASS.

**호출**: `/auto --paradigm=ttd "신규 결제 API 보안 검증"`.

---

## Paradigm 선택 가이드

| 작업 유형 | 권장 paradigm |
|----------|--------------|
| 일반 기능 구현 | `pdca` (default) |
| 라이브러리 함수, 회귀 위험 | `tdd` |
| 사용자 시나리오, e2e 중심 | `bdd` |
| 기술 평가, 탐색 | `spike` |
| 보안/인증/외부 API | `ttd` |
| 컴플라이언스 (의료/금융) | `ttd` (확장) |
| 문서/리팩토링 | `pdca` (Phase 2 위주) |

## 자동 추천 (선택)

Phase -1.5 self-evaluation 시 paradigm 추천 가능:

```
domain_profile = 의료 → "보안 paradigm 권장: --paradigm=ttd"
README "TDD" 키워드 매칭 → "--paradigm=tdd 권장"
docs/spikes/ 디렉토리 존재 → "--paradigm=spike 자주 사용됨"
```

단 자동 적용 X. 사용자가 명시 옵션 사용해야.

## SKILL.md 통합

Phase 0 INIT의 옵션 파싱:

```
options = parse_options(user_input)

paradigm = options.get("paradigm", "pdca")  # default

IF paradigm == "pdca":
    → 현재 동작 (Phase 1-4 표준)
ELIF paradigm == "tdd":
    → Phase 2를 2a + 2b + 2c 분할 (Red-Green-Refactor)
ELIF paradigm == "bdd":
    → Phase 1을 시나리오 작성으로 변경
ELIF paradigm == "spike":
    → 결과물 = 학습 보고서 (코드 머지 금지)
ELIF paradigm == "ttd":
    → Phase 1을 위협 모델, Phase 3에 보안 검증 추가
ELSE:
    → 사용자 안내 + default pdca
```

## Multi-paradigm 조합 (advanced)

복합 작업 시 paradigm 조합 가능:

```bash
/auto --paradigm=tdd --paradigm=ttd "auth 모듈 구현"
# → TDD (테스트 먼저) + TTD (위협 모델 동시) 결합
# Phase 1: 위협 모델 + 테스트 케이스
# Phase 2: Red-Green + 보안 mitigation
# Phase 3: 표준 + 보안 스캔
```

## 출력 표준

Phase 0 끝에서 paradigm 명시:

```
═══ Phase 0 끝 — Paradigm 결정 ═══
복잡도: 5/10
fit_score: 88/100
project_profile: react_app
**paradigm: tdd** ← 사용자 명시
adaptive phase plan:
  Phase 1: mini (TDD 인터페이스 정의)
  Phase 2a: Red (failing test)
  Phase 2b: Green (minimal impl)
  Phase 2c: Refactor
  Phase 3: full
  Phase 4: mini
═══════════════════════════════════
```

## 본 다양성의 핵심 가치

`/auto`가 PDCA만 알던 한계 해결. 작업 유형마다 적합한 패러다임 적용으로 우월성 보편화. 직전 critic 보고서 R6 (Adaptive 부재) 완전 해결.
