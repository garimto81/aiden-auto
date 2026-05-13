# Plan → Design 전환 게이트 (Mandatory)

> **출처**: aiden-auto v18.2 SKILL.md L526-571 (critic 분석 후 흡수, 2026-05-11)
> **5원칙 매핑**: #5 슈퍼앱 = 자율 검증 게이트가 풍부해야 한다.
> **로드 시점**: Phase 2 (Build) 진입 직전 또는 Design 산출물 작성 직전.

## 핵심 원칙

Design 문서를 작성하기 전에 Plan 문서가 *4개 필수 섹션*을 모두 가지고 있는지 자동 검증. 누락 시 Plan을 1회만 자동 보완 후 재검증. 두 번째 실패 시 사용자에게 보고 (자율 결정 영역을 넘었음을 명시).

## 4개 필수 섹션

| # | 섹션 | 확인 방법 |
|:-:|------|----------|
| 1 | 배경/문제 정의 | `## 배경` 또는 `## 문제 정의` 헤딩 존재 |
| 2 | 구현 범위 | `## 구현 범위` 또는 `## 범위` 헤딩 존재 |
| 3 | 예상 영향 파일 | 파일 경로 1개 이상 포함 (`.py`/`.ts`/`.md`/`.json` 등 확장자) |
| 4 | 위험 요소 | `## 위험` 또는 `위험 요소` 헤딩 존재 |

## 게이트 로직

```
plan_path = "docs/01-plan/{feature}.plan.md"
plan_content = Read(plan_path)

gate_checks = {
  "배경/문제 정의": has_heading(plan_content, ["## 배경", "## 문제 정의"]),
  "구현 범위":     has_heading(plan_content, ["## 구현 범위", "## 범위"]),
  "영향 파일":     has_file_path(plan_content),
  "위험 요소":     has_heading(plan_content, ["## 위험", "위험 요소"])
}

missing = [k for k, v in gate_checks.items() if not v]

if missing:
  # 1회 자동 보완 (executor sonnet)
  Agent(
    subagent_type="executor",
    description=f"Plan 누락 섹션 보완 ({len(missing)}개)",
    prompt=f"Plan 문서 {plan_path}에 누락 섹션을 보완하세요: {missing}. 기존 내용 보존 + 누락만 추가."
  )
  # 재검증 1회만
  plan_content = Read(plan_path)
  missing_retry = [k for k, v in gate_checks(plan_content).items() if not v]

  if missing_retry:
    # 자율 영역 초과 → 사용자 보고 (Core Philosophy: 자율 실패 시만 진입점 발생)
    Report: "Plan 게이트 통과 실패. 누락 섹션: {missing_retry}. 수동 보완 필요."
    STOP
```

## 흡수 시 정제 사항 (옛 1480줄 대비)

- `AskUserQuestion` 호출 제거 (Core Philosophy 위반) → 단순 Report + STOP
- `team_name`/`SendMessage`/`shutdown_request` 등 폐기 패턴 제거 (1:1 subagent 호출)
- 1회 자동 보완만 허용 (재시도 폭주 차단, Circuit Breaker 정합)

## 적용 위치

- **CODE chapter**: Phase 2 진입 직전 자동 발동
- **DOC chapter**: Plan→Design 흐름 사용 시 발동 (option)
- **ITERATION chapter**: 매 iteration 의 Plan 단계마다 발동
