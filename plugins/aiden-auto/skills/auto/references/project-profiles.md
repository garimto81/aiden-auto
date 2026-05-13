# Project Profiles (S4) — 프로젝트 유형별 워크플로우 적응

> **로딩 시점**: Phase -1 결과의 `governance_profile` + `domain_profile` 결정 직후.
> **의존**: `references/phase-minus-1-context-detect.md`.
> **목적**: 프로젝트 유형 따라 추가 도구·governance·검증 자동 적용.

---

## 6개 표준 Profile

각 profile은 (1) 감지 신호 (2) 추가 적용 사항 (3) 권장 paradigm 정의.

---

### Profile 1: `ebs_governance` (자체 governance + 5팀 + 자체 도구)

**감지 신호**:
- `CLAUDE.md`에 "Team 0", "Team 1", ..., "Team 4" 또는 "팀 0-4" 패턴
- `tools/spec_drift_check.py`, `tools/reimplementability_audit.py` 존재
- `docs/2. Development/2.5 Shared/team-policy.json` 또는 `docs/4. Operations/`
- governance version 패턴 (V9.5, V10.0 등)

**추가 적용**:

| Phase | 적응 |
|-------|------|
| Phase -1 | governance_profile = `ebs_5teams` 자동 설정 |
| Phase 0 | architect 호출 시 "team conductor" 역할로 위임 (Team 0) |
| Phase 1 | PRD/Plan 출력 path: `docs/1. Product/`, `docs/2. Development/` |
| Phase 2 | 구현 작업 분배: Team 1 (frontend), Team 2 (backend), Team 3 (art) |
| Phase 3 | qa-tester가 `tools/spec_drift_check.py` + `reimplementability_audit.py` 자동 실행 (S3 tool-integration) |
| Phase 3 | KPI: drift_count == 0 + reimplementability ≥ 90% |
| Phase 4 | 보고서 출력: `docs/4. Operations/Reports/{date}-{feature}.md` |
| Phase 4 | governance log: V* version + SG-* 결정 archive |

**권장 paradigm**: PDCA (default). 단 spec drift 작업 시 `--paradigm=spec-drift-recon`.

**금지**: 표준 `docs/00-prd/` 디렉토리 생성 금지 (ebs는 자체 path 사용).

---

### Profile 2: `react_app` (Next.js + Vercel 생태계)

**감지 신호**:
- `package.json`에 `next` 또는 `react` + `vite`/`webpack`
- `next.config.js` 또는 `vercel.json` 존재
- `app/` 또는 `pages/` 디렉토리

**추가 적용**:

| Phase | 적응 |
|-------|------|
| Phase 1 | PRD 별도 디렉토리 생략, `README.md` 또는 `docs/features/` 갱신 |
| Phase 2 | TypeScript 검증 (`tsc --noEmit`) 자동 추가 |
| Phase 2 | `vercel:react-best-practices` skill 통합 (마켓플레이스 plugin) |
| Phase 3 | 표준 검증: `npm run lint`, `npm test`, `npm run build` |
| Phase 3 | KPI: Lighthouse score (자동 실행 시 `npx lighthouse-ci autorun`) |
| Phase 3 | bundle size 측정 (선택) |
| Phase 4 | 보고서: `docs/changelogs/{date}.md` 또는 `CHANGELOG.md` |

**권장 paradigm**: PDCA + 컴포넌트 단위 분할. UI 변경 시 스크린샷 verifier 자동.

---

### Profile 3: `python_cli` (Python 모듈/CLI)

**감지 신호**:
- `pyproject.toml` 또는 `setup.py`
- `src/<package>/` 또는 `<package>/__init__.py` 패턴
- Single-package (monorepo 아님)

**추가 적용**:

| Phase | 적응 |
|-------|------|
| Phase 1 | PRD/Plan: `docs/source/` (Sphinx) 또는 `docs/specs/`, fallback README |
| Phase 2 | 구현 + type hints 검증 (`mypy`) |
| Phase 3 | 표준 검증: `ruff check`, `pytest`, `mypy` |
| Phase 3 | KPI: coverage percentage (`pytest --cov`) |
| Phase 4 | 보고서: `CHANGELOG.md` (Keep a Changelog 형식) |

**권장 paradigm**: PDCA + TDD (테스트 먼저). pyproject.toml에 pytest 설정 있을 시.

---

### Profile 4: `monorepo` (Turbo / Nx / pnpm-workspace)

