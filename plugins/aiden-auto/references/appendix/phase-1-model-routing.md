# Phase 1 Appendix — Adaptive Model Routing (Task 자동 분류)

> 이 파일은 `phase-1-plan.md` 의 부록입니다. Phase 0.3 진입 시 lazy load.
> 원본: `phase-1-plan.md` (v25.2) 의 Step 0.3 섹션 분리 (Flaw 5 컨텍스트 예산 대응).

Phase 0에서 Task 특성을 자동 분류하여 에이전트별 최적 모델을 선택합니다.

---

```
# Phase 0.3 — Task 복잡도 자동 감지
def classify_task(user_request, affected_files):
    file_count = len(affected_files)
    keywords = extract_keywords(user_request)

    if file_count <= 1 and any(k in keywords for k in ["format", "typo", "rename", "summary"]):
        return "TRIVIAL"    # → Haiku 항상
    elif file_count <= 5 and not any(k in keywords for k in ["refactor", "debug", "design", "architect"]):
        return "STANDARD"   # → Sonnet (기본)
    elif any(k in keywords for k in ["refactor", "debug", "design"]):
        return "COMPLEX"    # → Opus (기본)
    elif any(k in keywords for k in ["architect", "system", "migration", "breaking"]):
        return "CRITICAL"   # → Opus 항상
    else:
        return "STANDARD"   # 기본값

# --eco 옵션 결합
def apply_eco_override(classification, eco_level):
    if eco_level == "eco":
        # Opus → Sonnet
        return "STANDARD" if classification in ("COMPLEX", "CRITICAL") else classification
    elif eco_level == "eco-2":
        # + 비핵심 Sonnet → Haiku
        return "TRIVIAL" if classification == "STANDARD" else "STANDARD"
    elif eco_level == "eco-3":
        return "TRIVIAL"  # 전부 Haiku
    return classification
```

**InitContract 확장**: `"adaptive_tier": "TRIVIAL|STANDARD|COMPLEX|CRITICAL"` 필드 추가.

---

## v28.1+ 변경: 글로벌 model-router 우선

**중요**: 본 섹션의 정적 분류 로직은 v28.1 이전 잔재입니다. 글로벌 CLAUDE.md
"Dynamic Model Routing (Advisor Pattern v1)" 규칙이 우선합니다:

1. /auto 진입 시 첫 호출 = `Agent(subagent_type="model-router", model="haiku", ...)`
2. router 가 31-key JSON model_plan 반환
3. Lead 가 모든 후속 Agent() 호출에 `model=plan["..."]` 동적 주입
4. 파싱 실패 시 → 전체 sonnet 폴백 + **사용자 알림 필수** (Flaw 4 fix)

본 정적 분류는 model-router 가 사용 불가한 경우의 폴백 참고 자료로만 활용하세요.
