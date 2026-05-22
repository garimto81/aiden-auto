---
name: doc-discovery
description: Track document/code change impact via unified reverse-dependency graph (frontmatter + Python ast + JS/TS) plus Hybrid RAG fallback (FTS5 + optional embedding) for semantic gap coverage. Use when files are about to be modified, when /auto workflow enters Phase 0, when the user asks "what is affected by changing X" / "이 파일 바꾸면 뭐가 영향 받아?" / "누락된 영향 파일", or for natural-language queries over docs ("auth 관련 문서 찾아줘"). Prevents the missing-update class of bugs (e.g., editing Overview.md while leaving derivative PRDs stale). Week 1-3 shipped: Layer 1 frontmatter + code graph + mtime cache + PageRank. Week 4-5 shipped: Layer 0 (git pre-commit hook + PreToolUse Edit/Write hook + /auto Phase 0 auto-trigger). Week 6 shipped: Layer 2 (SQLite FTS5 + RRF + optional fastembed/sentence-transformers/OpenAI semantic search + auto-fallback when Layer 1 returns 0).
---

# Doc Discovery

> **RAG = "검색기". 누락 방지 = "변경의 그림자 추적". 본 스킬은 후자를 담당한다.**

## 1. Why this exists

`/auto` 워크플로우에서 문서 한 장을 바꾸면 그것을 인용/파생한 다른 문서가 자동으로 stale 이 된다. 룰 20 (Mandatory Doc Discovery Pre-Work) 이 호출하도록 강제한 도구 (`tools/doc_discovery.py`) 가 실재하지 않아서 직전 사고 (`Command_Center_PRD.md` stale, 2026-05-06) 가 발생했다. 이 스킬이 그 도구의 글로벌 정본이다.

## 2. When to invoke

| 트리거 | 행동 |
|--------|------|
| `/auto` 진입 (Phase 0 entry) | `git diff --name-only HEAD` 의 변경 파일에 대해 `--impact-of` 자동 호출 → 영향 N개를 1줄 보고 |
| `.md` 편집 직전 (PreToolUse Edit/Write hook) | 해당 파일에 대해 `--impact-of` 호출 → 영향 받는 외부 PRD 자동 식별 |
| 사용자 평문: "이 파일 바꾸면 뭐 영향받아", "누락 검사", "impact of X" | `--impact-of <file>` 직접 호출 |
| Phase 4 close 직전 | 변경된 모든 파일에 대해 일괄 호출 → 누락된 frontmatter `last-updated` 갱신 제안 |

## 3. CLI usage (Week 1-3 shipped)

```bash
# 변경 영향 받는 파일 전부 (직접 + 전이적, 코드+문서 통합)
python scripts/doc_discovery.py --impact-of docs/Overview.md --root .

# JSON 출력 (다른 도구가 파싱할 때)
python scripts/doc_discovery.py --impact-of docs/Overview.md --format json

# 직접 영향만 (전이 제외)
python scripts/doc_discovery.py --impact-of docs/Overview.md --no-transitive

# PageRank 점수로 정렬 + 점수 첨부 (영향 큰 파일부터)
python scripts/doc_discovery.py --impact-of docs/Overview.md --with-rank

# 전체 그래프 PageRank top-N (가장 중심적인 파일)
python scripts/doc_discovery.py --rank --top 20

# 빌드 통계 (캐시 hit rate / 경과 시간)
python scripts/doc_discovery.py --impact-of docs/Overview.md --stats

# 캐시 우회 (디버깅 시)
python scripts/doc_discovery.py --impact-of docs/Overview.md --no-cache

# 캐시 관리
python scripts/doc_discovery.py --cache-info
python scripts/doc_discovery.py --cache-clear

# 코퍼스 한쪽만 스캔
python scripts/doc_discovery.py --impact-of foo.md --no-code   # 문서만
python scripts/doc_discovery.py --impact-of bar.py --no-doc    # 코드만
```

Exit codes:
- `0` — 영향 받는 파일 없음 (안전)
- `1` — 영향 받는 파일 있음 (사용자/워크플로우가 처리해야 함)
- `2` — 입력 오류

## 4. Edge types (Layer 1)

frontmatter / 본문에서 자동 추출:

