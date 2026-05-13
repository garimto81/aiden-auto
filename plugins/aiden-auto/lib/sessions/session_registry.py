"""session_registry.py — v28.2 Multi-Session 세션 인덱스 관리

Responsibilities:
- Session ID 생성 (aiden-auto:S-{ts}-{kind}-{hash})
- state/active-sessions.json 읽기/쓰기 (atomic)
- supervisor roster 조회 (`claude jobs list --json`)
- 중복 condition+parent_task 감지 → 재사용
- Status 전이 (ACTIVE → SUSPENDED/COMPLETED/FAILED)
- registry-hooks.json 콜백 등록 (Section 14)

Schema version: 1.0
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = "1.0"
SESSION_ID_PREFIX = "aiden-auto:"

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    lib/sessions/ 기준: parent.parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"
ACTIVE_SESSIONS_FILE = STATE_DIR / "active-sessions.json"
REGISTRY_HOOKS_FILE = STATE_DIR / "sessions" / "registry-hooks.json"

SessionKind = Literal["LOGIC_DATA", "VISUAL_INTERACTION"]
SessionStatus = Literal["ACTIVE", "SUSPENDED", "COMPLETED", "FAILED"]


@dataclass
class Session:
    schema_version: str
    id: str
    parent_task: str
    kind: SessionKind
    status: SessionStatus
    worktree: str
    created_at: str
    artifacts_dir: str
    condition_hash: str  # for dedup
    scope: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _short_hash(text: str, length: int = 4) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:length]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_active() -> dict:
    if not ACTIVE_SESSIONS_FILE.is_file():
        return {"schema_version": SCHEMA_VERSION, "sessions": [], "has_active_conflict": False}
    try:
        return json.loads(ACTIVE_SESSIONS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": SCHEMA_VERSION, "sessions": [], "has_active_conflict": False}


def _atomic_write(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def make_session_id(kind: SessionKind, condition: str) -> str:
    """Generate aiden-auto:S-{ts}-{kind}-{shorthash}."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M")
    h = _short_hash(condition + ts, length=4)
    return f"{SESSION_ID_PREFIX}S-{ts}-{kind.split('_')[0]}-{h}"


def find_duplicate(parent_task: str, condition_hash: str) -> Session | None:
    """Check active-sessions.json for matching parent_task + condition_hash. Returns reusable Session or None."""
    data = _read_active()
    for s in data.get("sessions", []):
        if (
            s.get("parent_task") == parent_task
            and s.get("condition_hash") == condition_hash
            and s.get("status") in ("ACTIVE", "SUSPENDED")
        ):
            return Session(**{k: v for k, v in s.items() if k in Session.__dataclass_fields__})
    return None


def register_session(
    parent_task: str,
    kind: SessionKind,
    condition: str,
    scope: str = "",
) -> Session:
    """Create and register a new session. Returns existing if duplicate found (dedup)."""
    condition_hash = _short_hash(condition, length=16)

    existing = find_duplicate(parent_task, condition_hash)
    if existing:
        return existing  # reuse — multi-CC safety §2

    sid = make_session_id(kind, condition)
    session = Session(
        schema_version=SCHEMA_VERSION,
        id=sid,
        parent_task=parent_task,
        kind=kind,
        status="ACTIVE",
        worktree=f".claude/worktrees/{sid.replace(':', '_')}/",
        created_at=_now_iso(),
        artifacts_dir=f"state/sessions/{sid.replace(':', '_')}/",
        condition_hash=condition_hash,
        scope=scope,
    )

    data = _read_active()
    data["sessions"].append(session.to_dict())
    _atomic_write(ACTIVE_SESSIONS_FILE, data)
    return session


def update_status(session_id: str, new_status: SessionStatus) -> bool:
    data = _read_active()
    updated = False
    for s in data["sessions"]:
        if s["id"] == session_id:
            s["status"] = new_status
            s["updated_at"] = _now_iso()
            updated = True
            break
    if updated:
        _atomic_write(ACTIVE_SESSIONS_FILE, data)
    return updated


def list_active(include_other_cc: bool = True) -> list[dict]:
    """List active sessions. If include_other_cc, also query supervisor roster."""
    own = _read_active().get("sessions", [])
    if not include_other_cc:
        return own

    try:
        # Multi-CC safety §4: supervisor roster from `claude jobs list`
        result = subprocess.run(
            ["claude", "jobs", "list", "--json"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            external = json.loads(result.stdout or "[]")
            # Merge: our prefix only for "aiden-auto:" namespace
            return own + [
                {"id": j.get("id"), "scope": j.get("scope", ""), "kind": "external", "status": j.get("status", "?")}
                for j in external
                if not str(j.get("id", "")).startswith(SESSION_ID_PREFIX)
            ]
    except (subprocess.SubprocessError, json.JSONDecodeError, FileNotFoundError):
        pass  # claude CLI 미설치 or 응답 실패 → own only

    return own


def flag_conflict(session_id_a: str, session_id_b: str, file_path: str) -> None:
    """Record conflict in conflicts-{date}.json and set statusline indicator."""
    conflicts_file = STATE_DIR / "sessions" / f"conflicts-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.json"
    existing = []
    if conflicts_file.is_file():
        try:
            existing = json.loads(conflicts_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            existing = []
    existing.append({
        "ts": _now_iso(),
        "sessions": [session_id_a, session_id_b],
        "conflict_file": file_path,
    })
    _atomic_write(conflicts_file, existing)

    # Mark in active-sessions.json
    data = _read_active()
    data["has_active_conflict"] = True
    _atomic_write(ACTIVE_SESSIONS_FILE, data)


def register_hook(hook_id: str, session_id_pattern: str, event_filters: list[str],
                  callback_type: str, callback_target: str, hmac_secret_ref: str = "env:AIDEN_AUTO_HMAC_SECRET") -> None:
    """Section 14: register a callback hook for event stream."""
    existing = {"schema_version": SCHEMA_VERSION, "hooks": []}
    if REGISTRY_HOOKS_FILE.is_file():
        try:
            existing = json.loads(REGISTRY_HOOKS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    # Replace existing hook with same id
    existing["hooks"] = [h for h in existing.get("hooks", []) if h.get("hook_id") != hook_id]
    existing["hooks"].append({
        "hook_id": hook_id,
        "session_id_pattern": session_id_pattern,
        "event_filters": event_filters,
        "callback_type": callback_type,
        "callback_target": callback_target,
        "hmac_secret_ref": hmac_secret_ref,
    })
    _atomic_write(REGISTRY_HOOKS_FILE, existing)


if __name__ == "__main__":
    # Smoke test
    s = register_session(
        parent_task="active-goal-test",
        kind="VISUAL_INTERACTION",
        condition="test condition",
        scope="frontend",
    )
    print(f"Registered: {s.id}")
    print(f"Active: {len(list_active(include_other_cc=False))} own sessions")
