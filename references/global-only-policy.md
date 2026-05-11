---
paths:
  - "automation_hub/**/*"
  - "archive-analyzer/**/*"
  - "vimeo_ott/**/*"
  - ".claude/skills/**/*"
  - ".claude/commands/**/*"
  - ".claude/agents/**/*"
---

# Global-Only Policy

## 핵심 원칙

**모든 스킬, 커맨드, 에이전트는 글로벌에만 존재해야 합니다.**

| 규칙 | 내용 |
|------|------|
| **글로벌 단일 소스** | 모든 리소스는 `C:\claude\.claude\`에만 존재 |
| **서브프로젝트 금지** | 서브프로젝트는 Junction만 허용 |
| **범용 재설계** | 프로젝트 특화 리소스는 범용으로 전환 후 글로벌에 추가 |
| **예외** | 로컬 상태 디렉토리만 허용 (hooks/, auto/, workflow/) |

## 허용/금지 테이블

### 디렉토리별 정책

| 디렉토리 | 글로벌 위치 | 서브프로젝트 | 정책 |
|----------|------------|--------------|------|
| **skills/** | `C:\claude\.claude\skills\` | Junction만 | ✅ 글로벌 필수 |
| **commands/** | `C:\claude\.claude\commands\` | Junction만 | ✅ 글로벌 필수 |
| **agents/** | `C:\claude\.claude\agents\` | Junction만 | ✅ 글로벌 필수 |
| **rules/** | `C:\claude\.claude\rules\` | 없음 | ✅ 글로벌 전용 |
| **hooks/** | - | 로컬 생성 | ✅ 로컬 허용 |
| **auto/** | - | 로컬 생성 | ✅ 로컬 허용 |
| **workflow/** | - | 로컬 생성 | ✅ 로컬 허용 |

### 파일 타입별 정책

| 파일 | 위치 | 정책 |
|------|------|------|
| `SKILL.md` | 글로벌만 | ❌ 로컬 생성 금지 |
| `*.md` (command) | 글로벌만 | ❌ 로컬 생성 금지 |
| `agent-*.md` | 글로벌만 | ❌ 로컬 생성 금지 |
| `config.json` | 로컬 가능 | ✅ 프로젝트별 설정 |
| `state.json` | 로컬 가능 | ✅ 세션 상태 |

## 잘못된 예

```powershell
# ❌ 서브프로젝트에 로컬 스킬 생성
mkdir automation_hub\.claude\skills\upload
New-Item automation_hub\.claude\skills\upload\SKILL.md

# ❌ 서브프로젝트에 로컬 커맨드 생성
New-Item archive-analyzer\.claude\commands\scan.md

# ❌ 디렉토리 복사
Copy-Item C:\claude\.claude\skills\ automation_hub\.claude\ -Recurse
```

## 올바른 예

```powershell
# ✅ 글로벌에 범용 스킬 생성
New-Item C:\claude\.claude\skills\media-upload\SKILL.md

# ✅ 서브프로젝트에 Junction 생성
cmd /c mklink /J automation_hub\.claude\skills C:\claude\.claude\skills

# ✅ 로컬 상태 디렉토리 생성
mkdir automation_hub\.claude\hooks
```

## 새 스킬/커맨드/에이전트 생성 프로세스

### 1. 필요성 검토

```
요청: "프로젝트 X 전용 스킬 필요"
    │
    ▼
┌─────────────────────────┐
│ 범용화 가능 여부 검토    │
└─────────────────────────┘
    │
    ├─ YES → 글로벌 추가
    └─ NO  → 로컬 설정 파일로 대체
```

### 2. 글로벌 추가

| 단계 | 작업 | 위치 |
|------|------|------|
| 1 | 범용 설계 | 모든 프로젝트에서 사용 가능하도록 |
| 2 | 글로벌 생성 | `C:\claude\.claude\skills\{name}\SKILL.md` |
| 3 | 문서화 | `docs/COMMAND_REFERENCE.md` 또는 `AGENTS_REFERENCE.md` |
| 4 | 테스트 | 여러 서브프로젝트에서 검증 |

### 3. 프로젝트 특화 설정

프로젝트별로 다른 동작이 필요한 경우:

```
글로벌 스킬
    ├── SKILL.md (범용 로직)
    └── 로컬 설정으로 동작 변경
        └── 서브프로젝트/.claude/config/skill-name.json
```

## 서브프로젝트 설정 방법

### Junction 생성 (권장)

```powershell
# 관리자 권한 필요
cd C:\claude\automation_hub\.claude

# skills 디렉토리 Junction
cmd /c mklink /J skills C:\claude\.claude\skills

# commands 디렉토리 Junction
cmd /c mklink /J commands C:\claude\.claude\commands

# agents 디렉토리 Junction
cmd /c mklink /J agents C:\claude\.claude\agents
```

### Junction vs 심볼릭 링크 비교

| 방식 | 타입 | Windows 표시 | 권장 |
|------|------|--------------|------|
| Junction | 디렉토리 전용 | `<JUNCTION>` | ✅ 권장 |
| SymbolicLink | 파일/디렉토리 | `<SYMLINK>` | ⚠️ 대안 |

**Junction이 권장되는 이유:**
- 디렉토리 전용으로 용도가 명확
- Windows 네이티브 지원
- 관리자 권한 필요 없음 (상대 경로 시)

### Junction 검증

```powershell
# Junction 확인
cmd /c dir /AL automation_hub\.claude

# 예상 출력:
# 2026-02-06  오전 10:00    <JUNCTION>     skills [C:\claude\.claude\skills]
```

## 위반 감지 체크리스트

### 수동 검사

```markdown
- [ ] 서브프로젝트에 `.claude/skills/` 디렉토리가 Junction인가?
- [ ] 서브프로젝트에 `.claude/commands/` 디렉토리가 Junction인가?
- [ ] 서브프로젝트에 `.claude/agents/` 디렉토리가 Junction인가?
- [ ] 새 스킬/커맨드가 글로벌에만 존재하는가?
- [ ] 로컬 생성된 파일이 상태/설정 파일만인가?
```

### PowerShell 검사 스크립트

```powershell
# 서브프로젝트에서 실행
$hasLocalSkills = Test-Path .claude/skills/*/SKILL.md
$hasLocalCommands = Test-Path .claude/commands/*.md
$hasLocalAgents = Test-Path .claude/agents/*.md

if ($hasLocalSkills -or $hasLocalCommands -or $hasLocalAgents) {
    Write-Error "❌ Global-Only Policy 위반: 로컬 리소스 발견"
}
```

## 마이그레이션 절차

기존 로컬 리소스를 글로벌로 전환:

| 단계 | 작업 | 명령 |
|------|------|------|
| 1 | 백업 | `Copy-Item .claude local-backup -Recurse` |
| 2 | 범용화 | 프로젝트 특화 부분 제거/설정화 |
| 3 | 글로벌 이동 | `Move-Item .claude\skills\X C:\claude\.claude\skills\` |
| 4 | 로컬 삭제 | `Remove-Item .claude\skills -Recurse -Force` |
| 5 | Junction 생성 | `cmd /c mklink /J .claude\skills C:\claude\.claude\skills` |
| 6 | 검증 | 기존 기능 동작 확인 |

## 강제 수단

- Hook: 계획 중 (서브프로젝트 로컬 생성 감지)
- 위반 시: ⚠️ 경고 메시지 + 마이그레이션 가이드 출력
- 영향도: **CRITICAL**