| Edge | 위치 | 의미 |
|------|------|------|
| `derivative-of` | frontmatter | 이 파일은 X의 파생. X 변경 시 본 파일 stale |
| `references` | frontmatter | 단순 참조. X 변경 시 본 파일 review 권장 |
| `supersedes` | frontmatter | 이 파일이 X를 대체함. X 보존만 알려주면 됨 |
| `[text](path.md)` | 본문 markdown link | 약한 reference. transitive 추적 시 깊이 1만 |

frontmatter 형식 (둘 다 지원):
```yaml
derivative-of: Overview.md       # 단일
derivative-of:                   # 다중
  - Overview.md
  - Foundation.md
```

## 5. Project auto-detection (Convention over Config)

스킬은 `.claude/discovery.yml` 이 없어도 작동한다. 다음 디렉토리를 자동 감지:

```
프로젝트 root/
├── docs/00-prd/        → PRD 코퍼스
├── docs/01-plan/       → 계획 코퍼스
├── docs/02-design/     → 설계 코퍼스
├── docs/04-report/     → 보고서 코퍼스
├── .claude/rules/      → 룰 코퍼스
├── docs/templates/     → 템플릿 코퍼스
└── .claude/discovery.yml  ← 옵션 (오버라이드)
```

`.claude/discovery.yml` 옵션 예시:
```yaml
extra_corpora:
  - path: ./Command_Center_UI/
    type: doc
    tier_field: audience
exclude:
  - "**/_generated/**"
  - "**/node_modules/**"
include_extensions:
  - .md
  - .py
```

## 6. Architecture (3-Layer, Layer 0+1 shipped)

```
   Layer 0  PROACTIVE TRIGGER     (Week 4-5 ✅)
            ├─ git pre-commit hook (`hooks/pre_commit_check.py`)
            ├─ PreToolUse Edit/Write hook (`hooks/pretool_md_check.py`)
            └─ /auto Phase 0 auto-trigger (triage.md § Layer 0)
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Layer 1  CODE/DOC GRAPH        (Week 1-3 ✅)
            └─ frontmatter parser + reverse adjacency
            └─ Python ast / JS / TS code graph + bridge edges
            └─ SQLite mtime cache (125x speedup) + PageRank
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Layer 2  HYBRID RAG (fallback) (Week 6+)
            └─ SQLite + sqlite-vec + FTS5 + BGE-M3
            └─ Container Gemma4: contextual chunk + CRAG eval
```

Layer 0+1 결합으로 직전 사고 (`Command_Center_PRD.md` stale) 의 (b) 구조적 누락 + (d) 인지적 누락이 모두 차단된다.

상세 설계 + 누락 4종 분해 + 트렌드 출처: `references/architecture.md` 참조.

## 6.1 Layer 0 활성화 (사용자 1회 실행)

```bash
# 활성화 — 현재 repo + user settings 모두 셋업 (멱등)
python ~/.claude/skills/doc-discovery/scripts/install_hooks.py

# dry-run (파일 변경 없이 확인만)
python ~/.claude/skills/doc-discovery/scripts/install_hooks.py --dry-run

# 비활성화
python ~/.claude/skills/doc-discovery/scripts/install_hooks.py --uninstall

# 임시 차단 (한 세션 한정)
export DOC_DISCOVERY_HOOK_DISABLE=1
```

설치 효과:
- `<repo>/.git/hooks/pre-commit` — staged .md 영향 분석 자동 (soft guard, 절대 block 안 함)
- `~/.claude/settings.json` PreToolUse — Edit/Write/MultiEdit 직전 .md 영향 1줄 경고

## 7. Integration with /auto

본 스킬은 `/auto` Phase 0 entry 가 호출하는 진입점이다. 사용자는 새 명령을 학습할 필요가 없다. 다음과 같이 통합:

```
[/auto 호출]
   |
   v
Phase 0 (Triage)
   |
   ├── git diff --name-only HEAD~1
   |    └── 각 변경 파일에 대해 doc_discovery --impact-of
   |
   v
"X.md 변경이 7개 PRD 에 영향. 함께 갱신할까요?" 1줄 보고
   |
   v
Phase 1 → Phase 4 (변경 시 영향 파일도 함께 추적)
```

사용자 학습 비용: **0 명령**.

## 8. Container Gemma4 활용 (Week 6+ Layer 2 도입 시)

