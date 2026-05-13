# Harness Status (auto-generated)

> 본 페이지는 harness-watcher 매 daily 실행 후 자동 갱신.
> 마지막 갱신: 2026-05-11 19:30 (v28.4 운영 첫 사이클 — autonomous iteration)

## 최근 watcher run

- **timestamp**: 2026-05-11 (v28.4 운영 첫 사이클 — D3 + B 동시 발동)
- **frameworks tracked**: 6 registered + **4 candidates auto-discovered**
- **신규 update**: 0건 (registered 6개 모두 baseline 동일)
- **monorepo discovery**: anthropics/claude-plugins-public 하위 **35 plugin** 탐색 → **4 후보** prescreen 통과

## Pending flags

| flag | 존재 여부 | 의미 |
|------|:--------:|------|
| `state/cc-researcher-pending.flag` | ❌ | claude-code 신규 release 감지 시 자동 발동 |
| `state/harness-critic-pending.flag` | ❌ | watcher가 update 발견 시 자동 발동 |
| `state/harness-applier-pending.flag` | ❌ | critic APPROVE 시 자동 발동 |
| `state/compaction-critic-pending.flag` | ❌ | compaction-gate 산출물 검증 (v28.3 신규) |
| `state/harness-discoveries-2026-05-11.json` | ✅ | **4 후보 사용자 옵트인 대기** |
| `state/d3-baseline-2026-05-11.json` | ✅ | **D3 baseline 수립 완료** |

## 최근 PR

| # | merge | 제목 |
|---|:-----:|------|
| #1 | 2026-05-11 | feat(v28.1): Index Router 재설계 + 외부 harness 자가개선 사이클 + critic 흡수 |
| #2 | 2026-05-11 | feat(v28.2): watcher dry-run baseline + owner 자동 보정 + check_method 확장 |
| #3 | 2026-05-11 | feat(v28.3): Balanced Token Efficiency + 외부 3 framework 차용 |
| #4 | (대기) | chore(v28.4): D3 inert 제거 + monorepo discovery 첫 사이클 |

## D3 KPI (축소 사이클)

| 지표 | 값 |
|------|----|
| live `references/` 총 KB (baseline) | **424 KB** (42 파일) |
| live 가장 큰 파일 (Top 3) | phase-1-plan.md (870줄) / options-handlers.md (691줄) / phase-2-build.md (552줄) |
| **inert reference 검출** | **9개 (60 KB, 14.2%)** |
| 제거 권고 | **7개 (52 KB)** |
| 보존 권고 | 2개 (documentation.md, project-inventory.md) |
| **제거 후 예상** | **372 KB (87.7%)** |
| **KPI 목표** | ≤ 80% (현재 100%, 제거 시 87.7%) |
| **추가 축소 필요** | 7.7% (active reference selective slice 검토) |

### 제거 대상 7개 (PR #4 예정)

| 파일 | 줄 | KB | 제거 사유 |
|---|--:|--:|---|
| agent-format.md | 143 | 8 | agent 형식 정의, 우리 agent에 inline 가능. 5원칙 무관 |
| explanation-style.md | 201 | 8 | communication-style.md와 중복 |
| global-only-policy.md | 193 | 8 | 글로벌 CLAUDE.md와 중복 |
| model-routing-guide.md | 262 | 12 | v27.x 잔재. critic-protocol-unified에 흡수됨 |
| skill-causality-graph.md | 80 | 8 | v27.x 인과 그래프. 신규 5원칙에 흡수 |
| supabase.md | 77 | 4 | supabase 특화. 우리 plugin 미사용 |
| task-decomposition.md | 119 | 4 | v27.x task 분해. iteration chapter에 흡수 |

## 최근 7일 통계

| 항목 | 값 |
|------|----|
| watcher runs | 2 (v28.2 dry-run + v28.4 운영 첫 사이클) |
| updates found | 0 (registered 6개 변화 없음) |
| **monorepo discoveries** | **1회** (anthropics/claude-plugins-public 35 plugin 탐색) |
| **discovery 후보** | **4 (claude-md-management, pr-review-toolkit, hookify, skill-creator)** |
| PRs merged | 3 (v28.1, v28.2, v28.3) |
| PRs pending | 1 (v28.4) |
| NEEDS_INFO | 0 |
| REJECT 누적 | 0 / 3 (Circuit Breaker) |

## 추적 6 framework 현재 baseline (변화 없음)

| ID | owner/repo | 최신 | last_checked |
|---|---|---|---|
| bkit-claude-code | popup-studio-ai/bkit-claude-code | v2.1.12 | 2026-05-11 |
| claude-code | anthropics/claude-code | v2.1.138 | 2026-05-11 |
| vercel | vercel/vercel-plugin | 61f1903b | 2026-05-11 |
| superpowers | obra/superpowers | v5.1.0 | 2026-05-11 |
| atlassian | atlassian/atlassian-mcp-server | 9b52fb18 | 2026-05-11 |
| frontend-design | anthropics/claude-plugins-public (subdir) | 00679aef | 2026-05-11 |

## auto-discovered 후보 4 (B 영역 — 사용자 옵트인 대기)

| ID | 출처 | prescreen | 핵심 가치 |
|---|---|:---:|---|
| **claude-md-management** | anthropics/claude-plugins-public/plugins/claude-md-management | **80** | 우리 5원칙 CLAUDE.md 관리 직결 |
| **pr-review-toolkit** | anthropics/claude-plugins-public/plugins/pr-review-toolkit | **75** | 우리 PR flow (#1/#2/#3) 동형 |
| **hookify** | anthropics/claude-plugins-public/plugins/hookify | **70** | Hook 표준 차용 (27 hooks 정리) |
| **skill-creator** | anthropics/claude-plugins-public/plugins/skill-creator | **70** | 이미 우리 세션 사용 중. 공식 표준 동기화 |

상세: `state/harness-discoveries-2026-05-11.json`.

**사용자 옵트인 방법**: 평문 *"신규 plugin 등록해줘"* 또는 4 후보 중 일부 명시.

## v28.3 신규 telemetry (compaction)

| 항목 | 값 |
|------|----|
| compaction-gate 발동 횟수 | 0 (실제 작업 대기) |
| 평균 compaction_ratio | (대기) |
| 평균 saved_bytes | (대기) |
| compaction-critic REJECT | 0 / 3 (Circuit Breaker) |
| RAW_FALLBACK 발동 | 0 |

## 다음 watcher 실행 예정

- daily auto-invoke (이전 실행 24h+ 경과 시)
- 수동 평문 트리거: "harness 체크" / "watcher 실행"
- 사용자 옵트인 대기: 4 discovery 후보 등록 결정
