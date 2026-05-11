# Compaction Gate (D1) — 조건부 토큰 절약 layer

> **5원칙 매핑**: #3 SKILL.md 최소 + #5 슈퍼앱 가치 유지 + 실제 lazy load 실현
> **로드 시점**: phase 진입 직전 (`gate_active` 판정 시만)
> **외부 차용**: bkit Context Anchor + Anthropic `effort.level` + superpowers HARD-GATE/Iron Law/Red Flag

## 1. 발동 조건 (HARD-GATE — superpowers 차용)

```
gate_active = (complexity_score >= 4) OR (expected_load > 15KB) OR (effort_level == "high")
```

trivial 작업 (score 1-3 AND load < 15KB AND effort != high) → gate **비발동**, 기존 lazy load 그대로.

3중 게이트 중 *하나라도* 충족하면 발동. 의미적으로:
- **score >= 4**: 복잡한 작업 (architectural 변경, 다중 모듈)
- **load > 15KB**: 큰 reference 진입 예정 (예: phase-1-plan.md 39KB)
- **effort_level == "high"**: 사용자 명시 의도 신호 (Anthropic v2.1.133+ 표준)

## 2. 4-tap pattern (조건부 작동)

| Tap | 시점 | 동작 |
|:---:|------|------|
| **T1** Pre-Phase Entry | 각 phase 진입 *직전* | `gate_active` 판정. 비발동 시 즉시 통과 |
| **T2** Post-Reference Read | reference 파일 Read 직후 | Selective Slice (§3 매핑 사용) |
| **T3** Inter-Phase Handoff | Contract JSON 직렬화 직전 | 현재 phase 미사용 필드 strip |
| **T4** Token Threshold | usage 60/75/90% 도달 시 | 대화 context summary (별도 hook) |

T2가 핵심 — 가장 비싼 3개 파일을 *현장에서* selective slice.

## 3. Selective Slice 매핑 (인라인 — 별도 JSON 안 만듦)

원본 reference 파일 *수정 없이*, gate가 메모리에서 *읽은 직후* 섹션만 추출.

### 3.1 `phase-1-plan.md` (870줄, 39KB)

```yaml
sections:
  S1_socratic:    {range: "L1-L60",    scope: ["ambiguity>=0.5"]}
  S2_prd:         {range: "L60-L200",  scope: ["!skip-prd"]}
  S3_analysis:    {range: "L200-L300", scope: ["!skip-analysis"]}
  S4_plan_light:  {range: "L300-L380", scope: ["LIGHT", "STANDARD", "HEAVY"]}  # 필수
  S5_critic_lite: {range: "L380-L450", scope: ["STANDARD", "HEAVY"]}
  S6_critic_loop: {range: "L450-L600", scope: ["HEAVY"]}
  S7_gate:        {range: "L600-L705", scope: ["STANDARD", "HEAVY"]}
  S8_extras:      {range: "L705-L870", scope: ["HEAVY"]}
```

LIGHT + --skip-prd + ambiguity<0.5 → **S4만 inject (~80줄, 86% 절감)**.

### 3.2 `common.md` (524줄, 22KB)

```yaml
sections:
  init_contract: {range: "L1-L100"}    # Phase 0 진입 시만
  plan_contract: {range: "L100-L200"}  # Phase 1 진입 시만
  build_contract:{range: "L200-L300"}  # Phase 2 진입 시만
  verify_contract:{range: "L300-L400"} # Phase 3 진입 시만
  close_contract:{range: "L400-L524"}  # Phase 4 진입 시만
```

각 phase 진입 시 *해당 Contract 1종만* inject (~5KB, **77% 절감**).

### 3.3 `options-handlers.md` (691줄, 28KB)

```yaml
sections:
  "--mockup":    {range: "L37-L120"}
  "--anno":      {range: "L120-L180"}
  "--critic":    {range: "L180-L240"}
  "--debate":    {range: "L240-L300"}
  "--research":  {range: "L300-L360"}
  "--daily":     {range: "L360-L420"}
  "--slack":     {range: "L420-L480"}
  "--gmail":     {range: "L480-L540"}
  "--con":       {range: "L540-L600"}
  "--jira":      {range: "L600-L660"}
  "--figma":     {range: "L660-L691"}
```

사용 옵션 1-2개 평균 → **~85-90% 절감**.

## 4. `compacted_context_v1` 산출물 schema (인라인 정의)

```json
{
  "schema_version": "compacted_context_v1",
  "phase": "1 | 2 | 3 | 4",
  "mode": "LIGHT | STANDARD | HEAVY",
  "complexity_score": 0-10,
  "effort_level": "low | medium | high",
  "context_anchor": {
    "WHY": "이 작업이 필요한 사유 (1줄)",
    "WHO": "주 사용자/이해관계자",
    "RISK": "주요 위험 요소",
    "SUCCESS": "성공 기준",
    "SCOPE": "포함/제외 범위"
  },
  "source_refs": [
    {
      "path": "references/phase-1-plan.md",
      "sections_loaded": ["S4_plan_light"],
      "original_bytes": 40410,
      "compacted_bytes": 5800,
      "ratio": 0.143
    }
  ],
  "prior_phase_summary": "string (max 500 tokens)",
  "contract_in": {"<stripped Contract>": "..."},
  "options_active": ["--eco-2"],
  "compaction_budget": {"phase_max_tokens": 6000, "actual_tokens": 5840},
  "telemetry": {"saved_bytes": 32610, "saved_pct": 80.7}
}
```

