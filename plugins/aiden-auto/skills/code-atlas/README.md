# Code Atlas — Local AI Hallucination Verification

AI 가 생성한 코드의 환각(hallucination)을 비개발자가 시각적으로 검증하는 **완전 로컬** 도구. Supabase / 계정 / 외부 서비스 없이 동작. 임의 TypeScript/JavaScript 프로젝트에 적용 가능.

## 설치

```bash
cd ~/.claude/skills/code-atlas
npm install
```

## 사용법

Claude Code 에서:

```
/code-atlas                    # 현재 디렉토리 분석
/code-atlas /path/to/project   # 특정 디렉토리
/code-atlas . --no-open        # 브라우저 자동 오픈 없이
/code-atlas . --port 4321      # 포트 고정
/code-atlas . --no-server      # 분석만, DB 저장 후 종료
```

직접 CLI 실행:

```bash
cd ~/.claude/skills/code-atlas
node --import tsx scripts/cli.ts /path/to/project
```

## 감지 유형

| ID | 유형 | 설명 | 기법 | 비용 |
|:---:|------|------|------|:----:|
| **H1** | Phantom Reference | import 한 모듈이 실제로 없음 | ts-morph 심볼 resolve | 즉시 |
| **H3** | Hollow Stub | 선언만 있고 본문 비어 있음 | AST heuristic (`return null`, `throw 'not implemented'`, `TODO`) | 즉시 |
| **H4** | Silent Duplicate | 같은 역할 함수 여러 파일에 중복 | Jaccard AST n-gram similarity (>= 0.75) | O(N²) 단일 스캔 |
| **H7** | Dangling Edge | UI→API 선은 있으나 핸들러가 mock 만 반환 | Next.js call graph + DB 패턴 매칭 | 즉시 |

## 저장소

타겟 프로젝트 루트에 `.code-atlas/atlas.db` (SQLite) 생성. `.gitignore` 에 `.code-atlas/` 추가 권장.

## Action Dock

환각 노드 선택 시 하단 독에 3개 버튼:

1. **📋 Claude 프롬프트 복사** — 수정 지시·증거·검증 기준이 포함된 자기완결형 프롬프트를 클립보드에 복사. 새 Claude 세션에 붙여넣기
2. **🐛 GitHub Issue 생성** — `gh` CLI 로 이슈 생성 (gh 설치·인증 필요). 라벨 `ai-hallucination` 자동 부착
3. **✅ 오탐 표시** — fingerprint 를 `false_positives` 테이블에 저장 → 다음 스캔부터 제외

## 테스트

```bash
cd ~/.claude/skills/code-atlas
npm test
```

픽스처 위치: `tests/fixtures/bad-repo/` — H1/H3/H4 를 의도적으로 심어둠.

## 아키텍처

```
scripts/
├── cli.ts                    # Entry point
├── analyzer/
│   ├── index.ts              # runScan orchestrator
│   ├── project.ts            # ts-morph Project loader
│   ├── types.ts              # Hallucination types
│   ├── fingerprint.ts        # SHA-256 fingerprints
│   ├── phantom.ts            # H1
│   ├── hollow.ts             # H3
│   ├── duplicate.ts          # H4 (Jaccard)
│   └── dangling.ts           # H7 (Next.js)
├── storage/
│   └── db.ts                 # better-sqlite3 CRUD
├── viewer/
│   ├── server.ts             # Node http server
│   └── static/
│       ├── index.html
│       ├── app.js            # Vanilla JS + fetch (no framework)
│       └── styles.css
├── action/
│   ├── prompt.ts             # Claude Code prompt builder
│   └── issue.ts              # gh CLI wrapper
└── utils/
    ├── open-url.ts           # open@10 wrapper
    └── git-blame.ts          # git blame helper
```

## 설계 원칙

1. **완전 로컬** — 외부 서비스 호출 0, 인증 불필요
2. **프로젝트 무관** — `/code-atlas [dir]` 로 어떤 TS/JS 프로젝트든 분석 가능
3. **결정론적** — LLM 호출 없이 AST 기반 (일관된 결과, 빠름)
4. **오탐 학습** — fingerprint 기반 false positive DB 로 반복 노이즈 제거
5. **AI-native UX** — 핵심 출력은 "다시 AI 에게 던질 수 있는 완결형 프롬프트"

## 제약 (v2.0.0)

- 언어: TS/JS 만. 다른 언어 (Python, Go) 는 미지원
- H7 는 Next.js App Router 만 최적화됨. 다른 프레임워크는 무반응
- H4 는 Jaccard AST 유사도 — 의미는 비슷하지만 구조가 다른 중복은 놓칠 수 있음 (embeddings 기반 v3 에서 개선 예정)
- H3 는 AST heuristic 만 사용. Self-consistency LLM 2차 검증은 v3 에서 옵션 추가 예정

## Changelog

| 버전 | 날짜 | 변경 |
|------|------|------|
| 2.0.0 | 2026-04-17 | 전면 재설계 — Supabase/Next.js 앱 의존 제거, 로컬 SQLite, 표준 HTTP 서버, Jaccard H4 |
| 1.0.0 | 2026-04-17 | M1 Skeleton — project_master 의존 (v1 deprecated) |
