# Plugin Fusion Rules (v24.0)

> 플러그인 자동 활성화 규칙 정의. `/auto` Phase 0.4에서 참조.

---

## 1. Project Type Detection

프로젝트 루트에서 파일 존재 여부로 타입을 감지합니다.

| 감지 파일 | 프로젝트 타입 | 활성화 플러그인 |
|-----------|-------------|----------------|
| `package.json` + `react` dep | React/Next.js | frontend-design, code-review, typescript-lsp |
| `package.json` + quasar dep | Quasar/Vue | frontend-design, code-review, typescript-lsp |
| `quasar.config.*` / `quasar.conf.*` | Quasar | frontend-design, code-review, typescript-lsp |
| `tsconfig.json` | TypeScript | typescript-lsp, code-review |
| `next.config.*` | Next.js | frontend-design, code-review, typescript-lsp |
| `pyproject.toml` \| `setup.py` | Python | code-review |
| `Cargo.toml` | Rust | code-review |
| `go.mod` | Go | code-review |
| `.claude/` 존재 | Claude Code 프로젝트 | claude-code-setup, superpowers |
| `figma.com` URL in args | Figma 연동 | figma |

**다중 타입 지원**: 프로젝트가 여러 타입에 해당하면 모든 매칭 플러그인이 활성화됩니다.

---

## 2. Complexity-Tier Plugin Mapping

복잡도 모드에 따라 플러그인 활성 범위가 확장됩니다.

| 모드 | 기본 활성 | 추가 활성 |
|------|----------|----------|
| LIGHT (0-1) | typescript-lsp (TS 프로젝트 시) | — |
| STANDARD (2-3) | + code-review, superpowers | Iron Laws 주입 |
| HEAVY (4-6) | + feature-dev, claude-code-setup | 전체 플러그인 |

---

## 3. Superpowers 17 Skills → /auto Phase Mapping

### Phase 0: INIT
| Skill | 주입 시점 | 적용 방식 |
|-------|----------|----------|
| using-superpowers | Phase 0 시작 | 스킬 라우팅 확인 (이미 Lead가 수행) |

### Phase 1: PLAN
| Skill | 주입 시점 | 적용 방식 |
|-------|----------|----------|
| brainstorming | Step 1.0 Requirement Gathering | STANDARD/HEAVY에서 PRD 작성 전 brainstorming 세션 |
| writing-plans | Step 1.3 계획 수립 | planner prompt에 plan 작성 가이드 주입 |
| writing-skills | Step 1.3 (스킬 생성 작업 시) | 스킬 파일 작성 시 품질 가이드 주입 |

### Phase 2: BUILD
| Skill | 주입 시점 | 적용 방식 |
|-------|----------|----------|
| test-driven-development | Step 2.1 구현 | impl-manager prompt에 TDD Iron Law 주입 |
| subagent-driven-development | Step 2.1 구현 (HEAVY) | 병렬 executor 조율 시 2-Stage Review Gate |
| executing-plans | Step 2.1 구현 | plan 기반 구현 체크포인트 |
| requesting-code-review | Step 2.2 Code Review | 리뷰 요청 시 체크리스트 주입 |
| receiving-code-review | Step 2.2 Code Review | 리뷰 결과 수신 시 검증 프로토콜 |
| dispatching-parallel-agents | Step 2.1 (HEAVY 병렬) | Wave 분할 + 충돌 방지 규칙 |
| using-git-worktrees | Step 2.1 (--worktree) | worktree 격리 실행 가이드 |

### Phase 3: VERIFY
| Skill | 주입 시점 | 적용 방식 |
|-------|----------|----------|
| systematic-debugging | Step 3.1 QA FAIL 시 | Architect 진단을 D0-D4 체계로 강화 |
| verification-before-completion | Step 3.3 최종 검증 | 완료 선언 전 증거 수집 강제 |

### Phase 4: CLOSE
| Skill | 주입 시점 | 적용 방식 |
|-------|----------|----------|
| finishing-a-development-branch | Step 4.2 | merge/PR/cleanup 옵션 제시 |

