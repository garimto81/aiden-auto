# Claude Code OAuth Advisor Protocol — verdict schema + 로깅 포맷

> **5원칙 매핑**: #2 자가개선 critic 사이클 강화 — Anthropic 공식 advisor-tool 패턴 차용
> **로드 시점**: cc-auth-executor / cc-auth-advisor / hooks/cc_auth_check.py 모두 본 문서를 단일 소스로 참조
> **출처**: [Anthropic advisor-tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/advisor-tool)

---

## 1. 핵심 매핑 (advisor-tool → Claude Code OAuth)

advisor-tool의 **"Executor-Advisor 2-tier" 패턴**을 OAuth 토큰 점검 흐름으로 차용:

| advisor-tool (API) | 본 protocol (auth 컨텍스트) |
|---|---|
| Executor 모델 (Sonnet/Haiku) | `cc-auth-executor` (haiku, 매 SessionStart) |
| server_tool_use(name="advisor") | executor의 escalate 결정 (3-질문 중 1개라도 YES) |
| Advisor 모델 (Opus) | `cc-auth-advisor` (opus, READ-ONLY) |
| advisor_tool_result 블록 | verdict 4종 + rationale |
| Executor 재개 | hook output (systemMessage / additionalContext / exit code) |
| usage.iterations[] 분리 청구 | `state/cc-auth-decisions-{date}.json` 모델별 분리 로깅 |

---

## 2. verdict 4종 (cc_auth_verdict_v1 schema)

```json
{
  "schema_version": "cc_auth_verdict_v1",
  "verdict": "AUTO_REFRESH | PROMPT_USER | BLOCK | DEFER",
  "weighted_score": 0-100,
  "confidence": "HIGH | MEDIUM | LOW",
  "rationale": "string (1단락, 평가 근거)",
  "scores_per_question": [int, ...],
  "tier": "executor | advisor",
  "access_token_hash": "16-char sha256 prefix (평문 토큰 절대 X)",
  "timestamp": "ISO 8601"
}
```

### verdict 정의

| Verdict | 조건 | 액션 | exit code | stdout |
|---|---|---|:---:|---|
| `AUTO_REFRESH` | 만료 임박만, refreshToken 정상, 패턴 정상 | no-op (Claude Code 자체 refresh에 위임) | 0 | (빈 출력) |
| `PROMPT_USER` | scope 변화 감지 또는 refreshToken 의심 신호 | 사용자에게 1줄 알림 | 0 | `{"systemMessage": "Claude Code 재인증 권장: claude login"}` |
| `BLOCK` | 401 누적 ≥3회/24h 또는 rateLimitTier 강등 | 세션 차단 + 사유 표시 | 2 | `{"reason": "..."}` |
| `DEFER` | idle 패턴, 인증 의존 작업 0건 예상 | 다음 세션 유예 (no-op) | 0 | (빈 출력) |

### critic_verdict_v1과의 alias

본 protocol은 `references/critic-protocol-unified.md`의 `critic_verdict_v1`과 호환을 위해 alias 제공:

| cc-auth verdict | critic_verdict_v1 alias |
|---|---|
| `AUTO_REFRESH` | `APPROVE` |
| `PROMPT_USER` | `NEEDS_INFO` |
| `BLOCK` | `REJECT` |
| `DEFER` | `NEEDS_INFO` (latency 회피 케이스) |

adapter 변환: cc-auth-advisor 산출물을 다른 critic 시스템(harness-watcher 등)이 흡수할 때 alias 사용.

---

## 3. Executor 3-질문 (1차 게이트)

cc-auth-executor (haiku)는 다음 3개 신호만 빠르게 체크 (≤100ms 목표):

| # | 질문 | 평가 방법 |
|:-:|------|----------|
| 1 | `expiresAt - now < 24h`? | timestamp 비교 (단순 산술) |
| 2 | `scopes`가 직전 세션 대비 변경되었는가? | 직전 snapshot과 set 비교 |
| 3 | 최근 401 누적이 ≥3회/24h? | `state/cc-auth-failures-{date}.json` 카운트 |

### Executor 결정 룰

```
signals = {
  near_expiry: Q1,
  scopes_changed: Q2,
  failure_burst: Q3,
}

if all(signals.values()) == False:
  # 모두 NO → 안전 통과
  verdict = None  # advisor 미호출, no-op
  return (escalate=False, verdict=None)

if signals == {near_expiry: True, scopes_changed: False, failure_burst: False}:
  # 만료 임박 단일 신호 → executor 직접 AUTO_REFRESH (advisor 미호출, 비용 절감)
  verdict = AUTO_REFRESH
  return (escalate=False, verdict=AUTO_REFRESH)

# 그 외 (모호/위험) → advisor escalate
return (escalate=True, verdict=None)
```

