# Perfect Deliverable Protocol (v28.2)

> **Core Objective**: Phase 4 close 진입 시 "Done" 마크 전 visual/textual verification 의무화. /goal evaluator가 transcript에서 확인 가능한 형태로 증거 출력.

## 4단 Gate 구조

```
  Phase 3 verify 완료
       |
       v
  Gate 1: 자동 7항목 검증 (perfect-output-validator, opus)
       |
       v
  Gate 2: E2E QA + 증거 생성 (e2e-qa-prover, session type 분기)
       |
       v
  Gate 3: Submission Format 4 섹션 강제
       |
       v
  Gate 4: 미통과 시 자동 BLOCK + pdca-iterator 재진입
       |
       v
  /goal evaluator (Haiku) — transcript에서 보고 충족 판정
       |
   +---+---+
   YES     NO
    |       |
    v       v
  /goal   다음 turn 자동 시작
  종료
```

## Gate 1: 7항목 자동 검증

`perfect-output-validator.md` 참조. 모두 PASS 필요.

## Gate 2: E2E QA (Session Type 분기)

`e2e-qa-prover.md` 참조.

| 세션 타입 | 증거 형태 | 스크린샷 |
|----------|----------|:--------:|
| LOGIC_DATA | unit tests + log + status code + checksum | **❌ 금지** |
| VISUAL_INTERACTION | Playwright ≥3장 + (migration) before/after 2장 | **✅ 필수** |

## Gate 3: Submission Format 4 섹션 (모두 필수)

```markdown
## Final Output
[primary asset 위치 + 1줄 요약]

## QA Report Summary
- [ ] Requirement Alignment: PASS
- [ ] Functional Integrity: PASS
- [ ] Visual Evidence (또는 Logic Evidence): 3 items attached
- [ ] Zero-Defect Confirmation: PASS (edge cases: A, B, C)

## Verification Evidence 또는 Gallery
[세션 타입별 markdown 형식]

## Validation Statement
> [세션 타입별 정확 문장]
```

## Gate 4: 자동 BLOCK 조건

1개라도 미충족 시:
- `state/circuit-breaker.json` `perfect_output_fail` increment
- pdca-iterator 자동 재진입 (∀ unmet 항목)
- 5회 도달 시 사용자 에스컬

## Validation Statement (정확 문장)

```
VISUAL_INTERACTION:
"I have verified this deliverable through E2E QA and confirmed its integrity via the attached screenshots."

LOGIC_DATA:
"I have verified this deliverable through E2E QA and confirmed its integrity via unit tests, log analysis, and checksum verification."

혼합 세션 (두 세션 동시):
"I have verified this deliverable through E2E QA across both backend (unit tests, log analysis, checksum) and frontend (Playwright screenshots), confirming integrity end-to-end."
```

## /goal Evaluator 통합

Perfect Output Gate는 별도 종료 판정자가 아니라 **/goal evaluator에게 가시한 증거 생성자**. Gate 1-3가 위 4 섹션을 Claude transcript에 출력 → /goal evaluator (Haiku)가 active-goal condition과 매칭.

condition 예시:
```
"... 모든 unit test PASS, console error 0건. Verification Gallery 3장 첨부. Validation Statement 정확 문장 포함. or stop after 20 turns."
```

evaluator가 transcript에서 위 condition 충족 확인 → goal achieved → /goal 종료 → /auto 종료 → 사용자 보고.

## 관련

- `agents/verification/perfect-output-validator.md` — Gate 1
- `agents/verification/e2e-qa-prover.md` — Gate 2
- `lib/goal/goal_writer.py` — condition 생성
- Plan Section 5 — 전체 사양
