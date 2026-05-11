# Phase -1: Context Detection — 자동 컨텍스트 감지

> **로딩 시점**: `/auto` 명시 호출 직후, Phase 0 INIT 진입 전. 항상 실행 (사용자 결정 점 0).
> **소요**: 5-10초 (read-only 스캔만).
> **출력**: `ContextProfile` (4개 필드) — Phase 0 이후 모든 phase가 참조.

---

## 목적

`/auto`가 "표준 PDCA 프로젝트"만 가정하던 한계 해결. 진입 즉시 프로젝트의 실제 구조·도구·governance·도메인을 인식하여 적응.

## ContextProfile schema

```yaml
context_profile:
  docs_layout: "standard_pdca" | "ebs_style" | "react_style" | "python_sphinx" | "custom" | "none"
  tools_registry:
    - name: <tool_name>
      cmd: <executable_path>
      role: "drift_check" | "kpi" | "lint" | "test" | "build" | "other"
  governance_profile: "ebs_5teams" | "single_dev" | "team_pr_review" | "oss_maintainer" | "generic"
  domain_profile: "frontend_react" | "frontend_vue" | "backend_python" | "backend_node" | "monorepo" | "poker_game" | "ecommerce" | "generic"
  fit_score: 0-100  # /auto가 이 컨텍스트에 적합한 정도 (Phase -1.5에서 사용)
```

## Step 1: docs 구조 스캔

```bash
# Pattern detection (read-only)
ls docs/ 2>/dev/null | head -20
ls docs/00-prd 2>/dev/null && layout="standard_pdca"
ls "docs/1. Product" 2>/dev/null && layout="ebs_style"
ls docs/source 2>/dev/null && layout="python_sphinx"
[ -f README.md ] && [ ! -d docs/ ] && layout="readme_only"
[ ! -f README.md ] && [ ! -d docs/ ] && layout="none"
# 매칭 안 되면 "custom"
```

| docs_layout | 감지 신호 | /auto 적응 |
|-------------|----------|-----------|
| `standard_pdca` | `docs/00-prd/`, `docs/01-plan/` | 현재 v25.6 동작 (변경 없음) |
| `ebs_style` | `docs/1. Product/`, `docs/2. Development/`, `docs/4. Operations/Reports/` | PRD/Plan/Design/Report 출력 위치 변경 |
| `react_style` | `README.md` + `docs/`만 (분리 없음) | PRD 생성 생략, README 갱신만 |
| `python_sphinx` | `docs/source/conf.py` | reStructuredText 형식 출력 |
| `custom` | 위 모두 매칭 안 됨 | 사용자에게 출력 위치 질의 |
| `none` | docs 디렉토리 자체 부재 | docs 생성 여부 사용자 결정 |

## Step 2: 자체 도구 발견

```bash
# 검증 도구 패턴
find tools/ -name "*.py" -executable 2>/dev/null
find scripts/ -name "*.py" -executable 2>/dev/null
find . -maxdepth 2 -name "Makefile" 2>/dev/null
[ -f package.json ] && cat package.json | jq '.scripts'
[ -f pyproject.toml ] && grep -A 20 '\[tool\.' pyproject.toml
```

도구 분류 키워드 (이름 또는 docstring 매칭):

| role | 키워드 |
|------|--------|
| `drift_check` | "drift", "spec_drift", "consistency", "audit" |
| `kpi` | "reimplementability", "score", "metric", "audit" |
| `lint` | "lint", "ruff", "eslint", "flake8" |
| `test` | "test", "pytest", "jest", "playwright" |
| `build` | "build", "bundle", "compile" |

**예시 (ebs)**:
```yaml
tools_registry:
  - name: spec_drift_check
    cmd: python tools/spec_drift_check.py --all --format=json
    role: drift_check
  - name: reimplementability_audit
    cmd: python tools/reimplementability_audit.py
    role: kpi
```

**예시 (React)**:
```yaml
tools_registry:
  - name: lint
    cmd: npm run lint
    role: lint
  - name: test
    cmd: npm test
    role: test
  - name: build
    cmd: npm run build
    role: build
  - name: lighthouse
    cmd: npx lighthouse-ci autorun
    role: kpi
```

## Step 3: Governance 감지

CLAUDE.md 또는 README.md에서 패턴 감지:

```bash
test -f CLAUDE.md && CLAUDE_MD="CLAUDE.md"
test -f README.md && README="README.md"

# 5팀 패턴 (ebs)
grep -E "Team [0-9]|팀 [0-9]" "$CLAUDE_MD" "$README" 2>/dev/null

# Governance version 패턴 (V9.5, V10.0 등)
grep -E "V[0-9]+\.[0-9]+|governance|SG-[0-9]" "$CLAUDE_MD" 2>/dev/null

# OSS maintainer 패턴
test -f CONTRIBUTING.md && grep -i "maintainer\|approval" CONTRIBUTING.md
```