> **비용 절감 원칙**: advisor-tool의 "필요 시에만 escalate" 정신을 유지. 단일 안전 신호(near_expiry만)는 executor가 직접 결론.

---

## 4. Advisor 5-질문 정가중 (2차 escalate)

cc-auth-advisor (opus, READ-ONLY)는 다음 5질문으로 정가중 평가:

| # | 질문 | 가중치 | 평가 0-10 기준 |
|:-:|------|:------:|---------------|
| 1 | 토큰 만료가 24h 이내인가? | 25% | 0=만료 1주+ / 5=24h~48h / 10=1h 이내 |
| 2 | `scopes` 변화의 의도가 명확한가? | 20% | 0=변화 없음 / 5=알려진 scope 추가 / 10=알려지지 않은 scope |
| 3 | 최근 401 패턴이 보안 위협인가? | 25% | 0=실패 0 / 5=401 1-2회 / 10=401 ≥3회/24h |
| 4 | `rateLimitTier` 강등 신호가 있는가? | 15% | 0=tier 동일 / 5=tier 강등 가능성 / 10=확정 강등 |
| 5 | 사용자 작업 컨텍스트가 인증 의존인가? | 15% | 0=read-only / 5=mixed / 10=API 호출 집약 |

`weighted_score = Σ (score_i × weight_i)`

### Security Floor (필수)

Q3(401 패턴) 또는 Q4(rateLimitTier 강등) 점수가 **≥7** 이면 다른 신호와 무관하게 critical:

```
if score_3 >= 7 or score_4 >= 7:
    weighted_score = max(weighted_score, 70)
```

이유: 보안 위협 단일 신호도 critical로 분류해야 안전. 가중치 합산만으로는 다른 신호 0점이 critical을 희석하는 문제 방지.

### Verdict 결정

| weighted_score | verdict |
|:--:|---|
| ≥70 | `BLOCK` 또는 `PROMPT_USER` (질문 3·4 가중치 큰 경우 BLOCK) |
| 50–69 | `PROMPT_USER` |
| 30–49 | `AUTO_REFRESH` |
| <30 | `DEFER` |

세부 분기는 advisor가 rationale에 명시.

---

## 5. 로깅 schema (`state/cc-auth-decisions-{date}.json`)

매 SessionStart마다 append. JSON 객체 (배열 아님):

```json
{
  "schema_version": "cc_auth_decisions_v1",
  "decisions": [
    {
      "schema_version": "cc_auth_verdict_v1",
      "verdict": "AUTO_REFRESH",
      "tier": "executor",
      "weighted_score": null,
      "confidence": "HIGH",
      "rationale": "single near_expiry signal only",
      "scores_per_question": null,
      "access_token_hash": "a3f2e1b4c5d6f7a8",
      "timestamp": "2026-05-12T10:00:00Z"
    },
    ...
  ]
}
```

### 보안 룰

- ❌ `accessToken`, `refreshToken` **평문 절대 X**
- ❌ `scopes` 배열 평문도 회피 (해시 또는 변화 여부만)
- ✅ `access_token_hash`: SHA256 16자 prefix만
- ✅ timestamp는 UTC ISO 8601

---

## 6. harness-watcher 통합 (자가개선 사이클)

`references/external-harness-registry.md`의 `internal_advisors` 섹션에 본 advisor 등록. harness-watcher가 daily 실행 시 추세 분석:

| 빈도 임계값 | 조치 |
|---|---|
| `PROMPT_USER` ≥ 3회/주 | "scope 사전 등록 권고" issue 자동 생성 |
| `BLOCK` ≥ 1회/주 | "rate limit / 보안 점검 권고" issue 자동 생성 |
| `AUTO_REFRESH` 빈도 추세 | metric만 누적 (정상) |

---

## 7. Anti-patterns

- ❌ executor가 advisor 미호출 상태에서 BLOCK 결정 — 보수적 결정은 advisor 영역
- ❌ advisor가 `accessToken` 평문 접근 — 해시만 + 메타데이터만
- ❌ verdict별 stdout 포맷 임의 변경 — hook output schema 고정 (§2 표)
- ❌ critic_verdict_v1 alias 누락 — 다른 시스템과 호환성 깨짐
- ❌ Claude Code 자체 refresh와 race condition — AUTO_REFRESH는 항상 no-op

---

## 8. 5원칙 정합성

- #2 (자가개선 critic 사이클): ✅ 6번째 advisor로 본 protocol 등록 — harness-watcher 자동 추세 추적
- #4 (자가개선 사이클): ✅ executor → advisor → 자동 로깅 → 추세 → issue
- Core Philosophy (사용자 진입점 최소화): ✅ AUTO_REFRESH/DEFER는 사용자 노출 0, PROMPT_USER만 1줄
