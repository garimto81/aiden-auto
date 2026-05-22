# chapter-quota-ops — HARNESS-OPS 카테고리 (v28.2 신규)

> **목적**: 쿼타 / 골 운영 흡수. /goal 메커니즘 기반 + advisor-tool API beta + Perfect Output Gate. (멀티세션 운영은 공식 `claude agents` CLI로 위임 — 2026-05-14 폐기)

## Use_When

- 사용자가 쿼타 상태 확인 / 강제 eco 모드 / goal 발화 / 진행률 조회 등 운영 의도 표명
- /auto 평문 트리거 중 plain_text_triggers에 매칭 (`쿼타 확인`, `goal로 돌려`, `완성될 때까지` 등)

## Do_Not_Use_When

- 일반 코드 구현 (CODE chapter)
- 문서 작성 (DOC chapter)
- 외부 framework 추적 (HARNESS chapter — harness-watcher/critic/applier 트리거)

## Phase Path

```
-2 Triage → 0 quota check → 4 Close
(1, 2, 3 skip — 운영 카테고리는 plan-build-verify 없음)
```

## Agent Team

| 역할 | Agent | 비고 |
|------|-------|------|
| 1차 쿼타 게이트 | `quota-executor` (haiku) | 3-질문 |
| 2차 쿼타 advisor | `quota-advisor` (sonnet + advisor-tool sub-inference opus 4.7) | 5-질문 정가중 |

## 통합 흐름 (Section 4 / Section 5 / Section 14 참조)

1. statusline 항상 표시 (cache 기반)
2. PreToolUse(Task) 시 quota-executor → 필요 시 quota-advisor 에스컬
3. 매 phase 전이 시 event_dispatcher가 events.jsonl append
4. Phase 4 close 시 Perfect Output Gate 4단 검증

## Lazy Load Sub-References

작업 진행 시 필요한 phase에서만 1개씩 로드:
- `references/quota-advisor-protocol.md` (Phase 0 quota 결정 시)
- `references/perfect-deliverable-protocol.md` (Phase 4 close 게이트)
- `references/adaptive-framework-protocol.md` (adapter 호출 시)

## Statusline 토큰 설명

```
[aiden-auto v28.2] 5h:40% (resets 03:00Z) | wk:11% | mode:default | CB:0/3 | quota:OK | goal:active | sessions:3A
```

| 토큰 | 의미 |
|------|------|
| `5h:XX%` | 5시간 사용량 |
| `wk:XX%` | 주간 사용량 |
| `mode:default\|eco\|eco-2\|eco-3` | 활성 eco 모드 (quota-advisor가 자동 조정) |
| `CB:N/3` | architect_reject 카운터 / hard limit |
| `quota:OK\|WATCH\|DOWNGRADE\|DEFER\|STALE` | quota_band (usage_reader 산출) |
| `goal:active\|none\|reached` | active-goal.json 상태 |
| `sessions:NA\|NA!` | 활성 세션 N개 + Agent View 활성 (`!` = conflict) |

## 보안 / Circuit Breaker

- Rule 17 카운터 영향: `quota_downgrade` (hard limit 5/session, 신규)
- /goal 안전절 자동 첨가: `or stop after 20 turns, or stop after 200k tokens` (goal_writer.py)
- HMAC 서명: 모든 event payload에 SHA256 서명 (`.hmac-secret`)

## 종료 보고 의무 (v28.2 Section 16)

HARNESS-OPS chapter의 모든 종료 보고는 **`user-friendly-reporter` agent 통과 의무** (Phase 4 close Gate 5). 비개발자 사용자가 결과를 한 번에 이해할 수 있도록 친절하고 자세히 풀어 설명.

규칙 준수:
- 약어·전문용어 첫 등장 시 무조건 풀이 (`quota`, `advisor`, `session` 등)
- 핵심 개념마다 일상 비유 1개 (도서관/집/식당/요리)
- 단계별 설명 (1단계, 2단계 ...)
- 모든 작업·결정에 "왜?" 1-2줄
- 길이 제한 없음 (자세히 풀어 설명)

자세한 사양: `references/user-friendly-report-protocol.md`

---

> 본 chapter는 lazy-load 진입점. 상세 사양은 sub-references 참조. SKILL.md (≤120줄) 무수정.