| governance_profile | 감지 | /auto 적응 |
|-------------------|------|-----------|
| `ebs_5teams` | "Team 0-4" + V* + SG-* | architect = team conductor 위임, V* 명명 규약 사용 |
| `team_pr_review` | CONTRIBUTING.md + CODEOWNERS | architect APPROVE 후 사용자 PR 리뷰 대기 |
| `oss_maintainer` | CONTRIBUTING.md + LICENSE | maintainer signoff 명시 |
| `single_dev` | CLAUDE.md "혼자", "solo" | architect 단독 결정 OK |
| `generic` | 위 모두 부재 | 현재 v25.6 동작 |

## Step 4: 도메인 추정

```bash
# package.json deps
[ -f package.json ] && cat package.json | jq -r '.dependencies | keys[]' 2>/dev/null

# requirements.txt
[ -f requirements.txt ] && cat requirements.txt | head -20

# README 첫 100단어 분석
head -100 README.md 2>/dev/null
```

| domain_profile | 신호 |
|----------------|------|
| `frontend_react` | next, react, @types/react, vite, tailwindcss |
| `frontend_vue` | vue, nuxt, vite |
| `backend_python` | fastapi, django, flask, sqlalchemy |
| `backend_node` | express, fastify, nestjs, prisma |
| `poker_game` | "poker", "blind", "deck", "rfid" 키워드 |
| `ecommerce` | stripe, shopify, "checkout", "cart" |
| `monorepo` | turbo.json, nx.json, pnpm-workspace.yaml |
| `generic` | 위 모두 매칭 안 됨 |

## Step 5: fit_score 산정 (Phase -1.5에서 사용)

```
fit_score = (
  docs_layout_score (0-25) +
  tools_compat_score (0-25) +
  complexity_match_score (0-25) +
  domain_fit_score (0-25)
)

docs_layout_score:
  standard_pdca → 25
  ebs_style → 15 (custom path 처리 가능)
  react_style → 20
  custom → 10
  none → 5

tools_compat_score:
  tools_registry 비어있음 → 25 (자체 도구 충돌 없음)
  tools_registry [drift_check, kpi 모두 있음] → 25 (S3로 통합 가능)
  tools_registry 일부만 → 15
  tools_registry 명시적 conflict → 5

complexity_match_score:
  복잡도 4-7 (PDCA sweet spot) → 25
  복잡도 1-3 (단순) → 10 (overkill 위험)
  복잡도 8-10 (refactor) → 15 (다중 cycle 권장 = /iteration)

domain_fit_score:
  generic / 일반 web app → 25
  domain 특화 (poker, medical, finance) → 10 (도메인 지식 부족)
  research/exploratory → 5 (PDCA 부적합)
```

## Step 6: ContextProfile 결과 출력

`/auto`의 다른 phase에서 다음과 같이 참조:

```
Phase 0: 옵션 파싱 시 context_profile.docs_layout 확인
Phase 1: PRD/Plan 출력 위치를 docs_layout에 따라 결정
  - standard_pdca → docs/00-prd/
  - ebs_style → docs/1. Product/
  - react_style → README.md inline
  - custom → 사용자 질의
Phase 3: qa-tester가 tools_registry 사용 (S3 tool-integration.md 참조)
Phase 4: 보고서 출력 위치 docs_layout 따라 결정
```

## 검증 시나리오

### Scenario A: ebs 프로젝트 진입
```
Phase -1 출력:
  docs_layout: ebs_style
  tools_registry: [spec_drift_check, reimplementability_audit]
  governance_profile: ebs_5teams
  domain_profile: poker_game
  fit_score: 50 (custom path 15 + tools 25 + complexity 25 + domain 10 = 75... 보정 -25 for governance complexity)
```

### Scenario B: 신규 React 프로젝트
```
Phase -1 출력:
  docs_layout: react_style
  tools_registry: [lint, test, build, lighthouse]
  governance_profile: generic (or team_pr_review)
  domain_profile: frontend_react
  fit_score: 90+
```

### Scenario C: 빈 프로젝트 (`mkdir test && cd test`)
```
Phase -1 출력:
  docs_layout: none
  tools_registry: []
  governance_profile: generic
  domain_profile: generic
  fit_score: 60 (custom path 5 + tools 25 + complexity ? + domain 25)
  → 사용자에게 docs 생성 여부 질의
```

## 출력 표준

Phase -1 완료 시 항상 다음 형식 출력:

```
═══ Phase -1: Context Detection ═══
docs_layout:        {layout}
tools_registry:     {N개 도구 발견 — names list}
governance_profile: {profile}
domain_profile:     {profile}
fit_score:          {0-100} → Phase -1.5 진입
═══════════════════════════════════
```