### Cross-cutting (전 Phase)
| Skill | 적용 범위 | 적용 방식 |
|-------|----------|----------|
| verification-before-completion | 모든 Gate | Iron Law: 증거 없이 완료 선언 금지 |
| test-driven-development | 모든 코드 작성 | Iron Law: 실패 테스트 없이 코드 작성 금지 |
| systematic-debugging | 모든 실패 | Iron Law: Root cause 없이 수정 금지 |

---

## 4. Code Review Plugin Hybrid (STANDARD/HEAVY)

code-review 플러그인은 5개 병렬 Sonnet 에이전트를 제공합니다:

| Agent | 역할 |
|-------|------|
| CLAUDE.md Compliance | CLAUDE.md 규칙 준수 검사 |
| Shallow Bug Scan | 표면 버그 탐지 |
| Git Blame Context | 변경 이력 기반 분석 |
| PR Comment Patterns | PR 코멘트 패턴 분석 |
| Code Comment Compliance | 코드 주석 품질 검사 |

**Hybrid Review 흐름**:
1. 내부 code-reviewer (기존) → APPROVE/REVISE
2. code-review 플러그인 5-agent → 추가 이슈 수집
3. 두 결과 병합 → 최종 판정

---

## 5. Feature-Dev Plugin Integration (HEAVY)

feature-dev 플러그인은 guided feature development를 제공합니다:
- 코드베이스 이해 + 아키텍처 분석 → Phase 1.2 사전 분석에 병합
- 단독 실행하지 않고, /auto Phase 1 내에서 분석 결과로 활용

---

## 6. Claude-Code-Setup Plugin (HEAVY / Audit)

claude-code-setup 플러그인의 automation-recommender:
- /auto: Phase 4에서 완료 후 자동화 개선 제안
- /audit: Phase 2.5에서 Setup 최적화 점검

---

## 7. Plugin Activation Detection Code

```python
# Phase 0.4에서 Lead가 직접 실행하는 감지 로직 (의사코드)
activated_plugins = []

# Project type detection
if Glob("tsconfig.json"):
    activated_plugins.append("typescript-lsp")
if Glob("package.json"):
    pkg = Read("package.json")
    if '"react"' in pkg or '"next"' in pkg:
        activated_plugins.extend(["frontend-design", "code-review"])
    elif '"quasar"' in pkg or '"@quasar/app-vite"' in pkg or '"@quasar/app-webpack"' in pkg:
        activated_plugins.extend(["frontend-design", "code-review", "typescript-lsp"])
    else:
        activated_plugins.append("code-review")
if Glob("quasar.config.*") or Glob("quasar.conf.*"):
    activated_plugins.extend(["frontend-design", "code-review", "typescript-lsp"])
if Glob("next.config.*"):
    activated_plugins.append("frontend-design")
if Glob("pyproject.toml") or Glob("setup.py") or Glob("*.py"):
    activated_plugins.append("code-review")
if Glob(".claude/"):
    activated_plugins.extend(["claude-code-setup", "superpowers"])

# Complexity tier escalation
if mode in ["STANDARD", "HEAVY"]:
    activated_plugins.extend(["superpowers", "code-review"])
if mode == "HEAVY":
    activated_plugins.extend(["feature-dev", "claude-code-setup"])

# Deduplicate
activated_plugins = list(set(activated_plugins))
```

---

## 8. Iron Laws (superpowers 흡수)

| # | Iron Law | 원본 스킬 | /auto 적용 위치 |
|:-:|----------|----------|----------------|
| 1 | **TDD**: 실패 테스트 없이 프로덕션 코드 작성 금지 | test-driven-development | Phase 2.1 impl-manager |
| 2 | **Debugging**: Root cause 조사 없이 수정 금지 | systematic-debugging | Phase 3.1 QA FAIL |
| 3 | **Verification**: 증거 없이 완료 선언 금지 | verification-before-completion | Phase 2.3, 3.3 Gate |
