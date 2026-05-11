# Harness Status (auto-generated)

> 본 페이지는 harness-watcher 매 daily 실행 후 자동 갱신.
> 마지막 갱신: 2026-05-11 (v28.3 초기화, 첫 자동 갱신은 다음 watcher 실행 시)

## 최근 watcher run

- **timestamp**: 2026-05-11 (v28.2 dry-run baseline)
- **frameworks tracked**: 6 registered + 0 auto-discovered (대기)
- **신규 update**: 0건
- **owner correction**: 4건 (atlassian/superpowers/vercel/frontend-design)
- **baseline 수립**: 4건

## Pending flags

| flag | 존재 여부 | 의미 |
|------|:--------:|------|
| `state/cc-researcher-pending.flag` | ❌ | claude-code 신규 release 감지 시 자동 발동 |
| `state/harness-critic-pending.flag` | ❌ | watcher가 update 발견 시 자동 발동 |
| `state/harness-applier-pending.flag` | ❌ | critic APPROVE 시 자동 발동 |
| `state/compaction-critic-pending.flag` | ❌ | compaction-gate 산출물 검증 (v28.3 신규) |

## 최근 PR

| # | merge | 제목 |
|---|:-----:|------|
| #1 | 2026-05-11 | feat(v28.1): Index Router 재설계 + 외부 harness 자가개선 사이클 + critic 흡수 |
| #2 | 2026-05-11 | feat(v28.2): watcher dry-run baseline + owner 자동 보정 + check_method 확장 |
| #3 | (대기) | feat(v28.3): Balanced Token Efficiency + 외부 3 framework 차용 |

## D3 KPI (축소 사이클)

| 지표 | 값 |
|------|----|
| live `references/` 총 KB | (baseline 수립 대기, 다음 watcher 실행 시 측정) |
| baseline (v28.2 시점) | (다음 watcher 실행 시 snapshot) |
| 목표 | ≤ 80% |
| 다음 축소 대상 | (inert reference 검출 대기) |

## 최근 7일 통계

| 항목 | 값 |
|------|----|
| watcher runs | 1 (v28.2 dry-run) |
| updates found | 0 |
| PRs merged | 2 (v28.1, v28.2) |
| NEEDS_INFO | 0 |
| REJECT 누적 | 0 / 3 (Circuit Breaker) |

## 추적 6 framework 현재 baseline

| ID | owner/repo | 최신 | last_checked |
|---|---|---|---|
| bkit-claude-code | popup-studio-ai/bkit-claude-code | v2.1.12 | 2026-05-11 |
| claude-code | anthropics/claude-code | v2.1.138 | 2026-05-11 |
| vercel | vercel/vercel-plugin | 61f1903b | 2026-05-11 |
| superpowers | obra/superpowers | v5.1.0 | 2026-05-11 |
| atlassian | atlassian/atlassian-mcp-server | 9b52fb18 | 2026-05-11 |
| frontend-design | anthropics/claude-plugins-public (subdir) | 00679aef | 2026-05-11 |

## auto-discovered 후보 (B 영역)

| ID | 출처 monorepo | critic prescreen | 등록 상태 |
|---|---|:---:|:--------:|
| (아직 없음 — 다음 watcher 실행 시 frontend-design parent monorepo에서 후보 탐색) | | | |

## v28.3 신규 telemetry (compaction)

| 항목 | 값 |
|------|----|
| compaction-gate 발동 횟수 | 0 (v28.3 cutover 후 측정 시작) |
| 평균 compaction_ratio | (대기) |
| 평균 saved_bytes | (대기) |
| compaction-critic REJECT | 0 / 3 (Circuit Breaker) |
| RAW_FALLBACK 발동 | 0 |

## 다음 watcher 실행 예정

- daily auto-invoke (이전 실행 24h+ 경과 시)
- 수동 평문 트리거: "harness 체크" / "watcher 실행"
