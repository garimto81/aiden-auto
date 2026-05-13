# TDD 규칙

**테스트 먼저 작성 (Red → Green → Refactor)**

| 단계 | 설명 | 예상 결과 |
|------|------|----------|
| **Red** | 실패하는 테스트 먼저 작성 | 테스트 실패 |
| **Green** | 테스트 통과하는 최소 코드 작성 | 테스트 통과 |
| **Refactor** | 코드 개선 (테스트 유지) | 테스트 통과 |

**워크플로우**: 테스트 작성 → `pytest -v` (FAIL) → 최소 구현 → (PASS) → 리팩토링 → (PASS 유지)

**파일 명명**: pytest `test_*.py` / Jest `*.test.ts` 또는 `*.spec.ts`

## 강제 수단

- Hook: `session_init.py` (경고), `post_edit_check.js` (편집 후 검증)
- 스킬: `/tdd` 강제 TDD 모드
