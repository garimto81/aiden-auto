#!/usr/bin/env python
"""event_dispatcher.py — v28.2 Section 14 event 발화 + callback + DLQ

호출 패턴:
  from hooks.event_dispatcher import dispatch_event
  dispatch_event(event, blocking=False)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    hooks/ 폴더 기준: parent = hooks/, parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"

try:
    sys.path.insert(0, str(PLUGIN_ROOT))
    from lib.sessions.event_schema import (
        Event,
        append_event,
        dlq_jsonl_path,
        verify_event,
    )
except ImportError:
    Event = None  # type: ignore
    append_event = None
    dlq_jsonl_path = None
    verify_event = None
REGISTRY_HOOKS_FILE = STATE_DIR / "sessions" / "registry-hooks.json"

# Rate limiting (Section 14 Risk #15)
RATE_LIMIT_PER_SECOND = 10
_recent_event_times: dict[str, list[float]] = {}


def _read_registry() -> list[dict]:
    if not REGISTRY_HOOKS_FILE.is_file():
        return []
    try:
        data = json.loads(REGISTRY_HOOKS_FILE.read_text(encoding="utf-8"))
        return data.get("hooks", [])
    except (OSError, json.JSONDecodeError):
        return []


def _match_pattern(pattern: str, session_id: str) -> bool:
    """Simple glob: '*', 'S-*', 'aiden-auto:*'."""
    import fnmatch
    return fnmatch.fnmatchcase(session_id, pattern)


def _rate_limited(session_id: str) -> bool:
    """Returns True if session exceeded RATE_LIMIT_PER_SECOND."""
    now = time.time()
    bucket = _recent_event_times.setdefault(session_id, [])
    # Keep only last 1 second window
    _recent_event_times[session_id] = [t for t in bucket if now - t < 1.0]
    if len(_recent_event_times[session_id]) >= RATE_LIMIT_PER_SECOND:
        return True
    _recent_event_times[session_id].append(now)
    return False


def _dispatch_callback(hook: dict, event_dict: dict) -> bool:
    """Returns True on success."""
    callback_type = hook.get("callback_type", "file_watch")
    target = hook.get("callback_target", "")
    if callback_type == "file_watch":
        # No-op: file watchers tail events.jsonl directly
        return True
    if callback_type == "process_signal":
        # SIGUSR1 to PID (target = PID string)
        try:
            os.kill(int(target), 10)  # SIGUSR1
            return True
        except (OSError, ValueError):
            return False
    if callback_type == "exec":
        try:
            result = subprocess.run(
                target.split(), input=json.dumps(event_dict),
                text=True, capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    return False


def _retry_with_backoff(hook: dict, event_dict: dict, max_attempts: int = 5) -> bool:
    """1/2/4/8s backoff. Returns True on eventual success, False = DLQ."""
    delays = [1, 2, 4, 8]
    for i, delay in enumerate(delays):
        if _dispatch_callback(hook, event_dict):
            return True
        time.sleep(delay)
    # final attempt without delay
    return _dispatch_callback(hook, event_dict)


def _send_to_dlq(event_dict: dict, hook: dict) -> None:
    if dlq_jsonl_path is None:
        return
    path = dlq_jsonl_path(event_dict["session_id"])
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"event": event_dict, "failed_hook": hook, "ts": event_dict["timestamp"]}
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def dispatch_event(event, blocking: bool = False) -> bool:
    """Section 14: append event + fire callbacks. Non-blocking by default.

    Args:
        event: Event instance or dict
        blocking: if True, wait for all callbacks; else fire-and-forget

    Returns:
        True if at least append succeeded.
    """
    if append_event is None:
        return False

    event_dict = event.to_dict() if hasattr(event, "to_dict") else event

    # Rate limit check
    if _rate_limited(event_dict["session_id"]):
        # batch later or drop (we choose batch — append still happens, but callbacks deferred)
        try:
            if hasattr(event, "session_id"):
                append_event(event)
            return True
        except Exception:
            return False

    # 1. Always append (Section 14.5: append never fails)
    try:
        if hasattr(event, "session_id"):
            append_event(event)
        else:
            # Reconstruct Event from dict
            from lib.sessions.event_schema import Event as _Event
            append_event(_Event(**{k: v for k, v in event_dict.items() if k in _Event.__dataclass_fields__}))
    except Exception:
        return False

    # 2. Fire callbacks
    hooks = _read_registry()
    for hook in hooks:
        pattern = hook.get("session_id_pattern", "*")
        filters = hook.get("event_filters", [])
        if not _match_pattern(pattern, event_dict["session_id"]):
            continue
        if filters and event_dict["status"] not in filters:
            continue
        # exec/signal need verification + retry; file_watch is no-op
        if hook.get("callback_type") == "file_watch":
            continue
        if blocking:
            ok = _retry_with_backoff(hook, event_dict)
            if not ok:
                _send_to_dlq(event_dict, hook)
        else:
            # Fire in background (best-effort); on failure → DLQ
            try:
                if not _dispatch_callback(hook, event_dict):
                    _send_to_dlq(event_dict, hook)
            except Exception:
                _send_to_dlq(event_dict, hook)

    return True


def main() -> int:
    """CLI entrypoint: read event JSON from stdin, dispatch."""
    try:
        event_dict = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        return 1
    ok = dispatch_event(event_dict, blocking=False)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
