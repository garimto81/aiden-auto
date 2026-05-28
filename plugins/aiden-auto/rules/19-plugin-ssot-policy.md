# Plugin SSOT (Single Source of Truth — 단일 정본) 정책 v2.0

**상태**: REVIVED v2.0 (2026-05-14)
**최초 제정**: 2026-05-12 (v1.0) | **v2.0 재작성**: 2026-05-14

---

## v1.0 폐기 경과 + v2.0 해결 방식

v1.0은 `~/.claude/plugins/marketplaces/…/plugins/aiden-auto/` 가 CC(Claude Code) 런타임
로드 위치라고 잘못 가정했다. 그 결과 drift(차이) 감지와 SHA256(파일 지문 알고리즘) 비교가
모두 엉뚱한 위치를 추적해왔다.

2026-05-14 진단 결과:
- **실제 CC 로드 위치**: `~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/28.3.0/`
- **marketplaces/** 폴더: marketplace 메타데이터 저장소일 뿐 (`.git` + `marketplace.json`)
- **정본**: `~/.claude/` (CC가 직접 읽는 agents, skills, hooks, rules, commands, references)
- `framework_edit_guard.py`가 이미 "plugin은 read-only auto-mirror, 정본은 `~/.claude/`"를 강제하고 있음

v2.0은 이 실제 구조를 정책에 반영한다.

---

## 한 줄 정책

> **정본 `~/.claude/` ↔ Project `C:\claude\.claude\` 양방향 sync (Plan B) + Plugin 3 mirror 단방향 수신. 실제 git 배포 repo = `C:\aiden-auto-repo` (총 6 물리 위치). 편집은 정본/Project 어디서나 — Plugin layer 만 read-only (framework_edit_guard 차단).**
>
> *(P4 정정 2026-05-28: 옛 "정본 1곳 → mirror 3곳, 편집 정본에만" 은 단방향 뉘앙스였으나 실제는 v3.2 Plan B 양방향. "정본"은 논리적 개념 — 물리적으로는 peer mirror 양방향 + Plugin 단방향 + 별도 배포 repo.)*

---

## 도서관 비유

`~/.claude/` 와 Project `C:\claude\.claude\` 는 **두 본관**이다 — 어느 본관에서 고쳐도
다른 본관에 자동 양방향 배달(Plan B sync). Plugin 3 mirror 는 **분관** — 본관 책 복사
수신 전용 (분관에서 고치면 framework_edit_guard 가 차단). 실제 출판 원본(git 배포)은
별도 `C:\aiden-auto-repo` 다. 총 6 물리 위치.

---

## 4-Mirror 구조 다이어그램

```
  ┌─────────────────────────────────────────┐
  │  정본 (SSOT)                            │
  │  ~/.claude/                             │
  │  agents/ skills/ hooks/ rules/          │
  │  commands/ references/                  │
  └──────────────┬──────────────────────────┘
                 │
        자동 sync (machine_framework_watcher.py)
        PostToolUse Edit/Write 트리거
                 │
     ┌───────────┼───────────────┐
     ▼           ▼               ▼
  Mirror 1    Mirror 2        Mirror 3
  C:\claude\  ~/.claude/      ~/.claude/plugins/
  plugins\    plugins/cache/  marketplaces/
  aiden-auto\ garimto81-      garimto81-aiden-auto/
              aiden-auto/     plugins/aiden-auto/
              aiden-auto/
              28.3.0/
              (CC 실제 로드)   (메타데이터만)
```

---

## Mirror 별 편집 권한

| 위치 | 역할 | 편집 가능? | 비고 |
|------|------|:---------:|------|
| `~/.claude/` | 정본 | **YES** | 모든 변경의 시작점 |
| `C:\claude\plugins\aiden-auto\` | Mirror 1 — auto-sync 수신 전용 (git-free) | READ-ONLY | **git 추적 안 됨** (ls-files=0, 자체 .git 없음). 실제 git 배포 repo 는 `C:\aiden-auto-repo` (origin=garimto81/aiden-auto.git) — framework_github_sync.py 가 사용 |
| `~/.claude/plugins/cache/…/28.3.0/` | Mirror 2 — CC 로드 | READ-ONLY | auto-sync 수신 전용 |
| `~/.claude/plugins/marketplaces/…/` | Mirror 3 — 메타 | READ-ONLY | marketplace.json만 관리 |

`framework_edit_guard.py`가 Mirror 1/2/3에 대한 직접 Edit/Write를 자동 차단한다.

---

## Sync 메커니즘 (v3.6 정합 — Plan B v2.0 반영)

| 도구 | 발동 시점 | 방향 | 책임 |
|------|----------|------|------|
| `bidirectional_sync.py` v2.0 | PostToolUse Edit/Write (Plan B 단독) | Global ↔ Project (**양방향**) + Global → Plugin (단방향) | 5 mirror 단독 처리 (v3.3 도입) |
| `machine_framework_watcher.py` | PostToolUse Edit/Write/MultiEdit | Global → Mirror 1/2/3 (백업 layer) | "제거 ≠ 답" 정책으로 보존 |
| `framework_edit_guard.py` | PreToolUse Edit/Write | — | Mirror 직접 편집 차단 |
| `plugin-ssot-audit` skill | 명시 호출 또는 audit-loop cycle 1 | 보고만 | drift 감지 + JSON 보고 |

**sync 방향 (v3.6 정의)**:
- **Project ↔ Global**: **양방향** (Plan B v2.0 — `bidirectional_sync.py`)
- **Global → Plugin (source / cache / marketplaces)**: 단방향
- **Plugin → Global / Project**: 없음 (Plugin layer 는 read-only)

> 옛 v2.0 본문의 "단방향 sync — 정본 → Mirror" 정의는 **v3.2 (Plan B 도입, 2026-05-15)** 으로 변경됨. v3.6 (2026-05-19) 이 본 표를 실제 코드 (`bidirectional_sync.py` 의 `determine_source_and_dests`) 와 정합화.

### EXCLUDE 정책 (Layer 독립성 보호 — v3.7 갱신)

다음 파일들은 Layer 간 sync 차단 — 각 layer 의 독립 정의를 보호:

| 파일 패턴 | 이유 |
|----------|------|
| `settings.json` / `settings.local.json` | 각 layer 의 hook 등록 / 권한 / env 는 독립 — dispatcher pattern 도입 후 핵심 |
| `CLAUDE.md` | 각 layer 의 instructions 독립 (Global vs Project) |
| `.env` / `.env.local` / `.credentials.json` | 환경 변수 / secret 은 layer 간 공유 금지 |
| `_silent_wrap.cmd` / `_silent_wrap.cmd.bak` | **wrapper 본문이 어떤 layer 에서 변경되어도 다른 layer 로 자동 전파되지 않도록 차단** (v3.7 critic Agent B R6 — lock 폭탄 자동 복귀 사례 방지) |

→ `bidirectional_sync.py` 의 `EXCLUDE_FILE_NAMES` 와 정합 (소스 정본).

### Deregistration vs Code Removal — 구분 정책 (v3.7 신규)

**핵심 원칙**: "Removal isn't the answer" 패러다임은 **코드 제거** 금지를 의미. **등록 deregistration** 은 별개 — 정당하며 권장될 수 있다.

| 행위 | 의미 | 패러다임 부합? |
|------|------|:------------:|
| hook 파일 자체 삭제 | code removal | ❌ 금지 |
| hook 파일 본문 변경 | code modification | ⚠️ 신중 |
| settings.json hooks 섹션에서 등록 제거 | deregistration | ✅ 허용 (특히 dispatcher pattern 도입 후 정리 시) |
| Plugin manifest 의 hook 등록 제거 | deregistration | ✅ 허용 |
| Project settings.json 의 wrapper hook 제거 (dispatcher 로 통합 시) | deregistration | ✅ 권장 |

본 cycle Phase 4a 에서 Project settings.json 의 Stop event 의 `auto_deploy` + `post_commit_quality` 등록 제거는 **deregistration** — 패러다임 위배 X.
이유: 두 hook 의 파일 자체는 Global + Plugin layer 에 보존. Plugin manifest 가 자체 등록 → 기능 손실 0. 단지 double-fire 차단 목적의 등록 정리.

---

## 편집 워크플로우

```
  사용자 / Claude 편집
         │
         ▼
  ~/.claude/ (정본) 파일 수정
         │
         ▼
  machine_framework_watcher.py 자동 발동
         │
         ├──► Mirror 1 (C:\claude\plugins\aiden-auto\)
         ├──► Mirror 2 (~/.claude/plugins/cache/…/28.3.0/)
         └──► Mirror 3 (~/.claude/plugins/marketplaces/…/)

  [Mirror 직접 편집 시도]
         │
         ▼
  framework_edit_guard.py 차단 → 정본 경로 안내
```

---

## 위반 감지 + 자동 정정

`plugin-ssot-audit` skill이 감지하는 항목:

| 코드 | 의미 | 자율 정정 가능? |
|------|------|:--------------:|
| DRIFT | 같은 경로, SHA256 불일치 | YES — 정본 기준으로 덮어쓰기 |
| MIRROR_ONLY | Mirror에만 있는 파일 | YES — 정본에 없으면 제거 |
| CANON_ONLY | 정본에만 있는 파일 | YES — Mirror에 sync |
| RUNTIME_ARTIFACT | `__pycache__/`, `*.pyc` | YES — 즉시 제거 |

사용자 결정 영역: 정책 충돌이 의심되거나 삭제 대상 파일이 200줄+ 인 경우 → 보고만, 자동 삭제 금지.

---

## GitHub repo 위상 (v3.8 정정 — 2026-05-28)

`https://github.com/garimto81/aiden-auto` 의 **실제 로컬 클론은 `C:\aiden-auto-repo`** 다
(`C:\claude\plugins\aiden-auto\` 가 **아니다** — 그 폴더는 git ls-files=0, 자체 .git 없음, 잡힌 remote 는 무관 repo).
**정본이 아니다.** 변경 흐름:

```
정본 ~/.claude/ ─(framework_github_sync.py v6)→ C:\aiden-auto-repo\plugins\aiden-auto\
                                                      │
                                                      └─ git commit + push → GitHub (배포원)

정본 ~/.claude/ ─(bidirectional_sync + watcher)→ Mirror 1 C:\claude\plugins\aiden-auto\
                                                  (git-free 부분 mirror — 증분 sync 수신)
```

GitHub 배포원 = `C:\aiden-auto-repo` (신규 PC 자기복제의 원천). Mirror 1
(`C:\claude\plugins\aiden-auto\`) 은 git 추적 안 되는 별개의 sync 수신 폴더이며 CC 로드 경로도 아니다 (cache 가 로드).

---

## 책임 매트릭스 (Responsibility Matrix) — v3.0 신규

각 영역이 **무엇을 가지는지 + 무엇을 가지지 않는지** 명확화.

| 영역 | 가지는 것 | 가지지 않는 것 |
|------|----------|---------------|
| **Project** (`C:\claude\.claude\`) | 이 프로젝트만의 rules, settings.json, project-only hooks (4개), project audit skills | commands, agents (Global이 정본) |
| **Global** (`~\.claude\`) ⭐ 정본 SSOT | commands, agents, skills, hooks, rules, references | 프로젝트별 override (Project로 위임) |
| **Plugin** (`C:\claude\plugins\aiden-auto\`) | 외부 framework — 자체 완결 패키지 | 사용자 customization (Global로 위임) |

### Resolution Priority (CC 호출 시 추정 순서)

```
   사용자 입력 (/audit 등)
        │
        ▼
   ① Project lookup  ──► 발견 시 실행
        │
        ▼ (Project 부재)
   ② Global lookup   ──► 발견 시 실행
        │
        ▼ (Global 부재)
   ③ Plugin lookup   ──► plugin enabled 시 실행
```

### 같은 이름 entity 다중 존재 정책 (v3.1 — 포함 패러다임)

**핵심 원칙 (사용자 결정 2026-05-15)**: **제거가 답이 아니다. 모든 mirror 를 유지하되 의미를 부여한다.**

> 비유: 본관 + 분관 3 곳 모두 같은 책 보관. 제거하면 나중에 빠뜨림. 대신 각 분관의 역할 명시.

| 시나리오 | 정책 (v3.1) | 자동 처리 |
|---------|-------------|----------|
| Project + Global, SHA 동일 | **유지** — Project = 자동 mirror | 정기 SHA 검증만 (drift 감지 후 동기화) |
| Project + Global, SHA 다름 | **유지** — Project override 의도 | drift 감지 → 사용자 결정 시 동기화 |
| Global + Plugin, SHA 동일 | **유지** — watcher sync 결과 | 자동 |
| Global + Plugin, SHA 다름 | drift | 다음 Edit 시 watcher 가 자동 정정 (~/.claude/ 정본) |

### v3.1 패러다임 전환 — "제거 → 포함"

| 옛 패러다임 (v3.0, 폐기) | 새 패러다임 (v3.1) |
|------------------------|------------------|
| Project commands "dead copy 자율 삭제" | Project commands 유지 — 자동 mirror 의미 부여 |
| phantom hook "제거" | phantom hook 유지 — 코멘트로 의도 명시 |
| deprecated entity "삭제" | deprecated entity 유지 — 알림으로 의도 명시 |

**이유**: 제거하면 나중에 누군가 호출 시 부재. 유지하면 의미 부여로 자율 가능.

### 강제 메커니즘 (Deterministic)

`~/.claude/scripts/spec-verify.py` (LLM-free deterministic verifier) 가 다음 위반 자동 감지:

- Layer 2 검사: 3축 mirror 일관성 (SHA drift 감지)
- Layer 3 검사: 정책 본문 ↔ guard/watcher 코드 일치 → drift 감지

비파괴 정리 자동 가능. 의미 차원 결정만 사용자에게 escalate.

---

## Plan B — 양방향 Sync 메커니즘 (v3.2 신규)

**핵심 원칙 (사용자 결정 2026-05-15)**: 단일 정본 SSOT 불가 시 → **양방향 sync 로 모든 변경 자동 전파**.

> 비유: 본관 ↔ 분관 1 양방향 자동 배달. 분관 2/3 은 본관에서 받기만 (편집 차단).

### 양방향 sync 흐름

```
   ┌──────────────────────────────────────────────────┐
   │  Project (C:\claude\.claude\) ←──┐               │
   │       │                          │               │
   │       │ Edit                     │ 양방향        │
   │       ▼                          │ sync          │
   │  bidirectional_sync.py ◀─────────┘               │
   │       │                                          │
   │       ▼                                          │
   │  Global (~/.claude/) ──┐                         │
   │                        │ 단방향 sync             │
   │                        │ (기존 watcher)          │
   │                        ▼                         │
   │                  Plugin (cache/marketplaces)     │
   │                  (수신만 — 편집 차단)            │
   └──────────────────────────────────────────────────┘
```

### 등록 위치

| Hook | 위치 | 매처 |
|------|------|------|
| `bidirectional_sync.py` | `~/.claude/hooks/bidirectional_sync.py` | PostToolUse `Edit\|Write` |
| `machine_framework_watcher.py` | `~/.claude/hooks/machine_framework_watcher.py` | PostToolUse `Edit\|Write\|MultiEdit` (기존) |

### 방어 3중 (Critic 검토 결과)

| 위험 | 방어 |
|------|------|
| **Loop** (A→B→A 무한) | SHA256 비교 — dest 와 SHA 동일하면 skip |
| **Race condition** | mtime newest — dest 가 source 보다 newer 면 skip (다른 곳에서 더 최근 편집 보존) |
| **Self-edit recursion** | `is_self_edit()` — watcher/sync hook 자체 제외 |

### v3.2 패러다임 — "Plan B = 사용자 진입점 0"

| 시나리오 | v3.2 동작 |
|---------|----------|
| 사용자가 Project 에서 Edit | bidirectional_sync.py 가 Global 로 자동 mirror → watcher 가 Plugin 으로 자동 mirror |
| 사용자가 Global 에서 Edit | bidirectional_sync.py 가 Project 로 자동 mirror + watcher 가 Plugin 으로 자동 mirror |
| Plugin 변경 시도 | `framework_edit_guard.py` 차단 — 정책 유지 |

→ **사용자는 어디서든 편집. 다른 두 곳은 자동 mirror**. Plan B 달성.

---

## Plan B v2.0 — 5 Mirror 통합 책임 (2026-05-15 QA 결과)

**배경**: Plan B v1.0 의 QA 시나리오 1-2 결과 — `bidirectional_sync.py` 는 Project ↔ Global 양방향 작동했으나, `machine_framework_watcher.py` 가 `Edit` 도구 발동 시 호출 안 됨 확인.

**원인 추정**: project `settings.json` 의 `PostToolUse Edit|Write` 매처가 global `settings.json` 의 `Edit|Write|MultiEdit` 매처를 override.

**v2.0 자율 정정**: `bidirectional_sync.py` 가 watcher 책임도 흡수 → **5 mirror 단독 처리**.

### v2.0 sync 책임 매트릭스

| Hook | 처리 mirror | 의존 |
|------|------------|------|
| `bidirectional_sync.py` v2.0 (Plan B 단독) | Project + Global + Plugin source + cache + marketplaces (5개) | 독립 — watcher 의존 0 |
| `machine_framework_watcher.py` (보존) | 동일 5 mirror (백업 layer) | "제거 ≠ 답" 정책에 따라 보존. Plan B 미작동 시 fallback |

### 양 hook 중복 등록 정책

- 같은 도구 호출 시 두 hook 모두 발동 가능
- `sync_one()` 의 SHA256 비교로 두 번째 호출 시 `skip_same` 처리
- 실제 sync 는 한 번만 발생 (성능 영향 없음)

→ "Removal isn't the answer" 원칙 일관 적용. 두 layer 보존, 중복 안전.

### QA 통과 증거 (2026-05-15)

```
Scenario 1: Global Edit (work.md) → Project + Plugin sync ✅
Scenario 2: Project Edit → Global + Plugin sync ✅
Scenario 3: Plugin Edit 시도 → framework_edit_guard 차단 ✅
3축 SHA256: 모두 동일 (87533d13f6337207)
spec-verify: 100.0 / 100 PASS
```

---

## 적용 예외 (v3.5 — 2026-05-15 Part 9 critic 반영)

아래 디렉토리/파일은 sync 대상에서 영구 제외 (bidirectional_sync.py EXCLUDE_DIR_NAMES + EXCLUDE_FILE_SUFFIXES 와 정합):

**디렉토리 (이름 기반)**:
- `node_modules/` — JS/TS 의존성 (1만개+ 파일 5축 sync 폭발 방지)
- `__pycache__/` — Python 바이트코드 캐시
- `dist/`, `build/` — 빌드 산출물
- `.venv/`, `venv/` — Python 가상환경
- `.next/` — Next.js 빌드
- `.git/` — git 내부 데이터
- `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` — 캐시류
- `coverage/`, `htmlcov/` — 커버리지 산출물

**파일 (suffix 기반)**:
- `*.pyc`, `*.pyo` — Python 컴파일 산출물
- `*.log` — 로그 파일
- `*.swp`, `*.swo` — vim swap

**기존 (유지)**:
- `state/runtime.yml` — 세션별 런타임 상태

---

## 금지 사항

- Mirror 1/2/3 직접 편집 금지 (`framework_edit_guard.py` 차단)
- 정본 없이 Mirror만 수정 후 방치 금지 (drift 누적)
- Mirror 2(cache/) 버전 디렉토리 임의 삭제 금지 (CC 로드 불가)
- sync 방향 역전 (Mirror → 정본) 금지

---

## 관련 파일

| 역할 | 경로 |
|------|------|
| 정본 SSOT | `~/.claude/` |
| Mirror 1 (git 추적) | `C:\claude\plugins\aiden-auto\` |
| Mirror 2 (CC 로드) | `~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/28.3.0/` |
| Mirror 3 (메타데이터) | `~/.claude/plugins/marketplaces/garimto81-aiden-auto/plugins/aiden-auto/` |
| 편집 차단 | `machine_framework_watcher.py` — `framework_edit_guard.py` |
| Audit skill | `C:\claude\.claude\skills\plugin-ssot-audit\` |
| 본 정책 | `C:\claude\.claude\rules\19-plugin-ssot-policy.md` |

---

## 변경 이력

| 날짜 | 버전 | 변경 | 사유 |
|------|------|------|------|
| 2026-05-12 | v1.0 | 최초 작성 | drift 36 + 누락 166 + audit 분석 모순 발견 |
| 2026-05-14 | v1.0 → DEPRECATED | marketplace 경로 오인 확인 | 실제 CC 로드 위치는 cache/, marketplaces/는 메타만 |
| 2026-05-14 | v2.0 REVIVED | `~/.claude/` 정본 명시화 + 4-Mirror 구조 재설계 | `framework_edit_guard.py` 강제 정책과 일치 |
| 2026-05-15 | v3.0 | 책임 매트릭스 + Resolution Priority 추가 | 3축 entity 위치 규정 |
| 2026-05-15 | v3.1 | 포함 패러다임 — "제거 ≠ 답" | 사용자 결정. Project mirror 자동 유지 |
| 2026-05-15 | v3.2 | Plan B 양방향 sync hook 신규 | bidirectional_sync.py 도입 |
| 2026-05-15 | v3.3 | Plan B v2.0 — 5 mirror 통합 책임 | watcher 미작동 QA 발견, hook 자체 흡수 |
| 2026-05-15 | v3.4 | 정책 범위 = aiden-auto 전용 명시 + multi-session-router 의도 명문화 | 사용자 결정 1A, 5A 적용 |
| 2026-05-18 | v3.5 | 본문 cache 경로 28.2.0 → 28.3.0 갱신 (6곳) | audit-loop critic review 자율 정정. plugin v28.3.0 실제 버전 정합 |
| 2026-05-19 | v3.6 | Sync 메커니즘 표 v3.2 정합화 (단방향 → 양방향) + EXCLUDE_FILE_NAMES 명시 (settings.json / CLAUDE.md / .env) | Single Dispatcher Pattern critic Agent B S5/S9 자율 정정. layer 독립성 보호 + 정책 본문 vs 실제 코드 일치 |
| 2026-05-19 | v3.7 | EXCLUDE 에 `_silent_wrap.cmd` 추가 + Deregistration vs Code Removal 구분 정책 신규 | critic Agent B R6 (wrapper lock 폭탄 자동 복귀) + Agent A C1 (Phase 4a "Removal" 위배 정당화) 자율 정정 |
| 2026-05-28 | v3.8 | Mirror 1 정의 정정 ("git 추적" → "auto-sync 수신 전용 git-free") + GitHub repo 위상 정정 (실제 배포 repo = `C:\aiden-auto-repo`, Mirror 1 은 git ls-files=0) | critic NOT-A-GHOST 판정. 증분 sync 만으로 부분 mirror (1036 파일 누락) 발견 → reconcile-plugin-mirror.py 로 완전화 + bidirectional_sync global registry 등록 |
| 2026-05-28 | v3.9 | P4 정정 — 한 줄 정책 + 도서관 비유 양방향 정합 (단방향 뉘앙스 → Plan B 양방향 + 6 물리 위치 + aiden-auto-repo 배포 명시) + R3 전면 — registry json 15개 command `C:/Users/AidenKim` → `$HOME` device-agnostic | /auto autonomous iteration — P1/P6 후속 잔여 정리 |

---

> **한 줄 요약**: 정본은 `~/.claude/` 하나. 나머지 3곳은 자동 mirror. 편집은 정본에서만, sync는 자동.

---

## v3.4 신규 — 정책 범위 + Deprecated Entity 의도 (2026-05-15)

### 정책 범위 명시 (사용자 결정 1A 적용)

**본 SSOT 정책 = `aiden-auto` plugin 전용**.

다른 plugin 14개 (vercel, atlassian, slack, superpowers, frontend-design, claude-code-setup, skill-creator, code-review, feature-dev, figma, supabase, code-simplifier, explanatory-output-style, ralph-loop) 는 본 정책 적용 안 됨.

이유:
- `framework_edit_guard.py` 의 `PROTECTED_PATHS` 가 aiden-auto 만 보호
- `machine_framework_watcher.py` 의 `PROJECT_SOURCE` / `CACHE_ROOT` / `MARKETPLACES` 가 aiden-auto 만 sync
- 다른 plugin 은 외부 framework — 별도 정책 cycle 필요 (현재 미정)

### Deprecated Entity — multi-session-router (사용자 결정 5A 적용)

**현재 상태**: `~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/28.3.0/agents/meta/multi-session-router.md` 에 cache 잔존. `~/.claude/agents/meta/` 에는 부재.

**의도**: Plugin CLAUDE.md 에 "폐기 예정 (multi-session 운영은 공식 claude agents CLI 위임)" 명시되었으나, 패러다임 **"제거 ≠ 답"** 일관 적용 → cache 잔존 유지.

**처리 정책**:
- `~/.claude/agents/meta/` 에 복원 안 함 (의도된 cache-only 상태)
- cache 직접 제거 안 함 ("Removal isn't the answer" 사용자 결정 보존)
- framework 가 호출 시도 시 cache 에서 로드 (기존 동작 유지)
- 영구 폐기 결정은 plugin v28.3+ release 에서 (별도 cycle)

→ **v3.4 = 정책 범위 명시 + deprecated entity 의도 명문화. 본 cleanup cycle 자율 영역 마지막 작업.**