| 역할 | 작업 |
|------|------|
| Contextual chunk 생성 | 인덱싱 시 각 chunk에 50-100 토큰 맥락 prepend (Anthropic 패턴) |
| Impact summary | "이 변경이 외부 PRD § 3.2 와 충돌 가능" 자연어 요약 |
| CRAG confidence eval | RAG 결과의 신뢰도 평가 → 낮으면 "수동 확인 권장" |
| Symbol-PRD linking | 새 코드 commit 시 symbol → PRD § 매칭 |

Layer 1 에서는 Gemma4 호출 없음 (deterministic graph만).

## 9. Roadmap

| Week | 산출물 | 누락 방지 효과 |
|------|--------|---------------|
| **1 (MVP, ✅)** | `lib/graph_builder.py` + `scripts/doc_discovery.py` + frontmatter `derivative-of` graph | 직전 사고 (b) 구조적 누락 즉시 차단 |
| **2-3 (✅)** | Python ast / JS / TS 코드 graph (`lib/code_graph.py`) + SQLite mtime cache (`lib/cache.py`) + 통합 graph (`lib/unified_graph.py`) + PageRank (`lib/pagerank.py`) + bridge edge (코드 주석 → md) | (b) 코드 영역 + (c) 시간적 누락. 실측 cache speedup 125x |
| **4-5 (✅)** | git pre-commit hook (`hooks/pre_commit_check.py`) + PreToolUse Edit/Write hook (`hooks/pretool_md_check.py`) + /auto Phase 0 auto-trigger (triage.md § Layer 0) + 멱등 install/uninstall (`scripts/install_hooks.py`) | (d) 인지적 누락 차단. 51 tests PASS |
| **6 (✅)** | Layer 2 Hybrid RAG — SQLite FTS5 (stdlib, deps zero) + RRF + optional embedder (fastembed/sentence-transformers/OpenAI graceful) + CRAG-style confidence band + Layer 1 → Layer 2 auto-fallback | (a) 의미적 누락 보강. 74 tests PASS |

## 10. Resources

- `lib/graph_builder.py` — frontmatter parser + reverse-adjacency graph (Week 1)
- `lib/code_graph.py` — Python ast + JS/TS regex 코드 그래프 (Week 2)
- `lib/cache.py` — SQLite mtime 캐시 (Week 2)
- `lib/pagerank.py` — power-iteration PageRank (Week 2)
- `lib/unified_graph.py` — doc + code 통합 + bridge edge + cache 적용 (Week 2-3)
- `scripts/doc_discovery.py` — CLI (`--impact-of`, `--rank`, `--with-rank`, `--cache-info`, `--no-cache`, `--stats`, `--semantic-of`, `--fts-build`, `--auto-fallback`, `--no-embed`)
- `scripts/install_hooks.py` — Layer 0 멱등 install/uninstall (Week 4-5)
- `hooks/pre_commit_check.py` — git pre-commit soft guard (Week 4-5)
- `hooks/pretool_md_check.py` — Claude Code PreToolUse Edit/Write hook (Week 4-5)
- `lib/fts5_index.py` — SQLite FTS5 lexical index (Week 6)
- `lib/rrf.py` — Reciprocal Rank Fusion combinator (Week 6)
- `lib/embedder.py` — backend-agnostic embedding adapter (fastembed / sentence-transformers / openai / none) (Week 6)
- `lib/hybrid_search.py` — Layer 2 orchestrator + CRAG-style confidence (Week 6)
- `references/architecture.md` — 3-Layer 설계 + Week 2-6 산출물 상세 + 트렌드 출처
- `tests/test_*.py` — 74 self-verification tests (Week 1: 12, Week 2-3: 27, Week 4-5: 12, Week 6: 23, all PASS)

## 11. Layer 2 사용 (Week 6+)

```bash
# 1회: 인덱스 빌드 (이후 mtime 기반 incremental)
python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py --fts-build --root .

# 자연어 검색 (FTS5 only, deps zero)
python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py \
   --semantic-of "auth 토큰 만료" --root . --no-embed

# 의미 검색 (embedding 백엔드 자동 감지)
pip install fastembed   # 또는 sentence-transformers
python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py \
   --semantic-of "session secrets rotation" --root .

# Layer 1 → Layer 2 자동 폴백
python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py \
   --impact-of docs/Overview.md --root . --auto-fallback
```

신호 체계:
- `✓` 신뢰도 ≥ 0.7 — 결과 그대로 사용
- `~` 0.4-0.7 — 검토 권장
- `?` < 0.4 — 수동 확인 필수
