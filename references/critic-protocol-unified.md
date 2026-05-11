# Critic Protocol Unified (D2 + B) — 통일 schema + 5 기존 critic adapter

> **5원칙 매핑**: #2 자가개선 critic 사이클 강화 + 기존 워크플로우 그대로 유지
> **로드 시점**: critic agent 호출 직전 또는 verdict 산출 후 변환 시
> **외부 차용**: bkit Quality Gate(Match Rate >=90%) + superpowers Red Flag

## 1. 통일 schema (`critic_verdict_v1`) — 인라인 JSON 정의

```json
{
  "schema_version": "critic_verdict_v1",
  "critic_id": "compaction-critic | doc-critic | harness-critic | ...",
  "verdict": "APPROVE | REJECT | NEEDS_INFO",
  "weighted_score": 0-100,
  "confidence": "HIGH | MEDIUM | LOW",
  "risk_score": 1-5,
  "rationale": "string (1단락, 평가 근거)",
  "patch_proposal": "string | null",
  "retry_count": 0,
  "timestamp": "ISO 8601"
}
```

**필수 필드** (모든 critic): `verdict`, `confidence`, `rationale`, `timestamp`.
**조건부 필드**: `weighted_score` (가중 평가 시), `patch_proposal` (APPROVE 시), `retry_count` (NEEDS_INFO 누적 시).

## 2. 기존 5 critic 매핑 매트릭스 (본체 무수정)

기존 critic은 *본체 1줄도 안 건드림*. 대신 adapter 변환 규칙으로 통일 schema 호환.

| 기존 critic | 현 schema | 통일 후 매핑 | adapter 변환 규칙 |
|---|---|---|---|
| `embedded-critic` (PRD/Plan/Report) | `VERDICT`, `CONFIDENCE`, `RISK_SCORE`, `FEEDBACK` | 그대로 매핑 | verdict=VERDICT, confidence=CONFIDENCE, risk_score=RISK_SCORE, rationale=FEEDBACK |
| `doc-critic` (18세 일반인 기준) | 4-axis PASS/FAIL | verdict=PASS→APPROVE, FAIL→REJECT | confidence=HIGH (기본), weighted_score=PASS 비율*100 |
| `harness-critic` (외부 framework critic) | weighted 0-100 + verdict | **이미 정합** (변환 불필요) | 그대로 사용 |
| `phase-3 architect` (E2E 검증) | APPROVE / CONDITIONAL / REJECT | verdict 매핑 (CONDITIONAL→NEEDS_INFO) | weighted_score는 산출 (Match Rate 활용) |
| `self-evaluation-gate` (Phase -1.5 fit) | `GO / PROCEED / RECOMMEND` + fit_score | verdict 매핑 (GO→APPROVE, PROCEED→NEEDS_INFO, RECOMMEND→REJECT) | weighted_score=fit_score, confidence=HIGH/MEDIUM/LOW (fit_score 구간별) |

### Adapter 변환 — 실패 처리 (Critic agent 권고 흡수)

```
adapter_failed = True if:
  - 기존 critic 출력에 필수 필드 누락
  - 매핑 규칙 불일치
  - 형식 파싱 실패

if adapter_failed:
  # 원본 verdict 그대로 사용 (강제 통일 금지)
  log_telemetry("adapter_fallback", critic_id, raw_output)
  return raw_output as-is
```

→ adapter 실패가 critic 본체에 *전혀 영향 없음*. 통일 시도 실패해도 기존 워크플로우는 정상 작동.

## 3. 신규 `compaction-critic` (통일 schema 처음부터 준수)

- 위치: `agents/meta/compaction-critic.md`
- 모델: haiku (기본) / sonnet (HEAVY 모드)
- 입력: `compacted_context_v1` 산출물
- 출력: `critic_verdict_v1` 형식 (adapter 불필요)
- 5 IL check 검증 (compaction-gate L? 참조)

## 4. 무한 루프 방지 룰 (Critic agent 권고 흡수)

**HARD-GATE**: critic은 다른 critic의 출력을 검토하지 않는다.

```
적용 위치:
  - compaction-critic의 input ≠ harness-critic의 output
  - harness-critic의 input ≠ doc-critic의 output
  - phase-3 architect의 input ≠ self-evaluation-gate의 output

  → critic 산출물은 항상 *agent/executor/human*만 검토 가능
  → critic-to-critic chain 금지
```

**예외**: `harness-critic` → `harness-applier` chain은 *critic → executor* 패턴이라 OK.

## 5. Red Flag 섹션 (superpowers 차용)

다음 패턴은 즉시 STOP:

```
❌ 5 기존 critic의 schema/output을 *변경*하는 PR
   → 통일 schema는 신규 critic에만, 기존은 adapter layer만
❌ adapter 없이 통일 schema 강제 사용
   → 변환 실패 시 fallback 없으면 기존 워크플로우 break
❌ critic-to-critic chain 시도
   → §4 HARD-GATE 위반
❌ critic verdict를 다른 critic의 input으로 사용
   → 무한 루프 위험
❌ 통일 schema의 필수 필드 누락한 신규 critic
   → critic_verdict_v1 사용 의무 위반
```

## 6. Quality Gate (bkit 차용 — Match Rate ≥ 90%)

bkit-claude-code의 *Match Rate* 패턴을 critic verdict에 적용:

| critic 영역 | Quality threshold |
|---|---|
| compaction-critic | compaction_ratio in target range (§8 compaction-gate) |
| harness-critic | weighted_score ≥ 70 (APPROVE) |
| doc-critic | PASS 비율 ≥ 90% (4 axis 중 3.6+ PASS) |
| phase-3 architect | Match Rate ≥ 90% (Design vs Code) |
| embedded-critic | VERDICT == APPROVE AND RISK_SCORE ≤ 3 |
| self-evaluation-gate | fit_score ≥ 70 (GO) |

threshold 미달 시 REJECT 또는 NEEDS_INFO.

## 7. 사용자 진입점 보장

- adapter 변환은 *자율*. 사용자에게 묻지 않음.
- 변환 실패 시 fallback 자동 (사용자 진입점 0).
- 통일 schema 활용은 *내부 도구*용 (사용자가 직접 보지 않음).
- telemetry는 `state/critic-verdict-log.jsonl` (별도 hook 또는 critic agent가 append).

## 8. 재사용하는 기존 인프라

- `references/embedded-critic-protocol.md` — adapter 변환 규칙의 base template
- `hooks/circuit_breaker.py` — critic REJECT 누적 카운터
- 기존 5 critic agent 정의 — 본체 *0줄 수정*, 외부에서 adapter만 추가
