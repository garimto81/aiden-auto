"""agent_view_adapter — DEPRECATED stub (2026-05-15)

배경: lib/sessions/helpers.py:37 이 `from ..adapters import agent_view_adapter`
호출. 옛 multi-session-router 시스템이 사용했으나 공식 `claude agents` CLI 채택 후
폐기 의도 (Plan B v3.4 결정 5A).

본 파일은 ImportError 방지용 stub. 함수 호출 시 NotImplementedError 발생하여
사용 시 명시적 fail. 진짜 폐기 결정 시 호출자 (lib/sessions/helpers.py) 정리 필요.

관련:
- ~/.claude/agents/meta/multi-session-router.md (RESTORED 2026-05-15)
- ~/.claude/references/multi-session-bridge.md (RESTORED)
- 공식: https://code.claude.com/docs/en/agent-view
"""

DEPRECATED = True
DEPRECATION_DATE = "2026-05-15"
REPLACEMENT = "Use official `claude agents` CLI directly"


def get_active_sessions(*args, **kwargs):
    """Stub — 옛 multi-session-router 시스템 잔재.

    공식 `claude agents` CLI 사용 또는 `~/.claude/jobs/` 직접 읽기로 대체.
    """
    raise NotImplementedError(
        "agent_view_adapter is deprecated. "
        "Use `claude agents` CLI or read ~/.claude/jobs/ directly."
    )


def register_session(*args, **kwargs):
    """Stub — 옛 session registry 등록."""
    raise NotImplementedError(
        "agent_view_adapter.register_session deprecated. "
        "Sessions are auto-managed by supervisor process."
    )


def get_session_status(*args, **kwargs):
    """Stub — 옛 session 상태 조회."""
    raise NotImplementedError(
        "agent_view_adapter.get_session_status deprecated. "
        "Use `claude logs <id>` or `claude agents`."
    )