**감지 신호**:
- `turbo.json`, `nx.json`, `pnpm-workspace.yaml`, 또는 `lerna.json`
- 복수 `packages/*/package.json` 또는 `apps/*/`

**추가 적용**:

| Phase | 적응 |
|-------|------|
| Phase 0 | 영향 받는 workspace 식별 (`turbo run build --filter=...`) |
| Phase 1 | Plan에 영향 workspace 명시 |
| Phase 2 | 변경 범위 limit: 명시된 workspace만 |
| Phase 3 | `turbo run test --filter=...` 또는 `nx affected:test` |
| Phase 3 | 영향 받지 않은 workspace는 검증 skip (속도 최적화) |
| Phase 4 | workspace별 변경 요약 |

**권장 paradigm**: PDCA + 영향 분석 우선.

---

### Profile 5: `fastapi_backend` (Python + FastAPI/Django/Flask)

**감지 신호**:
- `requirements.txt`/`pyproject.toml`에 fastapi, django, flask
- `main.py` 또는 `app.py` 또는 `manage.py`
- API spec 파일 (openapi.json, schema.py 등)

**추가 적용**:

| Phase | 적응 |
|-------|------|
| Phase 2 | API endpoint 추가 시 OpenAPI spec 자동 갱신 검증 |
| Phase 3 | 표준 검증 + `pytest`, contract test (api 응답 schema) |
| Phase 3 | DB migration 검증 (alembic 등) — 자동 dry-run |
| Phase 3 | KPI: contract test pass + p99 latency (선택) |

**권장 paradigm**: PDCA + Contract-first (OpenAPI 갱신 → 구현).

---

### Profile 6: `generic` (모든 profile 매칭 안 됨, fallback)

**감지 신호**: 위 5개 profile 모두 매칭 실패.

**추가 적용**: 없음. v25.6 표준 동작 그대로.

---

## Profile 적용 매트릭스

| Profile | 추가 도구 | docs path 변경 | KPI source |
|---------|----------|----------------|------------|
| ebs_governance | ✓ tools/spec_drift_check.py + reimplementability | ✓ 1.Product/, 4.Operations/Reports/ | reimplementability ≥ 90% |
| react_app | ✓ tsc, lint, lighthouse-ci | ✓ docs/features/ 또는 README | Lighthouse score |
| python_cli | ✓ ruff, mypy, pytest --cov | ✓ docs/source/ 또는 README | coverage % |
| monorepo | ✓ turbo affected / nx affected | 동일 | filtered tests |
| fastapi_backend | ✓ contract test, alembic dry-run | API spec | contract pass + latency |
| generic | (없음) | 표준 docs/00-prd/ | gap % (현재 v25.6) |

## Profile 결정 우선순위

복수 profile 매칭 시 우선순위:

```
1. ebs_governance (감지 신호 강력함, 우선)
2. monorepo (workspace 구조 명시)
3. react_app / python_cli / fastapi_backend (단일 stack)
4. generic (fallback)
```

## SKILL.md 통합 포인트

Phase -1 완료 후 다음 분기:

```
context_profile.governance_profile + domain_profile + tools_registry 종합:

IF "Team 0-4" + "tools/spec_drift_check.py" + "V*" 패턴:
  → profile = ebs_governance
ELIF "next" + "vercel" deps:
  → profile = react_app
ELIF "pyproject.toml" + "fastapi/django/flask":
  → profile = fastapi_backend
ELIF "turbo.json" or "nx.json":
  → profile = monorepo
ELIF "pyproject.toml" or "setup.py":
  → profile = python_cli
ELSE:
  → profile = generic
```

## 출력 표준

Phase -1 끝의 ContextProfile 출력에 profile 추가:

```
═══ Phase -1: Context Detection ═══
docs_layout:        ebs_style
tools_registry:     [spec_drift_check, reimplementability_audit] (2개)
governance_profile: ebs_5teams
domain_profile:     poker_game
project_profile:    ebs_governance  ← S4 신규
fit_score:          72/100
═══════════════════════════════════
```

## 사용자 override

명시 옵션:

```bash
/auto --profile=generic       # 강제 표준 동작
/auto --profile=react_app     # 강제 react profile (감지 잘못된 경우)
```

## 본 profile system의 핵심 가치

직전 critic 보고서 R3 (Governance 인식 부재) + R5 (Domain 무지) 해결.
프로젝트 유형마다 자동으로 적합한 도구·검증·보고 형식 적용.
