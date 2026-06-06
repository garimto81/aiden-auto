# root-cause iteration-1 — 분석

테스트 3종 × (with-skill / baseline) = 6 run. baseline = 스킬 없음 (둘 다 sonnet).

## 결과 요약

| 케이스 | with-skill | baseline | 판정 |
|--------|-----------|----------|------|
| codebug | 분류→원인(빈 장부 비유)→근거표→수정제안(적용X)→모르는점. 수정안 실제 실행 검증 | 정답 동일, 단 3개 방법 코드 나열 + jargon(딕셔너리/`{}`) + '적용X' 프레이밍 없음 | with-skill: 구조·말투·규율 우위 |
| framework | framework 분류→sync 체인 추적→비유 다이어그램→Critical Unknowns 정직 | 정답 동일, log 증거(commit failed/no changes)까지 더 깊이 파냄, 단 15세 프레이밍 약함 | 무승부 (skill=친화, baseline=진단 깊이) |
| ambiguous | "단정 불가" 명시→후보 3 표→모르는점 표(필요 정보)→롤백 제안→"/debug가 수정 담당" 경계 | 동일하게 불확실성 존중, 후보 6개로 더 exhaustive, 더 길다 | 무승부 (둘 다 추측 단정 안 함) |

## 핵심 통찰

- baseline(sonnet)이 이미 강함 → 스킬의 가치는 "더 똑똑한 조사"가 아니라 **일관성 + 규율 + 말투**:
  1. 보고서 구조 강제 (TL;DR / 비유 / 근거표 / 모르는점) — ad-hoc 방지
  2. "수정은 제안만, 적용 안 함" 규율 — baseline은 이 프레이밍 누락
  3. 평이한 말투 강제 — baseline은 jargon 으로 드리프트
  4. `/debug`와 역할 경계 명시
- 이는 설계 의도(얇은 오케스트레이터, READ-ONLY, 15세 보고서)와 정확히 일치 → 스킬 건전.

## 관찰된 비-결함

- subagent 파일 쓰기 차단 = 하니스 정책(결과는 텍스트 반환). eval 설정 artifact일 뿐 스킬 결함 아님. 실사용은 Lead가 chat에 보고서 조립 → 무관.
- framework with-skill이 baseline보다 log를 덜 팜 = tracer를 실제 spawn 안 하고 inline 실행해서. 실사용(Lead가 tracer 실제 호출)에선 해소. 스킬 본문 수정 불요.

## 결론

iteration-1 통과. 스킬 본문 수정 없이 finalize 권장. (선택: description 트리거 정확도 최적화)
