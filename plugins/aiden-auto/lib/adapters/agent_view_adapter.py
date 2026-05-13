"""agent_view_adapter.py — v28.2 CC `claude --bg` / `claude agents` 격리

CLI 명령 wrapper. 출력 파싱 (--json 우선), 버전 분기, agent-view 사용성 검증.

Schema version: 1.0
"""
from __future__ import annotations

import json
import re
import subprocess
from typing import NamedTuple

SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["2.1.139+"]
MIN_VERSION_TUPLE = (2, 1, 139)


class AgentViewStatus(NamedTuple):
    available: bool
    version: tuple[int, ...] | None
    supports_bg: bool
    error: str | None


def detect_cc_version() -> tuple[int, ...] | None:
    """Returns version tuple e.g., (2, 1, 139) or None if undetectable."""
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=5
        )
        m = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout)
        if m:
            return tuple(int(g) for g in m.groups())
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def check_status() -> AgentViewStatus:
    v = detect_cc_version()
    if v is None:
        return AgentViewStatus(
            available=False, version=None, supports_bg=False,
            error="claude CLI not detected"
        )
    supports = v >= MIN_VERSION_TUPLE
    return AgentViewStatus(
        available=True, version=v, supports_bg=supports,
        error=None if supports else f"version {v} < required {MIN_VERSION_TUPLE}"
    )


def spawn_background(task: str, name_prefix: str = "aiden-auto:") -> tuple[bool, str]:
    """Spawn a background session via `claude --bg`. Returns (success, session_id_or_error).

    Multi-CC safety: session name uses aiden-auto: prefix.
    """
    st = check_status()
    if not st.supports_bg:
        return (False, st.error or "agent-view unavailable")
    try:
        result = subprocess.run(
            ["claude", "--bg", task],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            # Parse session id from output (format may vary)
            m = re.search(r"session[:\s]+([^\s]+)", result.stdout, re.IGNORECASE)
            sid = m.group(1) if m else result.stdout.strip().split("\n")[0]
            return (True, sid)
        return (False, result.stderr or "spawn failed")
    except subprocess.SubprocessError as e:
        return (False, f"spawn error: {e}")


def list_jobs() -> list[dict]:
    """Query supervisor roster via `claude jobs list --json`. Multi-CC safe.

    Returns list of all sessions (own + other CC instances). Caller filters by prefix.
    """
    try:
        result = subprocess.run(
            ["claude", "jobs", "list", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout or "[]")
            return data if isinstance(data, list) else []
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        pass
    # Fallback: plain text parsing
    try:
        result = subprocess.run(
            ["claude", "jobs", "list"], capture_output=True, text=True, timeout=5
        )
        jobs = []
        for line in (result.stdout or "").strip().split("\n"):
            if line and not line.startswith("ID"):
                parts = line.split()
                if parts:
                    jobs.append({"id": parts[0], "raw": line})
        return jobs
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


def respawn_all() -> bool:
    """Recover suspended sessions via `claude respawn --all`."""
    try:
        result = subprocess.run(
            ["claude", "respawn", "--all"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def cleanup_orphan_worktrees(repo_path: str = ".") -> list[str]:
    """List orphan worktrees under .claude/worktrees/. Caller decides cleanup."""
    try:
        result = subprocess.run(
            ["git", "worktree", "list"],
            cwd=repo_path, capture_output=True, text=True, timeout=5,
        )
        orphans = []
        for line in (result.stdout or "").split("\n"):
            if ".claude/worktrees/" in line:
                # Check if session_id still active (caller responsibility via session_registry)
                orphans.append(line.split()[0])
        return orphans
    except (subprocess.SubprocessError, FileNotFoundError):
        return []


if __name__ == "__main__":
    st = check_status()
    print(f"available={st.available}, version={st.version}, supports_bg={st.supports_bg}, error={st.error}")
    print(f"jobs: {len(list_jobs())}")
