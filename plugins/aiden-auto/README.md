# aiden-auto v28.2

> Index Router + /goal-based loop + Deep Interview + Multi-Session orchestrator for Claude Code.
> v28.2 — 사용자 진입점 최소화 + 자율 이터레이션 최대화.

## 설치

```
/plugin marketplace add garimto81/aiden-auto
/plugin install aiden-auto@garimto81-aiden-auto    # ← 하이픈(-) 주의
/reload-plugins
```

> **주의**: install 명령어의 `@` 뒤는 **`garimto81-aiden-auto`** (하이픈) 이지
> `garimto81/aiden-auto` (슬래시) 가 아닙니다.
> `marketplace add` 단계에서 GitHub repo 경로 (`owner/repo`) 가
> marketplace 이름 (`owner-repo`) 으로 자동 변환되기 때문입니다.

## 빠른 시작

작업을 평문으로 말하기만 하면 됩니다. `/auto` 입력 불필요.

```
"로그인 API 만들어줘"        → 자동으로 code chapter 실행
"이 PRD 분석해줘"            → 자동으로 doc chapter 실행
"테스트 깨진 거 고쳐줘"       → 자동으로 qa chapter 실행
"기능 개선 반복해줘"          → 자동으로 iteration chapter 실행
```

## 환경변수 (자동 주입, 알아두면 좋음)

Claude Code 가 hook 실행 시 자동으로 주입하는 환경변수입니다. 별도 설정 불필요.

| 변수 | 의미 | plugin 사용 패턴 |
|------|------|----------------|
| `CLAUDE_PLUGIN_ROOT` | plugin 본체 위치 | hook 스크립트 경로 결정 |
| `CLAUDE_PROJECT_DIR` | 현재 사용자 프로젝트 디렉토리 | state 파일, 로그, deploy-config 경로 결정 |

plugin 의 모든 Python 파일이 이 두 변수를 우선 참조하고, 없으면 `__file__` 또는 `os.getcwd()` 로 fallback 합니다.

**v28.2 이후 하드코딩된 `C:/claude` 경로는 모두 제거**되어 어느 PC, 어떤 사용자명 (공백 포함도 OK) 에서도 작동합니다.

## Statusline

본 plugin 은 hot reload 직후 statusline 을 자동 활성화합니다.

- `~/.claude/hud/` 폴더가 있으면 그대로 사용 (외부 도구 그대로 유지 원칙)
- 없으면 plugin 내장 statusline 을 `settings.json` 의 `statusLine` 키에 자동 주입
  (비파괴 — 기존 statusLine 이 있으면 건드리지 않음)

수동 비활성화: `settings.json` 의 `statusLine` 키 제거 후 `/reload-plugins`.

## 프로젝트 종속 hook — 자동 배포 (auto_deploy)

`auto_deploy.py` Stop hook 은 **프로젝트별 `.claude/deploy-config.json` 이 있을 때만** 작동합니다.
파일이 없으면 조용히 아무것도 하지 않습니다 (silent noop).

```
프로젝트 루트/
└── .claude/
    └── deploy-config.json    ← 이 파일이 있어야만 자동 배포 활성화
```

예시 파일 위치: `config/profiles/deploy-config.example.json`

```json
{
  "watch_paths": ["server/", "src/"],
  "docker_compose": "docker-compose.yml",
  "health_check": "http://localhost:8000/health",
  "flutter_dir": "my_app_flutter",
  "flutter_prefix": "my_app_flutter"
}
```

자신의 프로젝트 루트 `.claude/deploy-config.json` 에 복사 후 환경에 맞게 수정하면 됩니다.

## 핵심 컴포넌트

| 종류 | 개수 | 위치 |
|------|:----:|------|
| Skills | 22 | `skills/` |
| Agents | 44 | `agents/` |
| Hooks | 31 | `hooks/` |
| Rules | 8 | `rules/` |
| References | 44 | `references/` |
| Commands | 21 | `commands/` |
| Lib | 17 | `lib/` |
| Config | 4 | `config/` |

## 5가지 핵심 원칙

1. 외부 harness framework 그대로 유지 (참조만, 복사 안 함)
2. 외부 update 자동 critic → 자가개선 (`harness-watcher/critic/applier`)
3. SKILL.md 최소 진입점 (≤120줄, lazy load only)
4. Intent → Chapter 라우팅 (1 chapter = 1 reference 로딩)
5. 스킬/커맨드/워크플로우 = 방대 (슈퍼앱)

