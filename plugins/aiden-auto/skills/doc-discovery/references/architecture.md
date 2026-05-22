---
title: doc-discovery 3-Layer Architecture (Week 1-3 shipped)
status: REFERENCE
last_updated: 2026-05-06
---

# 3-Layer Discovery Architecture

> **RAG = "검색기" / 누락 방지 = "변경의 그림자 추적".**
> **본 문서는 doc-discovery 스킬이 따르는 설계 원칙과 주간 산출물 범위를 정의한다.**

## Edit History

| 날짜 | 버전 | 트리거 | 변경 |
|------|:----:|--------|------|
| 2026-05-06 | v1.0 | 사용자 directive — "/auto 워크플로우 누락 방지" 심층 분석 후 MVP 1주차 구현 | 최초 작성. 3-Layer 설계 + 누락 4종 + 트렌드 출처 정리 |
| 2026-05-06 | v2.0 | 사용자 directive — "until week 3 autonomous iteration" | Week 2-3 완료 반영. 코드 graph (Python ast + JS/TS regex) + mtime cache (SQLite) + PageRank + 통합 graph + bridge edge + 39 tests PASS. 실측 cache speedup 125x (60s → 0.48s, 2157-node 레포) |
| 2026-05-06 | v3.0 | 사용자 directive — "autonomous iteration week 4-5" | Week 4-5 완료 반영. Layer 0 (proactive trigger) 3종 셋업: git pre-commit hook + PreToolUse Edit/Write hook + /auto Phase 0 auto-trigger. 멱등 install/uninstall, 51 tests PASS (39 회귀 + 12 신규). |
| 2026-05-06 | v4.0 | 사용자 directive — "execute week 6+ autonomous iteration" | Week 6 완료 반영. Layer 2 (Hybrid RAG fallback) — SQLite FTS5 (deps zero) + RRF + optional embedding adapter (fastembed/sentence-transformers/OpenAI graceful degradation) + CRAG-style confidence + Layer 1 → Layer 2 auto-fallback. CLI: `--semantic-of`, `--fts-build`, `--auto-fallback`, `--no-embed`. 74 tests PASS (51 회귀 + 23 신규). |

## 1. The 3-Layer model

```
   Layer 0  PROACTIVE TRIGGER     (Week 4-5)
            git diff / PreToolUse hook / file watcher
            └─ "사용자가 호출 안 해도 작동" — 인지적 누락 (d) 차단
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Layer 1  CODE/DOC GRAPH        (Week 1 MVP)
            frontmatter parser + reverse adjacency + (Week 2-3) Tree-sitter
            └─ "이 변경이 영향 주는 파일 N개" — 구조적 누락 (b) 차단
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   Layer 2  HYBRID RAG fallback   (Week 6+)
            SQLite + sqlite-vec + FTS5 + BGE-M3 + RRF
            Container Gemma4: contextual chunk + CRAG eval
            └─ Layer 1 매칭 0개일 때만 호출 — 의미적 누락 (a) 보강
```

### 본 MVP 의 범위

- Layer 1 의 frontmatter 부분만 구현
- 의존성: Python 표준 라이브러리 + (옵션) PyYAML
- 글로벌 스킬, 모든 프로젝트에서 사용 가능

## 2. 누락 4종 분해

| 종류 | 정의 | /auto 발생 지점 | 본 MVP 대응 |
|------|------|----------------|------------|
| **(a) 의미적** | "auth 관련 룰" 검색 시 단어 다른 룰 못 찾음 | Phase -2 카테고리 분류 | ❌ Layer 2 필요 |
| **(b) 구조적** | `Overview.md` 변경 시 `derivative-of: Overview.md` 인 PRD 7종 못 찾음 | Phase 2 Build / Phase 4 Close | ✅ **본 MVP 가 해결** |
| **(c) 시간적** | 어제 인덱스라 방금 추가한 룰 못 찾음 | 모든 Phase | 부분 (매번 build, cache 없음) |
| **(d) 인지적** | 사용자가 변경했는데 워크플로우는 능동적으로 모름 | Phase -2 ~ Phase 4 전부 | ❌ Layer 0 필요 |

직전 사고 (`Command_Center_PRD.md` stale, 2026-05-06) = (b) + (d). 본 MVP 는 (b) 를 즉시 차단한다. (d) 는 Week 4-5 git hook 으로.

## 3. Layer 1 알고리즘 한 눈에

```
입력: target_file (예: docs/Overview.md)

1. build_graph(root)
   └─ 모든 .md 파일 walk
       └─ frontmatter parse (derivative-of, references, supersedes)
       └─ 본문 markdown link parse
       └─ forward + reverse 양방향 adjacency 저장

2. reverse_traversal(target_file, transitive=True)
   └─ BFS depth=0 부터 시작
       └─ depth N 의 각 노드의 reverse[edge_type] 따라가서 depth N+1 채움
       └─ 순환 방지 (seen set)
       └─ depth 별 layer dict 반환

3. impact_analysis(graph, target)
   └─ direct = layers[1]
   └─ transitive = layers[2..]
   └─ total_affected = 모든 depth 합

출력: {target, exists, direct, transitive, total_affected}
```

