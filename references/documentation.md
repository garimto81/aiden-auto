---
title: 문서화 규칙
impact: MEDIUM
section: docs
paths:
  - "docs/**/*"
  - "**/*.md"
  - "**/mockup*"
  - "**/SKILL.md"
---

# 문서화 규칙

## 시각화 필수

PRD 및 아키텍처 문서에는 반드시 시각적 자료 포함

| 단계 | 작업 | 산출물 |
|------|------|--------|
| 1 | HTML 목업 생성 | `docs/mockups/*.html` |
| 2 | 스크린샷 캡처 | `docs/images/*.png` |
| 3 | 문서에 이미지 첨부 | PRD, 설계 문서 |

## 시각화 흐름

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  HTML 목업  │────▶│  스크린샷   │────▶│  문서 첨부  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 목업 생성 방법

```powershell
# 목업 파일 생성
Write docs/mockups/feature-name.html

# Playwright로 스크린샷 캡처
npx playwright screenshot docs/mockups/feature-name.html docs/images/feature-name.png
```

## 적용 대상

| 문서 유형 | 시각화 필수 여부 |
|-----------|-----------------|
| PRD (기능 명세) | ✅ 필수 |
| 아키텍처 설계 | ✅ 필수 |
| API 문서 | ⚠️ 권장 |
| 변경 로그 | ❌ 선택 |

## Checklist 표준

Slack List 연동을 위한 Checklist 작성 필수

### 문서 위치

| 순위 | 경로 |
|:----:|------|
| 1 | `docs/checklists/PRD-NNNN.md` |
| 2 | `tasks/prds/NNNN-prd-*.md` |
| 3 | `docs/CHECKLIST.md` |

### PR-Checklist 연결

```
PR 제목: feat: add login [PRD-0001] #123
브랜치: feat/PRD-0001-123-add-login
```

### 자동 체크 형식

```markdown
- [ ] 기능 구현 (#101)     ← PR #101 머지 시 자동 체크
- [ ] 테스트 작성         ← 수동 체크
```

## 문서 구조 규칙

### 변경 이력 최하단 배치 (필수)

변경 이력, 버전 히스토리, Changelog는 **항상 문서 최하단**에 배치합니다.

| 규칙 | 내용 |
|------|------|
| **위치** | 문서 최하단 (마지막 섹션) |
| **헤딩** | `## 변경 이력` 또는 `## 버전 이력` |
| **이유** | 사용자에게 중요한 내용(사용법, 기능)이 먼저 보여야 함 |

**올바른 문서 구조:**
```markdown
# 제목
> 핵심 설명

## 사용법 / 기능 (가장 중요한 내용 먼저)
## 옵션 / 설정
## 세부 워크플로우
...
## 변경 이력          ← 항상 최하단
```

**금지 패턴:**
```markdown
# 제목
## 🆕 v2.0 변경사항    ← ❌ 상단 배치 금지
## 사용법
```

### 적용 대상

| 문서 유형 | 적용 |
|-----------|:----:|
| SKILL.md | ✅ |
| CLAUDE.md | ✅ |
| docs/*.md | ✅ |
| commands/*.md | ✅ |
| AGENTS_REFERENCE.md | ✅ |

## 상세 문서

- `.github/CHECKLIST_STANDARD.md`
- `docs/RESPONSE_STYLE.md`
