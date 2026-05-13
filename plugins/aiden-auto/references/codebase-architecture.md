# Codebase Architecture

상세 코드 아키텍처 참조. CLAUDE.md의 Architecture Summary와 함께 사용.

---

## 1. Multi-Agent 시스템 (`src/agents/`)

```
src/agents/
├── __init__.py          # WorkflowState, build_parallel_workflow, Teams API 공개
├── config.py            # AGENT_MODEL_TIERS, TEAM_CONFIGS, COMPLEXITY_TEAM_MAP
├── parallel_workflow.py # LangGraph Fan-Out/Fan-In 병렬 실행
├── teams/               # 4팀 오케스트레이션 (v2.0)
│   ├── coordinator.py   # 복잡도 분석 → 팀 배치 → 의존성 실행 → 결과 통합
│   ├── base_team.py     # BaseTeam 추상 클래스 (State → Node → Graph → Run)
│   ├── dev_team.py      # 개발팀 (설계, 구현, 테스트, 문서화)
│   ├── quality_team.py  # 품질팀 (PDCA 사이클 검증)
│   ├── ops_team.py      # 운영팀 (CI/CD, 인프라, 모니터링)
│   └── research_team.py # 리서치팀 (코드 분석, 웹 조사)
└── prompt_learning/     # 프롬프트 최적화 (DSPy, TextGrad)
```

**모델 티어링:** supervisor/lead/coder → sonnet, validator/assistant → haiku

**팀 배치 규칙** (복잡도 점수 0-10): 4-5 → Dev, 6-7 → Dev+Quality, 8-9 → +Research, 10 → 4팀 전체

## 2. 통합 라이브러리 (`lib/`)

```
lib/
├── gmail/          # Gmail OAuth + 메일 CRUD (Browser OAuth)
├── slack/          # Slack OAuth + 메시징 + Lists API (Bot/User Token)
├── google_docs/    # Markdown→Google Docs 변환, Drive 정리, 프로젝트 레지스트리
├── pdf_utils/      # PDF/MD 텍스트 추출 + 4가지 청킹 전략 (Fixed-size, Hierarchical, Semantic, Late) + `/chunk --prd`
├── ocr/            # Tesseract OCR 정밀 텍스트 추출 (pytesseract + OpenCV)
├── mockup_hybrid/  # HTML 와이어프레임 + Google Stitch 하이브리드 목업
└── ai_auth/        # AI 서비스 인증 통합 (GPT, Gemini)
```

**인증 방식:** 모든 lib은 Browser OAuth 사용 (API 키 금지). 토큰 저장: `C:\claude\json\`

## 3. 커맨드 시스템 (`.claude/commands/`)

22개 커맨드 (`/auto`, `/commit`, `/check`, `/chunk`, `/prd-update` 등). 각 `.md` 파일이 슬래시 커맨드 정의.

## 4. 에이전트 시스템 (`.claude/agents/`)

42개 로컬 에이전트. OMC 플러그인 완전 제거됨 (2026-02-18) — 모든 에이전트가 `.claude/agents/`에서 직접 로드됨.

**주요 에이전트**: `architect`, `executor`, `executor-high`, `planner`, `critic`, `designer`, `code-reviewer`, `qa-tester`, `gap-detector`, `writer`, `researcher`

## 5. 스킬 시스템 (`.claude/skills/`)

38개 스킬 디렉토리. 각 디렉토리에 `SKILL.md` + 관련 파일. 자동/수동 트리거 지원.

## 6. Hook 시스템 (`.claude/hooks/`)

| Hook | 역할 | 이벤트 |
|------|------|--------|
| `tool_validator.py` | 프로세스 전체 종료 명령 차단 | PreToolUse |
| `session_init.py` | 세션 시작 시 TDD 준수 경고 | SessionStart |
| `branch_guard.py` | main/master 브랜치에서 비허용 파일 수정 차단 | PreToolUse |
| `post_edit_check.js` | 편집 후 품질 검증 | PostToolUse |

## 7. 주요 하위 프로젝트

| 프로젝트 | 경로 | 설명 |
|----------|------|------|
| **automation_hub** | `C:\claude\automation_hub` | WSOP 방송 자동화 공유 인프라 (PostgreSQL, Supabase) |
| **archive-analyzer** | `C:\claude\archive-analyzer` | 미디어 파일 분류 및 MAM 시스템 |
| **vimeo_ott** | `C:\claude\vimeo_ott` | Vimeo OTT 콘텐츠 업로드/관리 (VHX API, S3) |
| **src/agents** | `C:\claude\src\agents` | Multi-Agent 병렬 워크플로우 시스템 (LangGraph) |
| **lib/** | `C:\claude\lib` | 통합 라이브러리 (Gmail, Slack, Google Docs, PDF, Mockup, AI Auth) |
