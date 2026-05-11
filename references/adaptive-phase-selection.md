# Adaptive Phase Selection (S2) — 복잡도 기반 동적 phase 구성

> **로딩 시점**: Phase 0 INIT의 복잡도 점수 산정 직후, 본격적 Phase 1 진입 전.
> **의존**: Phase 0의 복잡도 점수 (1-10).
> **목적**: 모든 작업에 Phase 0-4 전체를 강제하지 않고 복잡도에 따라 phase 동적 선택.

---

## 핵심 원칙

> "Phase 0-4 전체 = 복잡도 4-7 sweet spot 만 적합. 복잡도 1-3 = overkill. 복잡도 8-10 = 단일 cycle 부족 (`/iteration` 권장)."

`/auto`의 보편적 우월성 미달 원인 R4 (모든 phase 강제) 해결.

---

## 복잡도 → Phase Plan 매핑

| 복잡도 (10점) | Phase Plan | 근거 |
|--------------|------------|------|
| **1** (typo, 단일 file 1줄) | Phase 2 only | PRD/Plan/Verify 모두 overkill |
| **2** (간단 fix, 단일 file 다수 줄) | Phase 2 + Phase 3 (lite) | 검증만 추가 |
| **3** (small feature, 단일 module 1-2 file) | Phase 0 → 2 → 3 | Plan 생략 가능 |
| **4** (single feature, 1 module) | Phase 0 → 1 (mini) → 2 → 3 | Plan 간략화, 정상 흐름 |
| **5-6** (single feature, 다중 module) | Phase 0-4 전체 (current default) | sweet spot |
| **7** (cross-module feature) | Phase 0-4 전체 + Architect 추가 round | 정밀 검증 |
| **8** (refactor, 다수 module) | Phase 0-4 + 명시 경고 | 분할 권장 |
| **9-10** (architecture migration) | **/iteration 권장** | 단일 cycle 부족 |

## Phase 적응 모드

각 phase는 다음 모드로 실행 가능:

| Phase | mode 옵션 |
|-------|-----------|
| Phase 0 INIT | `full` / `minimal` / `skip` |
| Phase 1 PLAN | `full` (PRD+Plan+Design) / `mini` (Plan만, 1 page) / `skip` |
| Phase 2 BUILD | `full` (executor + reviewer) / `direct` (Lead 직접) / **`skip` 불가** |
| Phase 3 VERIFY | `full` (qa + arch + e2e) / `lite` (lint+test만) / `skip` |
| Phase 4 CLOSE | `full` (보고서 + cleanup) / `mini` (cleanup만) / `skip` |

## 복잡도별 mode 매핑

```yaml
복잡도 1:
  Phase 0: skip
  Phase 1: skip
  Phase 2: direct  # Lead가 직접 1줄 수정
  Phase 3: skip    # lint만 사용자 confirm
  Phase 4: skip
  예상 소요: 30초 - 1분

복잡도 2:
  Phase 0: minimal  # 옵션 파싱만
  Phase 1: skip
  Phase 2: direct
  Phase 3: lite     # lint + test
  Phase 4: skip
  예상 소요: 2-5분

복잡도 3:
  Phase 0: minimal
  Phase 1: skip     # PRD 없이 Plan 직접
  Phase 2: full     # executor 위임
  Phase 3: lite
  Phase 4: skip
  예상 소요: 5-10분

복잡도 4:
  Phase 0: full
  Phase 1: mini     # Plan만 (PRD/Design 생략)
  Phase 2: full
  Phase 3: full
  Phase 4: mini     # cleanup
  예상 소요: 10-20분

복잡도 5-6:
  Phase 0: full
  Phase 1: full     # PRD + Plan + Design
  Phase 2: full
  Phase 3: full
  Phase 4: full
  예상 소요: 20-60분

복잡도 7:
  복잡도 5-6 + Architect 추가 round (REJECT 시 재검토)
  예상 소요: 40-90분

복잡도 8:
  복잡도 5-6 + 사용자에게 분할 권장 메시지:
  "이 작업은 8/10. 분할하여 여러 /auto 호출 권장. 또는 /iteration 사용."
  + 사용자 confirm 시 진행

복잡도 9-10:
  자동 진행 거부:
  "이 작업은 {N}/10. 단일 /auto cycle로 부족.
   /iteration 사용 권장 (Impl-first 7-step 또는 Spec-first 5-step).
   강제 진행하려면 'force' 입력."
```

## 적응 로직

```
Phase 0 INIT 끝에서 복잡도 score = N (1-10) 산정 완료 시:

phase_plan = {
    "Phase 0": "full" if N >= 4 else ("minimal" if N == 2 or N == 3 else "skip"),
    "Phase 1": "full" if N >= 5 else ("mini" if N == 4 else "skip"),
    "Phase 2": "full" if N >= 3 else "direct",
    "Phase 3": "full" if N >= 4 else ("lite" if N >= 2 else "skip"),
    "Phase 4": "full" if N >= 5 else ("mini" if N == 4 else "skip"),
}

# 복잡도 8: 사용자 분할 권장
# 복잡도 9-10: /iteration 강력 권장 (자동 진행 거부)
```

## ContextProfile과의 결합

Phase -1의 fit_score도 함께 고려:

```
실효 phase plan = base(복잡도) ± fit_score 보정

fit_score < 50 + 복잡도 5:
  base = Phase 0-4 full
  보정: -1 단계 (Phase 0 minimal, Phase 4 mini) — fit 부족하므로 over-orchestration 방지

fit_score 80+ + 복잡도 5:
  base = Phase 0-4 full (변경 없음)

fit_score 80+ + 복잡도 2:
  base = Phase 2 + Phase 3 lite
  보정: 없음 (이미 minimal)
```

## 출력 표준

Phase 0 끝에 phase plan 출력:

```
═══ Phase 0: INIT 완료 ═══
복잡도: 4/10 (single feature, 1 module)
fit_score: 85/100 (Phase -1.5)

Adaptive Phase Plan:
  Phase 0: ✓ full (완료)
  Phase 1: → mini  (Plan만, PRD/Design 생략)
  Phase 2: → full  (executor 위임)
  Phase 3: → full  (qa + arch + e2e)
  Phase 4: → mini  (cleanup, 보고서 생략)
예상 소요: 12분
═══════════════════════════════
```

## 사용자 override

명시 옵션으로 phase plan 강제 가능:

```bash
/auto --full           # 복잡도 무관 Phase 0-4 전체 (현재 v25.6 동작)
/auto --minimal        # 모든 phase minimal/lite/skip 모드
/auto --phase=2,3      # Phase 2+3만 실행
/auto --skip-plan      # Phase 1 강제 skip
/auto --skip-verify    # Phase 3 강제 skip (위험)
```

## 안전 장치

- **Phase 2는 절대 skip 불가** (구현이 작업의 핵심)
- 복잡도 ≥ 4 작업의 Phase 3 skip 시 사용자 명시 confirm 필요 (안전)
- 복잡도 ≥ 8 작업에서 Phase 1 skip 시 거부 (Plan 부재 위험 큼)

## 본 적응의 핵심 가치

작업 복잡도에 비례한 orchestration. 단순 작업은 빠르게, 복잡 작업은 정밀하게. 직전 critic 보고서 R4 (Forced Full-Cycle) 해결.
