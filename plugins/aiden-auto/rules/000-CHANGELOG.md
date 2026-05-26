# Rules CHANGELOG — 번호 체계 거버넌스

> **목적**: `.claude/rules/`의 번호 sparse(누락) 사유를 추적하고 다음 신규 룰 자리를 명문화. 번호 자체는 git blame·history reference 보존을 위해 재정렬 안 함.

## 현재 활성 룰 (8개)

| 번호 | 파일 | 용도 |
|------|------|------|
| 04 | tdd.md | TDD Red→Green→Refactor (※ H7 결정으로 archive 예정 → superpowers:test-driven-development 위임) |
| 08 | skill-routing.md | Agent Teams 패턴, 스킬 라우팅 |
| 11 | ascii-diagram.md | 다이어그램 출력 규칙 (348줄, 내부 sub-rule 포함) |
| 12 | large-document-protocol.md | 대형 문서 토큰 초과 방지 |
| 13 | requirements-prd.md | PRD-First 정책 |
| 15 | backlog-capture.md | 백로그 즉시 기록 |
| 16 | auto-default.md | /auto 자동 실행 (REVIVED in v27.6 after deprecation in 6af0e83) |
| 21 | cycle-termination.md | 자율 cycle 종료 정의 — design SSOT critic 4 게이트 (D1 사용자 결정 반영) |

## 사라진 번호 추적 (Historical)

| 번호 | 원래 파일명 | 사라진 사유 | 후속 위치 |
|------|------------|-----------|-----------|
| 01 | language.md | CLAUDE.md 통합 | `CLAUDE.md` "Language" 섹션 |
| 02 | paths.md | CLAUDE.md 통합 | `CLAUDE.md` "Safety Rules" — Absolute paths only |
| 03 | git.md | CLAUDE.md 통합 | `CLAUDE.md` "Git" 섹션 |
| 05 | supabase.md | references로 이동 | `references/supabase.md` (외부 권위는 `supabase:supabase` 플러그인) |
| 06 | documentation.md | references로 이동 | `references/documentation.md` |
| 07 | build-test.md | docs로 이동 | `docs/BUILD_TEST.md` |
| 09 | global-only.md | references로 이동 | `references/global-only-policy.md` |
| 10 | image-analysis.md → task-decomposition.md | refactor commit ded9e7b 에서 이미지 분석 → 스킬 가이드라인, 그 후 task-decomposition으로 재할당 후 references로 이동 | `references/task-decomposition.md` |
| 14 | (생성된 적 없음) | 의도적 reserved slot | — |
| 17 | loop-circuit-breaker.md | aiden-auto/rules/로 이전 | `plugins/aiden-auto/rules/17-loop-circuit-breaker.md` |
| 18 | md-first-document.md | 글로벌 SSOT으로 승격 | 글로벌 거버넌스 (CLAUDE.md 또는 references) |
| 19 | feature-block-document.md | 글로벌 SSOT으로 승격 (commit 737b6cf) | 글로벌 거버넌스 |
| 20 | doc-discovery.md | "정리 및 구형 snapshot 제거" (commit a1868b6) | 폐기 또는 references로 이전 |

## 사라진 번호 추적 (이번 critic 정리에서 — 2026-05-10)

| 번호 | 사유 | 위치 |
|------|------|------|
| 04 | superpowers:test-driven-development와 SoT 단일화 (H7 결정) | `_archived/04-tdd.md` (이동 완료 2026-05-10) |

## 다음 신규 룰 자리

| 자리 | 사용 가능 여부 |
|------|--------------|
| 01-03 | ❌ CLAUDE.md 통합으로 영구 reserved |
| 05-07, 09-10 | ❌ references/ 이동으로 영구 reserved |
| 14 | ✅ **사용 가능** (생성 이력 없음) |
| 17 | ❌ aiden-auto plugin 점유 |
| 18-20 | ❌ 글로벌 SSOT 점유 |
| 21+ | ✅ **권장 신규 자리** |

→ 신규 룰은 **21번부터** 부여. 14번은 의도적 reserved slot (역사적 sparse 패턴 보존).

## 번호 체계 운영 정책

1. **재정렬 금지**: git blame·history reference·외부 문서 인용 보호. 한 번 부여된 번호는 영구.
2. **사라진 번호 영구 reserved**: 같은 번호 재사용 금지 (혼동 방지).
3. **CHANGELOG 갱신 의무**: rule 추가/이동/archive 시 본 파일 갱신.
4. **신규 룰 형식**: `<번호>-<kebab-name>.md` (e.g., `21-something.md`).
5. **archive 시**: 파일을 `_archived/`로 이동, 본 CHANGELOG에 기록. CLAUDE.md 또는 references로 위임 시 후속 위치 명시.

## 관련

- `CLAUDE.md` — 프로젝트 핵심 거버넌스 (language, paths, git 흡수)
- `.claude/references/` — rules에서 분리된 참조 문서 (supabase, documentation, global-only, task-decomposition 등)
- `docs/03-analysis/claude-config-critic-2026-05-10.md` — 본 CHANGELOG 추가의 critic 보고서

## 변경 이력

| 날짜 | 변경 | 사유 |
|------|------|------|
| 2026-05-10 | 본 파일 신규 작성 | critic 보고서 H4 결정 — sparse 번호 사유 명문화 |
| 2026-05-26 | rule 21 신규 등록 (cycle-termination.md) | D1 사용자 결정 — "until no more cycles" 종료 정의 (design SSOT critic 4 게이트). G1 갭 해소 |