## 구조

```
aiden-auto/
├── skills/        22  (auto 진입점 ≤120줄 + chapter 22)
├── agents/        44  (iteration 13 + verification 4 + creative 2 +
│                       meta 5 [harness-watcher/critic/applier 포함] +
│                       core/domain 10 + v28.2 신규 10)
├── hooks/         31  (auto_deploy + goal_stop_evaluator + event_dispatcher 등)
├── rules/          8  (rule 16 auto-trigger + rule 17 Circuit Breaker + 6)
├── references/    44  (chapter 6 + phase 5 + v28.2 신규)
├── commands/      21
├── lib/           17  (calendar/figma/gmail/jira/slack/confluence + adapters + sessions)
└── config/         4  (platform-detect, project-profiles, eco-modes, feature-flags)
```

## v28.2 신규 기능

| 기능 | 설명 |
|------|------|
| **Goal Loop Driver** | Stop hook + `/goal` command. 목표 달성까지 자율 루프 |
| **Deep Interview** | Phase -1.5 (`agents/core/intake-interviewer.md`). 모호 요청 자율 명세화 |
| **Multi-Session Router** | 세션 유형 분류 + 자동 재개 (`agents/meta/multi-session-router.md`) |
| **Perfect Output Gate** | 4단계 (Gate 1 validator → Gate 2 e2e-qa-prover → Gate 3 submission → Gate 4 BLOCK) |
| **Adaptive Framework** | 5 adapter + feature flags (`lib/adapters/`, `config/feature-flags.yml`) |
| **Progress Hooks** | events.jsonl + HMAC + DLQ (`lib/sessions/event_schema.py`) |
| **Portability** | `CLAUDE_PLUGIN_ROOT` / `CLAUDE_PROJECT_DIR` 기반. 하드코딩 경로 전면 제거 |

## Rule 19 — Plugin SSOT (단일 정본 원칙)

이 plugin 은 두 로컬 mirror 가 SHA256 일치해야 합니다.

```
외부 GitHub (SSOT)
    https://github.com/garimto81/aiden-auto  (main branch)
         │
         ├── Mirror 1 (Claude Code 로드)
         │   ~/.claude/plugins/marketplaces/garimto81-aiden-auto/plugins/aiden-auto/
         │
         └── Mirror 2 (git 추적, 개발)
             C:/claude/plugins/aiden-auto/  (또는 사용자별 clone 위치)
```

drift 감지: `plugin-ssot-audit` skill 실행.

## 환경 호환성

| 환경 | 지원 |
|------|:----:|
| Windows (사용자명 공백 포함) | O |
| Windows (사용자명 공백 없음) | O |
| macOS | O |
| Linux native | O |
| Linux WSL (`/mnt/c/...`) | O |

## 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| `Marketplace not found` | install 시 `owner/repo` (슬래시) 형식 사용 | `aiden-auto@garimto81-aiden-auto` (하이픈) 으로 install |
| Stop hook `Failed with non-blocking status code` | v28.2 이전 잔존 경로 문제 | `/plugin marketplace update garimto81-aiden-auto` |
| statusline 미표시 | settings.json 에 statusLine 키 부재 | SessionStart hook 이 자동 주입. `/reload-plugins` 후 새 세션 시작 |
| `Plugin directory does not exist` | marketplace cache race | `/plugin marketplace update garimto81-aiden-auto` + `/reload-plugins` |
| auto_deploy 가 실행되지 않음 | `.claude/deploy-config.json` 없음 | 프로젝트 루트 `.claude/deploy-config.json` 생성 (예시: `config/profiles/deploy-config.example.json`) |
| 경로 오류 (하드코딩 `C:/claude` 잔존) | v28.1 이하 버전 | marketplace update 후 `/reload-plugins` |

## 라이선스

MIT

## 작성자

garimto81 (garimto1981@gmail.com)

---

## 변경 이력

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v28.2 | 2026-05-13 | Portability 전면 수정. `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PROJECT_DIR` 기반. 하드코딩 경로 제거. Goal Loop / Deep Interview / Multi-Session / Perfect Output Gate / Adaptive Framework / Progress Hooks 신규. README 설치 가이드 갱신 |
| v28.1 | 2026-05-11 | SKILL.md 311→190줄. harness-watcher/critic/applier 신규. hook 차단 해소. 메타 4파일 동기화 |
| v28.0 | — | Index Router 아키텍처 기반. chapter 라우팅 확립 |