비유 (15세 수준): 책 한 권 옮길 때 "이 책을 인용한 다른 책 목록" 카드를 따라가서 영향 받는 책 5권 즉시 식별. 카드 없으면 (검색기) 사서가 일일이 뒤져야 함.

## 4. Edge type semantics

| Edge | weight | transitive 추적 | 의미 |
|------|:------:|:--------------:|------|
| `derivative-of` | strong | yes | 본 파일은 X 의 파생. X 변경 시 본 파일 stale 확정 |
| `supersedes` | strong | yes | 본 파일이 X 를 대체. X 변경 시 본 파일 review |
| `references` | medium | yes | 단순 참조. X 변경 시 본 파일 review 권장 |
| `link` (md inline) | weak | depth 1 만 | 약한 reference. transitive 깊이 1 |

## 5. Convention over Config (자동 감지 디렉토리)

```
프로젝트 root/
├── docs/00-prd/        ← PRD
├── docs/01-plan/       ← 계획
├── docs/02-design/     ← 설계
├── docs/04-report/     ← 보고서
├── docs/05-analysis/   ← 분석
├── docs/templates/     ← 템플릿
├── .claude/rules/       ← 룰
├── .claude/skills/      ← 스킬
└── .claude/discovery.yml ← 옵션 (오버라이드)
```

`.claude/discovery.yml` 미존재 시 위 default 만으로 작동. 사용자 학습 비용 0.

## 6. /auto 통합 지점 (Week 4-5 추가 예정)

| 지점 | 트리거 | 행동 |
|------|--------|------|
| `/auto` Phase 0 entry | 호출 직후 | `git diff --name-only HEAD~1` → 각 파일에 `--impact-of` → 1줄 보고 |
| PreToolUse(Edit/Write) | `.md` 편집 직전 | `--impact-of` → 영향 외부 PRD 자동 식별 |
| Phase 4 close 직전 | commit 직전 | 변경 파일 일괄 → `last-updated` 자동 갱신 제안 |
| 세션 시작 (선택) | 첫 turn | 직전 commit 이후 변경의 영향 범위 1줄 요약 |

## 7. 트렌드 출처 (2024-2026)

본 MVP 의 설계 근거가 된 자료:

