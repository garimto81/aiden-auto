---
name: code-atlas
description: AI 코딩 환각(hallucination)을 로컬에서 시각적으로 검증하는 도구. 사용 - /code-atlas [path] 로 타겟 디렉토리 분석 후 브라우저에서 4분할 맵으로 확인. Supabase/계정 없이 동작. TypeScript/JavaScript 프로젝트 지원. H1(존재하지 않는 import), H3(빈 껍데기 함수), H4(의미적 중복), H7(UI→API→DB 단절) 감지.
---

# Code Atlas — Local AI Hallucination Verification

AI 가 생성한 코드에서 환각을 찾아내어 비개발자가 시각적으로 검증하고 수정 지시를 내릴 수 있게 해 주는 로컬 도구.

## 사용법

- `/code-atlas` — 현재 작업 디렉토리 분석
- `/code-atlas /path/to/project` — 특정 디렉토리 분석
- `/code-atlas . --no-open` — 분석만 하고 브라우저는 열지 않음
- `/code-atlas . --port 4321` — 포트 지정

## 감지 유형

| ID | 유형 | 설명 | 기법 |
|:---:|------|------|------|
| **H1** | Phantom Reference | import/호출한 모듈·심볼이 실제로 존재하지 않음 | ts-morph 심볼 resolve |
| **H3** | Hollow Stub | 선언만 있고 본문이 `return null` / TODO 인 함수 | AST heuristic |
| **H4** | Silent Duplicate | 같은 역할을 하는 함수가 여러 파일에 중복 | Jaccard AST similarity |
| **H7** | Dangling Edge | UI→API 선언은 있으나 API 가 실제 DB 에 닿지 않음 | Next.js call graph |

## 동작 순서 (Claude Lead 가 실행할 명령)

사용자가 `/code-atlas [path]` 를 입력하면 Claude 는 다음을 수행한다:

0. **스킬 디렉토리**: `~/.claude/skills/code-atlas/` (Windows: `C:/Users/<USER>/.claude/skills/code-atlas/`). 아래 스텝의 `<SKILL_DIR>` 는 이 경로를 가리킨다.
1. **타겟 디렉토리 결정**: `[path]` 가 주어지면 `resolve()` 후 절대 경로로 변환. 없으면 현재 작업 디렉토리 (`pwd`) 사용.
2. **스킬 의존성 확인**: `<SKILL_DIR>/node_modules/tsx` 가 없으면 `cd <SKILL_DIR> && npm install --no-audit --no-fund` 를 먼저 실행
3. **분석 실행** (반드시 스킬 디렉토리에서 실행해야 tsx 가 resolve 됨):
   ```
   cd <SKILL_DIR> && node --import tsx scripts/cli.ts <ABSOLUTE_TARGET_PATH>
   ```
   실제 명령 예시:
   ```
   cd C:/Users/AidenKim/.claude/skills/code-atlas && node --import tsx scripts/cli.ts C:/claude/project_master/frontend
   ```
4. 표준 출력의 진행률을 그대로 사용자에게 흘려준다. `complete` 출력 후 브라우저가 자동 오픈됨
5. 사용자는 4-pane UI 에서 환각 노드 확인 → 증거 패널 → Claude 프롬프트 복사

### 플래그

- `--no-open` 브라우저 자동 오픈 억제
- `--no-server` 분석 후 DB 저장만 하고 서버 시작 안 함 (CI 용)
- `--port <n>` 포트 고정 (기본: OS 할당 랜덤)

## 저장소

분석 결과는 타겟 프로젝트 루트의 `.code-atlas/atlas.db` (SQLite) 에 저장된다. Git 추적 제외 권장 (`.gitignore` 에 `.code-atlas/` 추가).

## 지원 범위

- 언어: TypeScript, JavaScript
- 프레임워크: Next.js (H7 최적화), React, Node.js 서버
- OS: Windows / macOS / Linux

## 주의

- 인증 없음, 로컬 전용 (외부 서비스 호출 없음)
- GitHub 이슈 자동 생성은 `gh` CLI 가 설치·인증되어 있을 때만 동작
- Claude 프롬프트 복사는 OS 클립보드 API 사용 (브라우저에서)
