# Tool Integration — 자체 도구 자동 통합

> **로딩 시점**: Phase 3 VERIFY 진입 시 (Phase -1의 `tools_registry` 비어있지 않을 때만).
> **의존**: `references/phase-minus-1-context-detect.md` 의 `tools_registry` 필드.
> **목적**: 프로젝트 자체 검증 도구를 일반 qa-tester 대신 우선 사용.

---

## 동작 원리

Phase -1에서 `tools_registry` 채워졌다면 Phase 3 VERIFY 진입 시:

```
IF tools_registry is empty:
  → 일반 qa-tester (현재 v25.6 동작)
ELSE:
  → tool-augmented qa-tester
    - 발견된 모든 tools_registry 도구 자동 실행
    - 결과를 /auto 의 gap % 측정 대신 사용
    - kpi role 도구 결과로 success/fail 판정
```

## qa-tester prompt 패치 (tool 모드)

기존 qa-tester가 도구를 의식하도록 prompt 변경:

```python
Agent(
  subagent_type="qa-tester",
  name="check-qa-with-tools",
  description="[PDCA Check] 자체 도구 + 일반 검증",
  team_name="auto-{feature}",
  model="sonnet",
  prompt=f"""구현 결과의 기술 검증 + 자체 도구 활용:

1. 표준 검증 (현재 동작):
   - pytest/jest 테스트 통과
   - 린트 에러 0건
   - 빌드 성공

2. 프로젝트 자체 도구 (Phase -1 발견됨):
   {tools_registry_yaml}

   각 도구 실행 → 결과 수집:
   - drift_check role: drift_count → 0이면 PASS
   - kpi role: 점수/percent → target과 비교
   - lint role: 에러 0이면 PASS
   - test role: 테스트 통과
   - build role: 빌드 성공

3. 결과 종합:
   - 모든 표준 + 자체 도구 PASS → /auto gap % 100%로 매핑
   - 일부 FAIL → FAIL 항목 + 자체 도구 결과 모두 출력
   - 자체 도구의 KPI 결과는 architect의 gap 판정 대체

출력: PASS/FAIL + 표준 검증 결과 + 자체 도구별 결과 표"""
)
```

## tools_registry 실행 패턴

### Pattern 1: drift_check role

```bash
# 예시: ebs spec_drift_check
python tools/spec_drift_check.py --all --format=json > /tmp/drift.json

# 결과 parsing
DRIFT_COUNT=$(cat /tmp/drift.json | python -c "
import json, sys
data = json.load(sys.stdin)
print(sum(len(v.get('items', [])) for v in data.values()))
")

# 판정
if [ "$DRIFT_COUNT" -eq 0 ]; then
  echo "drift_check: PASS"
else
  echo "drift_check: FAIL ($DRIFT_COUNT items)"
fi
```

### Pattern 2: kpi role

```bash
# 예시: ebs reimplementability
python tools/reimplementability_audit.py > /tmp/kpi.txt

# parsing (markdown table)
PASS_PCT=$(grep "PASS" /tmp/kpi.txt | grep -oE "[0-9]+%" | tr -d '%')

# 판정 (target ≥ 90%)
if [ "$PASS_PCT" -ge 90 ]; then
  echo "reimplementability: PASS ($PASS_PCT%)"
else
  echo "reimplementability: FAIL ($PASS_PCT% < 90%)"
fi
```

### Pattern 3: lint role

```bash
# 예시: ruff
ruff check src/ --output-format=json > /tmp/lint.json

ERROR_COUNT=$(cat /tmp/lint.json | python -c "
import json, sys
print(len(json.load(sys.stdin)))
")

[ "$ERROR_COUNT" -eq 0 ] && echo "lint: PASS" || echo "lint: FAIL ($ERROR_COUNT errors)"
```

### Pattern 4: test role

```bash
# 예시: pytest
pytest tests/ --json-report --json-report-file=/tmp/test.json

PASSED=$(cat /tmp/test.json | python -c "
import json, sys
print(json.load(sys.stdin)['summary'].get('passed', 0))
")
FAILED=$(cat /tmp/test.json | python -c "
import json, sys
print(json.load(sys.stdin)['summary'].get('failed', 0))
")

[ "$FAILED" -eq 0 ] && echo "test: PASS ($PASSED tests)" || echo "test: FAIL ($FAILED failures)"
```

## architect의 gap % 대체

Phase 3 Step 0.4b (architect gap 판정) 에서 자체 KPI 우선:

```
IF tools_registry has kpi role tool:
  /auto gap % = kpi role tool 결과
  Architect 판정:
    kpi PASS → APPROVE
    kpi FAIL → REJECT (rejection_reason = kpi 결과)
ELSE:
  현재 v25.6 architect gap % 동작
```

이렇게 하면 ebs 같은 프로젝트에서 `/auto`의 gap %가 무의미한 일반 measurement이 아니라 **프로젝트가 신경 쓰는 reimplementability_pass_rate** 값을 사용.

## 통합 검증 결과 출력

Phase 3 완료 시 형식:

```
═══ Phase 3: VERIFY 결과 ═══
표준 검증:
  - pytest:    PASS (45 tests)
  - lint:      PASS (0 errors)
  - build:     PASS

자체 도구 (Phase -1 발견):
  - spec_drift_check:        PASS (0 drift)
  - reimplementability_audit: PASS (92%)
  - lighthouse:              PASS (95)

종합: PASS → Phase 4 CLOSE 진입
═════════════════════════════
```

또는 FAIL 시:

```
═══ Phase 3: VERIFY 결과 ═══
...
자체 도구:
  - reimplementability_audit: FAIL (70% < 90%)
    └─ MISSING 20건 + UNKNOWN 11건

종합: FAIL → Phase 0.5 Case 1 (gap-fixer) 진입
       (reimplementability_audit 결과를 prompt에 전달)
═════════════════════════════
```

## 자동 도구 미발견 시 fallback

Phase -1에서 `tools_registry`가 비어있는 경우 (신규 프로젝트, generic):
- 현재 v25.6 동작 유지 (qa-tester 일반 검증만)
- architect가 일반 gap % 측정

이 경우 본 reference는 로딩되지 않음 (선택적 lazy load).

## 호환성

| 시나리오 | tools_registry 상태 | /auto 동작 |
|---------|---------------------|-----------|
| 신규 프로젝트 (없음) | empty | 현재 v25.6 그대로 |
| ebs 같은 성숙 프로젝트 | drift + kpi 가득 | tool-augmented qa-tester + KPI 대체 |
| React 표준 | lint + test + build + lighthouse | tool-augmented qa-tester (lighthouse를 KPI로) |
| Python CLI | ruff + pytest | tool-augmented qa-tester (coverage를 KPI로) |

## 본 통합의 핵심 가치

`/auto`가 프로젝트 무관 표준 검증만 하지 않고, **프로젝트가 이미 가지고 있는 검증 인프라를 존중하고 활용**. 이는 직전 critic 보고서의 R2 (자체 도구 인식 부재) 해결.
