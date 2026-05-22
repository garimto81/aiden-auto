# Hook Lifecycle

## Hook → Event 매핑 (14개 전체 레지스트리)

| Hook | 이벤트 | HARD RULE | 역할 | 매처 |
|------|--------|:---------:|------|------|
| agent_validator.py | SessionStart | - | 에이전트 YAML frontmatter 검증 | `""` |
| session_init.py | SessionStart | - | 브랜치 확인, TODO 표시, Stale 상태 정리, CB 리셋 | `""` |
| tool_validator.py | PreToolUse | **YES** | 위험 명령(taskkill/전체 프로세스 종료) 차단 | `Bash\|Write\|Edit` |
| branch_guard.py | PreToolUse(Edit\|Write) | **YES** | main 브랜치에서 코드 수정 차단 (허용 파일만 예외) | `Edit\|Write` |
| agent_teams_guard.py | PreToolUse(Agent) | - | bare Agent() 호출 차단 (team_name 필수) | `Agent` |
| post_edit_check.js | PostToolUse(Edit\|Write) | - | 린트/테스트 자동 실행 (TDD 피드백) | `Edit\|Write` |
| edit_error_recovery.py | PostToolUse(Edit) | - | Edit 실패 시 복구 안내 | `Edit` |
| context_limit_recovery.py | PostToolUse | - | 컨텍스트/토큰 한계 감지 → compaction 권고 | `""` |
| circuit_breaker.py | PostToolUse | - | 연속 실패 차단 (CLOSED→OPEN→HALF_OPEN) | `Bash\|Edit\|Write\|Agent` |
| pre_compact_save.py | PreCompact | - | 팀/태스크 상태 스냅샷 저장 | `""` |
| stop_completion_check.py | Stop | - | 미완료 태스크 존재 시 종료 차단 | `""` |
| deploy_gate.py | Stop | - | 배포 게이트 확인 | `""` |
| session_cleanup.py | SessionEnd | - | 미완료 작업 저장 | `""` |
| session_error_recovery.py | SessionEnd | - | 세션 에러(연결/만료) 감지 및 복구 안내 | `""` |

## SubagentStop Hooks

| Hook | 역할 |
|------|------|
| checklist_updater.py | TODO/체크리스트 자동 갱신 |
| tmpclaude_cleanup.py | 임시 파일 정리 |
| subagent_zombie_detector.py | Agent Teams 미완료 정리 |

## Phase별 Hook 적용 흐름

**Phase 0 (세션 시작)**: agent_validator.py → session_init.py (브랜치 확인 + CB 리셋 + TODO 표시)
**Phase 2-3 (구현)**: branch_guard.py (main 보호) → tool_validator.py (위험 차단) → agent_teams_guard.py (bare Agent 차단) → post_edit_check.js (린트/테스트) → circuit_breaker.py (연속 실패 차단)
**Phase 3 (검증)**: edit_error_recovery.py (Edit 복구) → context_limit_recovery.py (컨텍스트 한계)
**Pre-Compact**: pre_compact_save.py (스냅샷)
**종료 시**: stop_completion_check.py → deploy_gate.py → session_cleanup.py → session_error_recovery.py