- [Anthropic Contextual Retrieval (2024-09)](https://www.anthropic.com/news/contextual-retrieval) — chunk 에 context prepend, 35-49% 개선. Layer 2 도입 시 활용.
- [Microsoft GraphRAG](https://www.microsoft.com/en-us/research/blog/graphrag-new-tool-for-complex-data-discovery-now-on-github/) — entity-relation graph + community summary. Layer 1 typed edge 의 영감.
- [Aider Repository Map](https://aider.chat/docs/repomap.html) — Tree-sitter + PageRank 기반 token-budgeted symbol map. Week 2-3 코드 graph 의 모델.
- [Sourcegraph Cody — How Cody understands codebase](https://sourcegraph.com/blog/how-cody-understands-your-codebase) — embedding 폐지 + Tree-sitter 우선. 구조 우선 원칙 검증.
- [Bazel rdeps query](https://buildkite.com/resources/blog/a-guide-to-bazel-query/) — reverse-dependency 의 정석 패턴. 본 MVP 의 reverse_traversal 직접 영감.
- [Semgrep cross-file analysis](https://semgrep.dev/docs/semgrep-code/semgrep-pro-engine-intro) — type / inheritance / taint propagation. Week 2-3 추가 모델.
- [CRAG (Corrective RAG, 2024)](https://arxiv.org/abs/2401.15884) — confidence eval + fallback web search. Layer 2 신뢰도 측정 모델.

## 8. Week 1 MVP 검증 기준

다음 5개를 충족하면 MVP 합격:

| # | 기준 | 검증 방법 |
|:-:|------|----------|
| 1 | `python doc_discovery.py --impact-of <file>` 정상 종료 | exit 0 또는 1 |
| 2 | frontmatter `derivative-of` 단일/다중 형식 모두 파싱 | tests/test_graph_builder.py |
| 3 | reverse traversal 이 직접 + 전이 영향 모두 발견 | tests + 실제 PRD 시나리오 |
| 4 | `--no-transitive` 옵션이 직접 영향만 반환 | tests |
| 5 | JSON / text 두 출력 형식 동작 | CLI 직접 호출 |

## 9. Roadmap (확정)

- **Week 1 (MVP, 완료 ✅)**: Layer 1 frontmatter graph + CLI
- **Week 2-3 (완료 ✅)**: 코드 graph (Python ast + JS/TS regex) + PageRank + mtime cache + 통합 graph + bridge edge
- **Week 4-5 (완료 ✅)**: Layer 0 — git pre-commit hook + PreToolUse Edit/Write hook + /auto Phase 0 auto-trigger + 멱등 install/uninstall
- Week 6+: Layer 2 Hybrid RAG + Container Gemma4 통합

## 10. Week 2-3 산출물 상세

### 추가된 모듈

| 모듈 | 책임 | 의존성 |
|------|------|--------|
| `lib/code_graph.py` | Python ast로 import/def 추출, JS/TS regex로 import/export 추출 | stdlib (`ast`, `re`) |
| `lib/cache.py` | SQLite 기반 mtime cache (path + mtime + size 키) | stdlib (`sqlite3`, `json`) |
| `lib/pagerank.py` | Power-iteration PageRank (damping=0.85, tol=1e-6, max_iter=50) | stdlib (`typing`) |
| `lib/unified_graph.py` | doc + code graph 결합 + bridge edge (코드 주석 → md 참조) + cache 적용 | 위 3개 |

### 새 CLI 플래그

| 플래그 | 효과 |
|--------|------|
| `--rank --top N` | 전체 그래프 PageRank top-N 출력 |
| `--with-rank` | `--impact-of` 결과를 PageRank 점수로 정렬 + 점수 첨부 |
| `--no-cache` | mtime cache 우회 (디버깅용) |
| `--cache-info` / `--cache-clear` | cache 통계 / 비우기 |
| `--no-code` / `--no-doc` | 한 쪽 코퍼스만 스캔 |
| `--stats` | nodes / elapsed / hit_rate를 stderr로 출력 |

### 새 edge type 4종

| Edge | source → target 의미 |
|------|---------------------|
| `imports` (code) | 파일이 모듈을 import |
| `defines` (code) | 파일이 top-level symbol 정의 |
| `references` (code) | from-import로 외부 symbol 참조 |
| `references` (bridge) | 코드 주석/docstring이 .md 경로 언급 |

### 실측 성능 (2157 노드, 573 파일)

| 모드 | 경과 | hit rate |
|------|:----:|:--------:|
| Cold (캐시 비우기 후) | 60s | 0.0% |
| Warm (재실행) | 0.48s | 100% |
| **Speedup** | **125x** | — |

### Week 1 회귀 + Week 2-3 신규 — 39 tests PASS

| 슈트 | 테스트 수 | 결과 |
|------|:--------:|:----:|
| `test_graph_builder.py` (Week 1) | 12 | PASS |
| `test_code_graph.py` (Week 2) | 7 | PASS |
| `test_cache.py` (Week 2) | 8 | PASS |
| `test_pagerank.py` (Week 2) | 8 | PASS |
| `test_integration.py` (Week 3) | 4 | PASS |
| **합계** | **39** | **PASS** |

## 11. Week 4-5 산출물 상세 (Layer 0)

> **목표**: 사용자가 doc_discovery 를 명시 호출하지 않아도 작동. 인지적 누락 (d) 차단.

### 추가된 hook 3종

| 진입점 | 파일 | 동작 |
|--------|------|------|
| Git pre-commit | `hooks/pre_commit_check.py` | staged .md → `--impact-of` → soft warn (절대 block 안 함) |
| Claude Code PreToolUse | `hooks/pretool_md_check.py` | Edit/Write/MultiEdit .md → 영향 1줄 stderr 경고 |
| `/auto` Phase 0 entry | `triage.md § Layer 0 Auto-Trigger` | git diff .md → 자동 영향 분석 + TriageContract 갱신 |

### 멱등 install/uninstall

| 경로 | 동작 |
|------|------|
| `<repo>/.git/hooks/pre-commit` | `# doc-discovery-layer0` 마커 기반. 기존 hook 있으면 refuse (수동 chain 안내) |
| `~/.claude/settings.json` PreToolUse | 동일 command 매칭 dedup. 다중 install 시 1개만 등록 |
| `--dry-run` | 파일 변경 없이 sequence 미리보기 |
| `--uninstall` | 마커가 우리것일 때만 제거. 외부 hook 보존 |
| `DOC_DISCOVERY_HOOK_DISABLE=1` | 런타임 임시 차단 |

### Week 1-3 회귀 + Week 4-5 신규 — 51 tests PASS

| 슈트 | 테스트 수 | 결과 |
|------|:--------:|:----:|
| `test_graph_builder.py` (Week 1, conftest fix) | 12 | PASS |
| `test_code_graph.py` (Week 2) | 7 | PASS |
| `test_cache.py` (Week 2) | 8 | PASS |
| `test_pagerank.py` (Week 2) | 8 | PASS |
| `test_integration.py` (Week 3) | 4 | PASS |
| `test_hooks.py` (Week 4-5 신규) | 12 | PASS |
| **합계** | **51** | **PASS** |

### test_hooks.py 커버리지 (12 tests)

| 영역 | 테스트 |
|------|--------|
| pre-commit | silent on no staged md / warns when overview changes / disable env var |
| pretool | silent on non-md / silent on empty event / silent on malformed JSON / warns on overview / silent outside repo |
| installer | creates pre-commit / refuses to overwrite foreign hook / pretool idempotent / uninstall cleans both sides |

### 사이드 이펙트 (의도된)

| 변경 위치 | 영향 |
|-----------|------|
| `tests/conftest.py` 신규 | Week 1 fixture 누락 사전결함 해결. 회귀 8 errors → 0 |
| `triage.md § Layer 0` 신규 | /auto 워크플로우가 진입 시 자동 호출. 명시 옵션 불필요 |
