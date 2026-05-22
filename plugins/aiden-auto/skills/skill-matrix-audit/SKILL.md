---
name: skill-matrix-audit
description: skill 디렉토리 3 경로 (project local / global user / plugin marketplace) 를 전수 검색하여 각 SKILL.md 의 무결성을 검증한다. NAME_MISMATCH (dir명 ≠ frontmatter name), WEAK_DESC (description 50자 미만), STUB (본문 10줄 미만 또는 deprecated 키워드), NO_FRONTMATTER, DUPLICATE (동일 name 중복) 를 자동 감지하고 JSON + 표로 리포트한다. skill 추가/삭제/이름변경 직후, "skill 무결성", "skill audit", "deprecated stub 검출", "skill 위치 확인" 등이 언급될 때 반드시 사용.
---

# Skill Matrix Audit

## When to use

이 skill 은 다음 상황에 즉시 사용한다:

- 새 skill 을 추가하거나 기존 skill 을 수정·삭제한 직후 무결성 검증
- "skill 무결성", "skill audit", "deprecated stub 검출", "skill 위치", "SKILL.md 검증" 등이 언급된 경우
- skill 라우팅 이상 (예: wrong skill 실행, skill not found) 디버깅 시
- 새 plugin 설치 후 skill 이 올바르게 등록됐는지 확인
- skill 이름 변경 / 이동 / 삭제 후 sync 점검

frontmatter 가 없거나 description 이 짧으면 auto-trigger (rule 16) 가 skill 을 찾지 못한다. 이 skill 은 그런 결함을 조기에 잡는다.

## How to use

```bash
python C:/claude/.claude/skills/skill-matrix-audit/scripts/audit_skills.py
```

10 초 이내 실행. exit code:
- `0` = 이슈 없음 (skill 정상)
- `1` = 이슈 1 개 이상 발견 (수정 필요)

## Output format

### 콘솔 출력

```
=== Skill Audit Report (2026-05-12T12:34:56) ===

Skills found: 42

Status distribution:
  OK                   :  30
  STUB                 :   5
  WEAK_DESC            :   4
  NAME_MISMATCH        :   2
  NO_FRONTMATTER       :   1

Issues found: 12

  [STUB            ] old-feature     C:/claude/.claude/skills/old-feature/SKILL.md
  [WEAK_DESC       ] chunk           C:/Users/.../skills/chunk/SKILL.md
  ...

Saved to: C:/claude/.claude/state/skill-matrix-mapping.json
```

## Status 의미

| status | 의미 | 조치 |
|--------|------|------|
| **OK** | frontmatter 정상, description 충분, 본문 10줄+ | 정상 |
| **NAME_MISMATCH** | dir 이름 ≠ frontmatter `name` 필드 | frontmatter name 또는 dir명 통일 |
| **WEAK_DESC** | description 이 50자 미만 | description 보강 (키워드 + 트리거 조건) |
| **STUB** | 본문 10줄 미만 또는 "deprecated"/"redirect stub" 본문 포함 | 내용 보강 또는 파일 삭제 |
| **NO_FRONTMATTER** | YAML frontmatter (`---`) 없음 | frontmatter 추가 |
| **DUPLICATE** | 동일 `name` 이 2 곳 이상 | 1 곳만 남기거나 name 분리 |

## After audit — 권장 조치

| 이슈 | 조치 |
|------|------|
| STUB | 내용 작성 또는 `/auto` 로 재생성. deprecated 확정이면 파일 삭제 |
| WEAK_DESC | description 에 트리거 키워드 + 사용 시나리오 보강 (50자 이상) |
| NAME_MISMATCH | frontmatter `name:` 을 dir 명과 일치시키는 것이 표준 |
| NO_FRONTMATTER | `SKILL_TEMPLATE.md` 참조하여 frontmatter 추가 |
| DUPLICATE | 우선순위 경로(project local > global > plugin) 에 따라 1 개만 유지 |