**Context Anchor 5 필드는 모든 phase에서 보존 (bkit 차용 — WHY/WHO/RISK/SUCCESS/SCOPE)**.

## 5. `effort.level` 통합 (Anthropic v2.1.133+ 차용)

hook 입력에서 `effort.level` 또는 `$CLAUDE_EFFORT` 환경변수 읽기:

| effort.level | Selective Slice 깊이 | T4 threshold |
|:------------:|---------------------|:------------:|
| `low` | 최소 섹션만 (S4만 등) | 90% |
| `medium` (기본) | LIGHT/STANDARD 섹션 | 75% |
| `high` | 모든 섹션 + 추가 압축 | 60% |

신호 미지원 환경 (구버전 CC CLI) → effort 무시, score+load만 사용.

## 6. Red Flag 섹션 (superpowers 차용)

다음 패턴은 즉시 STOP:

```
❌ "그냥 phase-1-plan.md 전체 inject" → 70% 토큰 낭비. Selective Slice 강제.
❌ "compaction 결과를 또 compaction" → 무한 루프. critic-protocol-unified L? 룰 위반.
❌ "Iron Laws 5개 중 하나라도 누락" → 즉시 RAW_FALLBACK (압축 포기, 원본 사용).
❌ "Context Anchor 5 필드 빠뜨림" → REJECT 후 retry.
❌ "trivial 작업에 gate 강제 발동" → 사용자 진입점 증가, Core Philosophy 위반.
❌ "compaction-gate가 critic 출력을 검토" → 무한 critic 루프 (critic-protocol L? 룰).
```

## 7. Iron Laws (compaction 영역, 5개)

compaction-critic이 검증할 5가지:

| IL | 이름 | 확인 |
|:--:|------|------|
| **IL1** | `essential_fields_present` | source_refs, contract_in, phase, mode 모두 존재 |
| **IL2** | `scope_match_active_mode` | LIGHT 모드에 HEAVY 전용 섹션 포함되지 않음 |
| **IL3** | `no_hallucinated_content` | compacted 내용이 source 줄범위에 실재 |
| **IL4** | `context_anchor_preserved` | WHY/WHO/RISK/SUCCESS/SCOPE 5 필드 모두 존재 |
| **IL5** | `compaction_ratio_in_range` | target 범위 (mode별, §8) |

## 8. 복잡도 → Compact Strategy 매핑 (eco 결합)

| score (5점) | score (10점) | mode | compact 빈도 | ratio target | budget |
|:-----------:|:------------:|:----:|:------------:|:------------:|:------:|
| 0-1 | 0-3 | LIGHT | T2만 (phase당 1회) | 0.10 - 0.20 | 3000 tok |
| 2-3 | 4-6 | STANDARD | T2 + T3 (2회) | 0.20 - 0.35 | 6000 tok |
| 4-6 | 7-10 | HEAVY | T1+T2+T3 + T4 threshold | 0.30 - 0.50 | 10000 tok |

**eco 결합**:

| mode × eco | budget | compaction-critic 모델 |
|------------|:------:|:----------------------:|
| LIGHT × (기본) | 3000 | haiku |
| LIGHT × --eco-3 | 1500 | haiku |
| STANDARD × --eco | 4500 | haiku |
| HEAVY × (기본) | 10000 | sonnet |
| HEAVY × --eco-2 | 5000 | sonnet |

## 9. REJECT 처리 (Circuit Breaker)

compaction-critic verdict가 REJECT인 경우:

```
1차 REJECT  → 다른 selective slice 시도 (1회 재시도)
2차 REJECT  → RAW_FALLBACK (원본 reference 사용 + telemetry에 기록)
3차 REJECT  → Circuit Breaker 발동 (hooks/circuit_breaker.py 재사용)
              → 사용자 escalation + gate 임시 비활성
```

## 10. 사용자 진입점 보장 (Core Philosophy)

- gate 발동은 *자율*. 사용자에게 묻지 않음.
- REJECT 누적 시만 사용자 보고 (1줄 stderr).
- 평소엔 *통계 telemetry*만 (`state/compaction-telemetry.jsonl`).
- Red Flag는 *Claude 자기 규제*용. 사용자 진입점 0 증가.

## 11. 재사용하는 기존 인프라

- `hooks/pre_compact_save.py` — 저장 시점 인프라
- `hooks/recovery/context_limit_recovery.py` — 90% 도달 시 경고
- `hooks/circuit_breaker.py` — REJECT 누적 카운터
- `references/adaptive-phase-selection.md` — complexity_score 입력
- `references/embedded-critic-protocol.md` — compaction-critic의 base template
