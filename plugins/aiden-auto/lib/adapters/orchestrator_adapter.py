"""orchestrator_adapter.py — v28.2 글로벌 orchestrator skill 격리

`~/.claude/skills/orchestrator/SKILL.md` v10.3+ 버전 감지 + 호출 경로 분기.
재구현 금지 — adapter는 facade만.

Schema version: 1.0
"""
from __future__ import annotations

import re
from pathlib import Path

SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["v10.3+"]

ORCHESTRATOR_PATH = Path.home() / ".claude" / "skills" / "orchestrator" / "SKILL.md"
MIN_VERSION = (10, 3)


def detect_orchestrator() -> tuple[bool, tuple[int, int] | None]:
    """Check if global orchestrator is present and version >= 10.3."""
    if not ORCHESTRATOR_PATH.is_file():
        return (False, None)
    try:
        content = ORCHESTRATOR_PATH.read_text(encoding="utf-8")
        m = re.search(r"v?(\d+)\.(\d+)", content[:1024])  # version usually near top
        if m:
            v = (int(m.group(1)), int(m.group(2)))
            return (v >= MIN_VERSION, v)
    except OSError:
        pass
    return (False, None)


def get_invocation_path(stream_count: int) -> str:
    """Returns user-facing recommendation string for orchestrator.

    Adapter purpose: if orchestrator API changes, only this function updates.
    """
    available, version = detect_orchestrator()
    if not available:
        return "글로벌 orchestrator (v10.3+) 미설치. claude --bg × N 직접 사용 권장."
    v_str = f"v{version[0]}.{version[1]}" if version else "v10.3+"
    return f"/orchestrator init streams={stream_count}  # (글로벌 {v_str} 사용)"


def get_compat_warning() -> str | None:
    """Return warning if version mismatch detected."""
    available, version = detect_orchestrator()
    if available:
        return None
    if version is not None:
        return f"orchestrator {version} < required {MIN_VERSION}. Multi-session bridge fallback enabled."
    return "orchestrator missing — using claude --bg direct path"


if __name__ == "__main__":
    available, version = detect_orchestrator()
    print(f"orchestrator: available={available}, version={version}")
    print(f"recommend: {get_invocation_path(3)}")
    warning = get_compat_warning()
    if warning:
        print(f"warning: {warning}")
