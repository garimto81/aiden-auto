# Universal Deployment Checklist

> ⭐ premise 평가 reference. 모든 framework 변경 시 `/auto` Step 0.7 에서 자동 적용.

본 체크리스트는 글로벌 CLAUDE.md § Universal Deployment Premise (0 순위 원칙) 의 운영 도구.

---

## Pre-Change Checklist (변경 전 자체 평가)

```
변경 대상 분류:
   │
   ▼ 본인 PC 만의 자산? (state/, projects/memory/, .credentials.json 등)
   ├─ YES → premise 적용 안 함 (개인화 영역)
   │
   ▼ NO — framework 자산? (~/.claude/{agents,skills,hooks,...}, plugin)
   └─ premise 6 기준 평가 필수
```

---

## 6 기준 평가 표

| # | 기준 | 통과 검증 방법 | 자동화 가능? |
|---|------|--------------|:--:|
| 1 | 자기복제율 ≥95% | `python ~/.claude/scripts/measure-replication.py` (신규 PC 시뮬레이션) | ✅ |
| 2 | hardcoded path 0 | `grep -rE "C:\\\\claude\\|C:\\\\aiden-auto-repo" ~/.claude/hooks/` 결과 = 0 | ✅ |
| 3 | OS-agnostic | `pathlib.Path` 만 사용, `os.sep` / `\\` 직접 사용 안 함 | ⚠ 수동 + grep |
| 4 | 권한-agnostic | admin/sudo 명시 없음 (코드 + 문서) | ⚠ 수동 |
| 5 | idempotent | `python <hook>.py && python <hook>.py` 두 번 실행해도 결과 동일 | ✅ |
| 6 | 개인화 격리 | EXCLUDE 패턴에 `credentials/state/projects/memory/oauth_tokens/.env` 포함 | ✅ |

---

## 자산 분류 (universal vs personalization)

### Universal 자산 (모든 PC 동일 — 6 기준 적용)

| 영역 | 위치 | sync 대상? |
|------|------|:----------:|
| agents | `~/.claude/agents/` | ✅ |
| skills | `~/.claude/skills/` | ✅ |
| hooks | `~/.claude/hooks/` + `hooks/registry/` | ✅ |
| commands | `~/.claude/commands/` | ✅ |
| rules | `~/.claude/rules/` | ✅ |
| references | `~/.claude/references/` | ✅ |
| hud | `~/.claude/hud/` | ✅ |
| lib | `~/.claude/lib/` | ✅ |
| scripts | `~/.claude/scripts/` | ✅ |
| plugin | `plugin.json`, `marketplace.json` | ✅ |

### Personalization 자산 (PC 별 다름 — premise 적용 X)

| 영역 | 위치 | 보호 정책 |
|------|------|----------|
| settings | `settings.json`, `settings.local.json` | EXCLUDE_FILE_NAMES 차단 |
| 본인 CLAUDE.md | layer별 독립 | EXCLUDE_FILE_NAMES 차단 |
| secrets | `.credentials.json`, `oauth_tokens/`, `.env` | EXCLUDE_FILE_NAMES + EXCLUDE_DIRS |
| state | `state/` | EXCLUDE_DIRS |
| memory | `projects/*/memory/` | EXCLUDE_DIRS |
| logs | `logs/` | EXCLUDE_DIRS |

---

## 위반 패턴 자동 감지 + 대응

### 패턴 1: Hardcoded path

```python
# ❌ 위반:
PROJECT_SOURCE = Path(r"C:\claude\plugins\aiden-auto")

# ✅ 정정:
from path_resolution import resolve_plugin_source
def get_source():
    src = resolve_plugin_source()
    if src is None:
        log("plugin source 부재 — universal deployment graceful skip")
    return src
```

### 패턴 2: device-scoped 표현

| ❌ 위반 표현 | ✅ universal 표현 |
|-----------|-----------------|
| "본인 PC 에서" | "framework 정본에서" |
| "내 환경" | "정본 환경" |
| "C:\claude\\..." | "(autodetect 결과)" 또는 환경변수 |
| "다른 PC 는 수동" | "다른 PC 는 onboard 후 자동" |
| "내 컴퓨터만 작동" | premise 위배 — 자율 정정 필요 |

### 패턴 3: Personalization 누출

```python
# ❌ 위반:
def sync_all():
    sync(home / ".credentials.json", dest)

# ✅ 정정 (EXCLUDE 명시):
EXCLUDE_FILE_NAMES = {"settings.json", ".credentials.json", ...}
EXCLUDE_DIRS = {"state", "projects", "oauth_tokens", "logs"}
```

---

## 위반 감지 시 자동 대응 흐름

```
사용자 / Claude 변경 시도
     │
     ▼
Step 0.7 6 기준 자동 평가
     │
     ├─ 6/6 통과 → 변경 자율 진행
     │
     └─ 1+ 위반 →
         │
         ▼
   응답 작성 중단
         │
         ▼
   위배 사유 명시 (어느 기준 / 어느 표현)
         │
         ▼
   자율 정정 가능?
   ├─ YES → 즉시 정정 패턴 적용 (Layer B / EXCLUDE 추가 등) → 재평가
   └─ NO → premise 충돌 보고 + 사용자 결정 영역
```

---

## 검증 도구 (Phase 4 적용)

```bash
# 1. Hardcoded path 검증
grep -rE "C:\\\\claude\\|C:\\\\aiden-auto-repo" ~/.claude/hooks/*.py
# 기대: 빈 결과 또는 backward compat 주석 라인만

# 2. OS-agnostic 검증
grep -rE 'os\.sep|\\\\\\\\' ~/.claude/hooks/*.py | grep -v "^.*#"
# 기대: 빈 결과

# 3. 자기복제율 측정
python ~/.claude/scripts/measure-replication.py
# 기대: ≥95%

# 4. Idempotency 검증
python ~/.claude/hooks/bootstrap.py && python ~/.claude/hooks/bootstrap.py
# 기대: 두 번째 실행 시 0 files copied

# 5. Personalization 격리 검증
grep -E "(EXCLUDE_FILE_NAMES|EXCLUDE_DIRS)" ~/.claude/hooks/*.py
# 기대: credentials, state, projects 모두 포함
```

---

## 본 체크리스트의 메타-자율성

본 체크리스트 자체도 premise 6 기준 통과:

| # | 본 문서 자체 평가 |
|---|----------------|
| 1 | 자기복제율 | ✅ 본 문서가 모든 PC 에 동일 적용 (universal 자산) |
| 2 | hardcoded path 0 | ✅ 본 문서에 절대 경로 없음 (모두 `~/.claude/` 상대) |
| 3 | OS-agnostic | ✅ POSIX-style 경로 |
| 4 | 권한-agnostic | ✅ admin 명시 없음 |
| 5 | idempotent | ✅ read-only 참조 문서 |
| 6 | 개인화 격리 | ✅ universal 자산 분류 명시 |

---

## 변경 이력

| 날짜 | 변경 | 사유 |
|------|------|------|
| 2026-05-23 | v1.0 신규 | Universal Deployment Premise (HIGHEST PRIORITY) 평가 도구 |
