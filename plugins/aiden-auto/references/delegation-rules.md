# Delegation Rules

## What You Do vs. Delegate

| Action | YOU Do Directly | DELEGATE to Agent |
|--------|-----------------|-------------------|
| Read files for context | Yes | - |
| Quick status checks | Yes | - |
| Create/update todos | Yes | - |
| Communicate with user | Yes | - |
| Answer simple questions | Yes | - |
| **Minor code change (<=10 lines)** | Yes | - |
| **Substantial code change (>10 lines)** | NEVER | executor / executor-high |
| **Multi-file changes** | NEVER | executor / executor-high |
| **Complex debugging** | NEVER | architect |
| **UI/frontend work** | NEVER | designer |
| **Documentation** | NEVER | writer |
| **Deep analysis** | NEVER | architect / analyst |
| **Codebase exploration** | NEVER | explore / explore-medium / explore-high |
| **Research tasks** | NEVER | researcher |
| **Data analysis** | NEVER | scientist / scientist-high |
| **Visual analysis** | NEVER | vision |

## Path-Based Write Rules

| Allowed Paths (Direct Write OK) | Warned Paths (Should Delegate) |
|----------------------------------|-------------------------------|
| `~/.claude/**`, `.omc/**`, `.claude/**`, `CLAUDE.md`, `AGENTS.md` | `.ts`, `.tsx`, `.js`, `.jsx`, `.py`, `.go`, `.rs`, `.java`, `.c`, `.cpp`, `.svelte`, `.vue` |

Soft enforcement (warnings only). Audit log at `.omc/logs/delegation-audit.jsonl`.

## Magic Word Bypass

`!quick`, `!just`, `!hotfix` 키워드가 요청에 포함되면 Socratic Questioning(Step 0.2)과 clarification을 스킵하고 즉시 실행합니다.

| Magic Word | 효과 |
|------------|------|
| `!quick` | Socratic Q 스킵, LIGHT 모드 강제 |
| `!just` | Socratic Q 스킵, 확인 질문 없이 실행 |
| `!hotfix` | Socratic Q 스킵, LIGHT 모드 강제, `--skip-prd` 암묵 적용 |

## Parallelization Rules

- **2+ independent tasks** with >30 seconds work → Run in parallel
- **Sequential dependencies** → Run in order
- **Quick tasks** (<10 seconds) → Do directly

## Broad Request Detection (Ambiguity Score v1.0)

요청 모호성을 7개 팩터로 정량 측정:

| 팩터 | 가중치 | 조건 |
|------|:------:|------|
| 파일 경로 미언급 | +0.15 | 구체적 파일/디렉토리 없음 |
| 기술 용어 부재 | +0.10 | API, 함수명, 클래스명 등 없음 |
| 특정 대상 미지정 | +0.15 | 식별자(PascalCase, snake_case, 따옴표) 없음 |
| 범위 미정의 | +0.10 | only, all, specific 등 한정어 없음 |
| 다중 해석 가능 | +0.20 | 대명사 2회+, 모호 동사(fix, change, update) |
| 컨텍스트 충돌 | +0.15 | 현재 Phase와 요청 키워드 불일치 |
| 짧은 요청 | +0.15 | 30자 미만 |

**임계값**: score >= 0.5 → `/auto` Phase 1 (explore → plan)

**When BROAD REQUEST detected:** explore → (optional) architect → plan skill → user-preference questions only
