---
description: /goal 입력 시 /auto skill로 redirect. CC 빌트인 /goal은 /auto 내부에서 자동 활용
---

# /goal — /auto skill로 redirect

본 커맨드는 v28.2에서 `/auto` skill의 alias로 작동합니다.

- 사용자 입력 `/goal '<condition>'` → `/auto` skill 호출 (condition을 active-goal.json에 저장)
- CC 빌트인 `/goal` 메커니즘은 `/auto` 내부 Stop hook으로 자동 활용
- `/goal --builtin` 입력 시 본 redirect 우회하고 CC 빌트인 직접 사용

## 사용 예

```
/goal "모든 unit test PASS + console error 0 + 1단계 클리어 가능"
  → /auto가 Deep Interview skip (이미 condition 명시됨) → Phase 0 직진 → /goal Stop hook 자동 가동
```

## CC 빌트인 /goal 우회

`/goal --builtin <condition>` 입력 시 본 redirect 미발동. CC 공식 /goal 명령으로 직결.

## 관련

- `references/chapter-quota-ops.md` — HARNESS-OPS 카테고리 정의
- Plan Section 1: /auto = /goal = iteration 통합 아키텍처
- `hooks/goal_stop_evaluator.py` — Stop hook 직접 등록 메커니즘
