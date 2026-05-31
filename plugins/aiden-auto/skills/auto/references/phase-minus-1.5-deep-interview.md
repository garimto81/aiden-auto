---
name: phase-minus-1.5-deep-interview
phase: -1.5
version: v28.5
loaded_from: skill-auto
purpose: Deep Interview (의도 명료화 + 실행 방식 + Confluence sync 선택)
---

# Phase -1.5 — Deep Interview

> 산출물 `active-goal.json` 은 schema_version 1.1 (`lib/goal/goal_writer.py` 의 `SCHEMA_VERSION` 과 정합).

## 발동 시점

Phase -2 직후, /goal 자율 iteration 시동 직전.

Skip 조건:
- `!quick` / `!just` / `!hotfix` Magic Word
- `/goal` 명시 condition 제공
- 모호성 점수 < 0.5 (아주 명료한 작업)

## Part A — Brainstorming (의도 명료화)

`Skill("superpowers:brainstorming")` 외부 위임.

- 1 question at a time
- 2-3 approaches + 사용자 승인
- 산출물: `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`

질문 형식 (AskUserQuestion 도구 의무 — 가르침 #6):

> 옛 마크다운 표 → AskUserQuestion 도구. 단일 추천 + 선택지 정신 유지 (feedback_multi_session_choice). 비전문어 풀이.

```
AskUserQuestion(
  question="이 작업을 어떤 방식으로 실행할까요? (잘 모르겠으면 '자율'을 고르면 Claude 가 알아서 정합니다)",
  header="실행 방식",
  multiSelect=false,
  options=[
    {label: "자율 (추천)",
     description: "Claude 가 작업 성격을 보고 알아서 방식 선택. 결정 부담 최소 — 권장 기본값."},
    {label: "별도 세션 (Claude Agents)",
     description: "백그라운드 OS 세션으로 분리 실행. 큰 작업 여러 개 / 1일+ 장기 작업에 적합."},
    {label: "가벼운 단발 (Subagent)",
     description: "같은 세션에서 한 번 위임. 가장 가볍고 즉시 결과."},
    {label: "리뷰 포함 (Superpowers)",
     description: "계획 + 2단계 자동 검토까지. 중간 복잡도 + 리뷰가 꼭 필요할 때."},
  ]
)
```

응답을 active-goal.json 의 `multi_session_method` 필드에 저장 (label 기준).

## Part C — Confluence Sync 선택 (v28.5 신규)

**발동 조건**: DOC chapter 만 (CODE/QA/ITERATION/RESEARCH/MEDIA 에서는 skip)

질문 형식 (AskUserQuestion 도구 의무 — 가르침 #6):

> 인라인 텍스트 질문 금지. AskUserQuestion 도구 직접 호출 + 비전문어 풀이.

```
AskUserQuestion(
  question="작성한 문서를 GG NETWORK Confluence(사내 위키)에 자동으로 올릴까요?",
  header="Confluence",
  multiSelect=false,
  options=[
    {label: "기존 페이지 갱신",
     description: "이미 있는 위키 페이지를 새 내용으로 덮어씀. 페이지 ID 필요 (URL 의 /pages/{id} 숫자)."},
    {label: "새 페이지 생성",
     description: "위키에 새 페이지로 게시. 부모 페이지 ID 또는 공간(space) key 필요."},
    {label: "로컬만 (기본)",
     description: "위키 게시 안 함. 내 PC 파일로만 보관 (권장 기본값)."},
  ]
)
```

응답 처리:

| AskUserQuestion 답 (label) | active-goal.json 의 `confluence_sync` |
|---------|-------------------------------------|
| 로컬만 (기본) / 응답 없음 | `{"enabled": false}` |
| 기존 페이지 갱신 (+page_id) | `{"enabled": true, "mode": "update", "page_id": "..."}` |
| 새 페이지 생성 (+parent_id) | `{"enabled": true, "mode": "new", "parent_id": "..."}` |

## Part D — Executive Summary 결정 (v28.6 신규)

**발동 조건**: DOC chapter 만 + 자율 판단 휴리스틱 충족 시

### 자율 판단 (자동 평가, 사용자 개입 없음)

다음 **모두 true** 시 → 사용자에게 질문 추가:

1. `chapter == DOC`
2. Magic Word (`!quick` / `!just` / `!hotfix`) 부재
3. 다음 중 하나:
   - 키워드 매칭: `PRD` / `기획` / `전략` / `design` / `spec` / `보고서` / `report`
   - spec 예상 길이 ≥ 100줄
   - 이해관계자 키워드: `stakeholder` / `임원` / `전사` / `배포` / `보고`

조건 미충족 → **자동 skip** (질문 안 함, 생성 안 함). 진입점 0.

### 질문 형식 (조건 충족 시만 — AskUserQuestion 도구 의무, 가르침 #6 정합)

> 인라인 마크다운 텍스트 질문 금지. **AskUserQuestion 도구 직접 호출** (가르침 #6 — feedback_askuserquestion_mandatory). 비전문어 풀이 + 갈래별 결과 명시.

```
AskUserQuestion(
  question="작성할 문서에 Executive Summary(1페이지 요약)를 포함할까요? "
           "본문을 안 읽어도 전체를 한눈에 파악할 수 있는 요약입니다.",
  header="Exec Summary",
  multiSelect=false,
  options=[
    {label: "본문 첫 섹션 포함",
     description: "문서 맨 앞에 1페이지 요약 삽입 (기본 권장). 읽는 사람이 본문 전 전체를 빠르게 파악."},
    {label: "별도 파일로",
     description: "{slug}.exec-summary.md 로 분리 생성. 본문과 따로 공유·배포하기 좋음."},
    {label: "포함 안 함",
     description: "본문만 작성. 요약 페이지 생략."},
  ]
)
```

### 응답 처리

| AskUserQuestion 답 (label) | active-goal.json 의 `executive_summary` |
|---------|---------------------------------------|
| 본문 첫 섹션 포함 | `{"enabled": true, "mode": "inline"}` |
| 별도 파일로 | `{"enabled": true, "mode": "separate"}` |
| 포함 안 함 / 응답 없음 / 자동 skip | `{"enabled": false}` |

### Phase 1.3 동작 연동

`executive_summary.enabled = true` 시 chapter-doc 의 Step 1.3 자동 발동.
`false` 시 Step 1.3 skip → Step 1.4 (Multi-perspective Validation) 직행.

상세 양식 + 검증 룰: `references/executive-summary-template.md`.

## Part E — Atlassian MCP 인증 자율 점검 (v28.7 신규)

**발동 조건**: Atlassian 사용 자율 감지 시에만 (미감지 시 호출 자체 없음 — 부하 0)

### 자율 판단 (자동 평가, 사용자 개입 없음)

다음 중 **하나 이상** 충족 시 → atlassian_auth executor 호출:

1. 사용자 입력에 키워드: `Jira` / `Confluence` / `Atlassian` / `ticket` / `이슈` / `에픽` / `epic` / `sprint`
2. Part C 답변이 (1) 또는 (2) — Confluence sync 활성화
3. 본 세션에서 `atlassian:*` skill 호출 검출 (capture-tasks-from-meeting-notes / spec-to-backlog / search-company-knowledge / triage-issue / generate-status-report)
4. MCP 도구 `mcp__plugin_atlassian_atlassian__*` 호출 직전

위 조건 미충족 → **호출 자체 없음** (Atlassian 안 쓰는 프로젝트 부하 0).

### 호출 방식 (조건 충족 시만)

```bash
# Universal path (모든 PC 동일 작동 — Layer B path_resolution 활용)
python "$HOME/.claude/hooks/atlassian_auth.py"
# Windows: %USERPROFILE%\.claude\hooks\atlassian_auth.py
```

executor 가 verdict 산출:
- `PASS_THROUGH` → 조용히 진행
- `AUTO_REFRESH` → plugin MCP 자체 refresh 위임
- `ESCALATE` → `atlassian-auth-advisor` 자동 호출 (사용자가 Lead에게 위임)
- `BLOCKED_BY_BREAKER` → 사용자에게 차단 사유 1줄 안내

### 사용자 노출 매트릭스

| 상황 | 사용자 진입점 |
|------|:-----------:|
| Atlassian 미사용 프로젝트 | 0회 (호출 자체 없음) |
| Atlassian 사용 + 정상 | 0회 (PASS_THROUGH silent) |
| Atlassian 사용 + token stale | 0회 (AUTO_REFRESH 백그라운드) |
| Atlassian 사용 + 401 누적 | 1회 (PROMPT_USER → `/mcp` 1회 실행) |

상세: `docs/00-prd/aiden-auto-atlassian-mcp-auth-automation.prd.md` v1.1+ (project-relative path).

## 전제 조건 자동 검증

Part C 활성화 시 자동 확인:
- 환경변수 `ATLASSIAN_EMAIL` + `ATLASSIAN_API_TOKEN` 설정 여부
- `CONFLUENCE_BASE_URL` (default: https://ggnetwork.atlassian.net/wiki)
- `lib/confluence/md2confluence.py` 존재 여부

부재 시: Part C 자동 skip + 사용자 알림. 다른 Part 는 계속.

Part C 활성화 시 Part E 도 자동 충족 (Confluence sync = Atlassian 인증 필요).

## Phase 4 Close 동작 연동

`confluence_sync.enabled = true` 시 Phase 4 의 4.2 단계에서 자동 호출:

```bash
# Project-relative path (Layer B path_resolution 활용)
python "$PROJECT_ROOT/lib/confluence/md2confluence.py" <md_file> <page_id>
```

상세: `references/confluence-sync-flow.md`.

## 자료

| 항목 | 위치 |
|------|------|
| brainstorming skill | `superpowers:brainstorming` |
| multi-session | `references/multi-session-router.md` (또는 plugin) |
| Confluence 흐름 | `references/confluence-sync-flow.md` |
| md2confluence 도구 | `$PROJECT_ROOT/lib/confluence/md2confluence.py` (project-relative) |
| Executive Summary | `references/executive-summary-template.md` |
