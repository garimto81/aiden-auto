---
name: plan
description: Plan mode UI 목업 — ASCII 와이어프레임 + mockup-spec 생성
---

# /plan - Plan Mode UI 목업

Plan mode에서 UI 목업을 시각화합니다. ASCII 와이어프레임 + 구조화된 mockup-spec을 생성하여 구현 전 UI 합의를 가능하게 합니다.

## Usage

```bash
/plan [name] [options]

Options:
  --screens=N      화면 수 (1-5, 기본: 1)
  --layout=TYPE    1-column | sidebar | 2-column | tabs
  --flow           화면 간 Mermaid 흐름도 포함
  --prd=PRD-NNNN   PRD 연결 (추천 백엔드에 영향)
  --backend=TYPE   추천 백엔드 지정 (html|stitch|mermaid)
```

## 출력 (3-Tier)

```
/plan "대시보드"
  │
  ├─ Tier 1: ASCII 와이어프레임 (터미널 직접 출력)
  │   65자 폭 박스 문자 레이아웃
  │
  ├─ Tier 2: mockup-spec (계획 파일에 삽입)
  │   YAML: 화면명, 레이아웃, 컴포넌트, 흐름, 추천 백엔드
  │
  └─ Tier 3: Mermaid 흐름도 (--flow 시)
      화면 간 네비게이션 다이어그램
```

## 예시

### 단일 화면
```
/plan "로그인 화면"
```

출력:
- 터미널: ASCII 로그인 폼 와이어프레임
- 계획 파일: `mockup-spec` 블록 (name, components, flow)

### 다중 화면 + 흐름도
```
/plan "주문 관리" --screens=3 --flow --layout=sidebar
```

출력:
- 터미널: 3개 화면 ASCII 와이어프레임
- 계획 파일: 3개 `mockup-spec` 블록 + Mermaid 흐름도

### PRD 연결
```
/plan "대시보드" --prd=PRD-0012
```

출력:
- PRD 내용 기반 컴포넌트 자동 추출
- `recommended_backend: stitch` (PRD 연결 시 고품질 추천)

## mockup-spec 형식

계획 파일에 삽입되는 YAML 블록:

````yaml
## UI Mockup Specifications

```mockup-spec
name: screen-name
description: 화면 설명
recommended_backend: html|stitch|mermaid
layout: 1-column|sidebar|2-column|tabs
viewport: 900x600
components:
  - type: header|sidebar|form|table|cards|chart|modal|tabs
    content: "설명"
flow:
  - "trigger → target-screen"
style_notes:
  - "B&W Refined Minimal"
execution_command: '/mockup "화면명" --options'
```
````

## Post-Plan 연계

ExitPlanMode 승인 후:
1. 계획 파일에서 `mockup-spec` 블록 자동 감지
2. 각 spec의 `execution_command` 추출
3. "목업을 생성할까요?" 자동 제안
4. 승인 시 `/mockup` 순차 실행

## Plan Mode 제약

이 커맨드는 plan mode 전용:
- 파일 생성/수정 없음 (계획 파일 1개 예외)
- Bash 실행 없음
- ASCII 와이어프레임은 터미널 텍스트로만 출력
- 실제 HTML/PNG 생성은 ExitPlanMode 후 `/mockup`으로 수행

## 기존 /mockup과의 관계

| 상황 | 커맨드 |
|------|--------|
| Plan mode에서 UI 합의 | `/plan` |
| 실제 목업 생성 (HTML/PNG) | `/mockup` |
| Plan → 실제 자동 전환 | `/plan` spec → `/mockup` 자동 제안 |
