# 에이전트 파일 형식 표준

42개 로컬 에이전트(`.claude/agents/`)의 통일된 파일 형식을 정의합니다.

## Frontmatter YAML (필수 필드)

```yaml
---
name: agent-name          # 에이전트 식별자 (kebab-case)
description: "..."        # 에이전트 역할 설명 (1-2문장)
model: sonnet|haiku|opus  # 모델 티어 (기본: sonnet)
tools: Read, Write, ...   # 허용 도구 목록 (쉼표 구분)
---
```

### 모델 선택 기준

| 복잡도 | 모델 | 사용 조건 |
|--------|------|----------|
| LOW | `haiku` | 단순 조회, 보고서, 소규모 수정 |
| MEDIUM/HIGH | `sonnet` | 구현, 디버깅, 아키텍처 (기본) |
| 특수 요청 | `opus` | `--opus` 플래그 명시 시만 |

### 허용 도구 목록 (예시)

| 읽기 전용 에이전트 | 전체 권한 에이전트 |
|--------------------|-------------------|
| `Read, Grep, Glob` | `Read, Write, Edit, Bash, Grep, Glob, TodoWrite` |

## XML 태그 표준 섹션

42개 에이전트에서 일관되게 사용되는 XML 태그 정의:

### 필수 태그

```xml
<Role>
  에이전트의 핵심 역할과 정체성을 정의합니다.
  "당신은 X 전문가입니다. Y 작업을 Z 방식으로 수행합니다."
</Role>
```

```xml
<Critical_Constraints>
  절대로 해서는 안 되는 행동 목록.
  - 프로세스 전체 종료 금지
  - API 키 방식 사용 금지
  - main 브랜치 직접 수정 금지 (허용 파일 제외)
</Critical_Constraints>
```

### 선택 태그

```xml
<Anti_Patterns>
  피해야 할 잘못된 패턴.
  흔히 발생하는 실수나 잘못된 구현 방식.
</Anti_Patterns>
```

```xml
<Verification_Before_Completion>
  완료 주장 전 반드시 확인해야 할 체크리스트.
  - [ ] 빌드 통과
  - [ ] 테스트 통과
  - [ ] Architect 검증
</Verification_Before_Completion>
```

```xml
<Inherits_From>
  상위 에이전트 (예: executor-high).
  상위 에이전트의 모든 규칙을 상속합니다.
</Inherits_From>
```

## Mantle Prompt 원칙

Mantle Prompt는 XML 태그를 활용하여 에이전트의 행동 경계를 명확히 설정하는 방법론입니다.

### 역할 경계 명확화
`<Role>` 태그로 에이전트 정체성을 고정합니다.
- 에이전트가 해야 할 일과 하지 말아야 할 일을 명시
- 모호한 상황에서 판단 기준 제공

### 제약 계층화
```
Critical (절대 금지) > Standard (기본 규칙) > Recommended (권장 사항)
```
- `<Critical_Constraints>`: 위반 시 즉시 차단
- `<Anti_Patterns>`: 경고 및 교정
- 권장 사항: 가이드라인 형태로 본문에 기술

### 검증 루프 강제
`<Verification_Before_Completion>` 태그로 완료 전 검증을 의무화합니다.
- "구현했다" 주장 전 실제 증거 필요
- 테스트 통과 → Architect 검증 → 완료 선언

## 에이전트 파일 예시

```markdown
---
name: executor
description: Focused task executor for implementation work (Sonnet)
model: sonnet
tools: Read, Glob, Grep, Edit, Write, Bash, TodoWrite
---

<Role>
당신은 구현 전문 에이전트입니다.
설계 문서를 보고 코드를 작성하며, 테스트를 통과시키는 것이 목표입니다.
</Role>

<Critical_Constraints>
- 10줄 초과 코드 변경은 반드시 계획 먼저
- 테스트 없이 완료 주장 금지
- main 브랜치 직접 수정 금지
</Critical_Constraints>

<Verification_Before_Completion>
- [ ] 린트 통과 (ruff check)
- [ ] 테스트 통과 (pytest)
- [ ] Architect 검증 요청
</Verification_Before_Completion>
```

## 네이밍 컨벤션

| 대상 | 형식 | 예시 |
|------|------|------|
| 에이전트 파일명 | `kebab-case.md` | `code-reviewer.md` |
| `name` 필드 | `kebab-case` | `code-reviewer` |
| `description` | 영어, 1-2문장 | "Expert code review specialist." |
| XML 태그 | `PascalCase` with underscore | `<Critical_Constraints>` |

## 참조

- 에이전트 목록: `docs/AGENTS_REFERENCE.md`
- 모델 티어링: `~/.claude/CLAUDE.md` Smart Model Routing 섹션
- 스킬 시스템: `.claude/skills/` (SKILL.md 형식)

---
*최초 작성: 2026-02-23 | 버전: 1.0.0*
