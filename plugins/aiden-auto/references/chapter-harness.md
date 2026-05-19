# Chapter: HARNESS (C 영역 진입점) — v28.4 갱신 2026-05-19

> **5원칙 매핑**: #2 자가개선 매일 사이클 + #4 Intent→Chapter 라우팅
> **트리거**: 평문 "harness 상태" / "harness 체크" / "외부 framework 업데이트" / "watcher"
> **외부 차용**: superpowers HARD-GATE + Red Flag
> **v28.4 (2026-05-19)**: superpowers 12 skill 매트릭스 통합. `references/external-harness-registry.md` "v28.4 신규: superpowers 12 skill 매트릭스" 섹션 참조. Deep Interview brainstorming 위임 정합.

## 1. 진입 흐름

```
사용자 평문 트리거
       │
       ▼
┌─────────────────────────────────┐
│ Step 1: harness-status.md 로드   │
│  현재 상태 한 페이지 표시          │
│  · 최근 watcher run timestamp    │
│  · Pending flags 목록            │
│  · 최근 PR / 통계                │
│  · D3 KPI (축소 사이클)          │
└─────────────┬───────────────────┘
              │
              ▼
┌─────────────────────────────────┐
│ Step 2: 사용자 의도 분기 (자율)   │
│  "상태만"     → 보고 후 Phase 4   │
│  "watcher 실행" → harness-watcher │
│  "신규 등록"  → critic+applier   │
│  "축소 검토"  → D3 sub-step      │
└─────────────┬───────────────────┘
              │
              ▼
       Phase 4 Close
```

## 2. 진입 트리거 (`index.yml` plain_text_triggers)

활성 키워드:
- "harness 상태"
- "harness 체크"
- "외부 framework 업데이트"
- "watcher 실행"
- "외부 framework 상태"

비활성 (단순 조회):
- "harness가 뭐야" (단순 질문 — chapter 진입 안 함)

## 3. Step 2 의도 분기 세부

### 3.1 "상태만" 분기 (가장 빈번)
- harness-status.md 그대로 보고
- 추가 작업 없이 Phase 4 Close
- 토큰 비용: ~80줄 reference 1개만 (~3KB)

### 3.2 "watcher 실행" 분기
```
Agent(
  subagent_type="harness-watcher",
  model=plan["harness-watcher"],
  description="외부 6 framework update 체크",
  prompt="effort.level={감지된 신호}, 모든 framework 1회 체크"
)
```
→ `state/harness-updates-{date}.json` 생성. 신규 update 있으면 critic-pending flag 자동.

### 3.3 "신규 등록" 분기 (B 영역 — auto-discover)
사용자가 monorepo 발견 결과 등록 요청 시:
```
1. Read state/harness-discoveries-{latest}.json
2. critic prescreen score ≥ 50 후보만 노출
3. 사용자가 N개 선택 → registry에 batch 등록
4. 등록 직후 watcher 재실행으로 baseline 수립
```

### 3.4 "축소 검토" 분기 (D3 영역)
```
1. live references/ 디렉토리 스캔 (총 KB)
2. baseline (v28.2 시점) 대비 ratio 계산
3. archive vs live diff로 inert reference 후보 검출
4. critic 5질문 평가 후 사용자 보고 (이주 옵트인)
```

## 4. Context Anchor (bkit 차용 — 모든 chapter 공통)

HARNESS chapter 진입 시 자동 채워질 anchor:
- **WHY**: "외부 framework 변화 추적 + 자가개선 (5원칙 #2)"
- **WHO**: "사용자 (review/merge) + Claude (자율 사이클)"
- **RISK**: "외부 framework 의존성 변화 / API rate limit / owner 이전"
- **SUCCESS**: "신규 update 자동 critic + applier PR / KPI 80% 도달"
- **SCOPE**: "registered 6 framework + auto-discovered 후보 / 코드 *복사 금지*, 참조만"

## 5. Red Flag (superpowers 차용)

다음 패턴은 즉시 STOP:

```
❌ HARNESS chapter에서 외부 framework 코드 *복사* 시도
   → 5원칙 #1 위반 ("그대로 유지, 참조만")

❌ harness-applier 결과를 main 직접 push
   → 사용자 PR review 필수 (CI/CD 안전망)

❌ critic 평가 없이 신규 plugin registry 자동 등록
   → 사용자 옵트인 의무

❌ watcher 일 1회 미만 실행
   → 자가개선 사이클 약화 (5원칙 #2 위반)

❌ 축소 사이클에서 *active reference*를 archive로 이주
   → 데이터 손실. critic 5질문 + 사용자 옵트인 필수
```

## 6. HARD-GATE (superpowers 차용)

다음 조건 모두 충족 시만 chapter 발동:
- `gate_active = (트리거 매칭) AND (실행 권한 있음)`
- 단순 질문 ("harness가 뭐야") → 비발동, Phase 4 즉시 Close

## 7. Phase 4 Close 산출물

- `harness-status.md` 갱신 (watcher 실행한 경우)
- `state/harness-{action}-{date}.json` (action별)
- 사용자에게 1줄 보고:
  ```
  ✅ Harness {action} 완료
     - {N}건 처리
     - {M}개 pending → next: {agent}
     - 상세: state/harness-{action}-{date}.json
  ```

## 8. 재사용 인프라

- `references/external-harness-registry.md` — framework 메타데이터
- `agents/meta/harness-watcher.md` — 매일 사이클
- `agents/meta/harness-critic.md` — 5질문 평가
- `agents/meta/harness-applier.md` — patch + PR
- `agents/meta/cc-version-researcher.md` — claude-code 심층 분석 (chain)
- `hooks/circuit_breaker.py` — REJECT 누적

## 9. 5원칙 정합성

- #1 외부 framework 그대로 유지: ✅ 코드 복사 0, 참조만
- #2 매일 critic 자가개선: ✅ 본 chapter가 사이클 진입점
- #3 SKILL.md 최소: ✅ SKILL.md 직접 영향 없음, chapter 1개 추가만
- #4 Intent → Chapter: ✅ HARNESS 카테고리 자체가 routing
- #5 슈퍼앱: ✅ 추가 도구 영역 (운영 모니터링) 신설
