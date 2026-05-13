#!/usr/bin/env python
"""event_consumer_dlq.py — v28.2 Section 14.5 DLQ 1h 재시도

Cron/Stop hook으로 발화. 모든 active session의 dlq.jsonl 점검 + 재시도.
성공 시 DLQ 항목 제거. 실패 시 retry_count 증가, 5회 초과 시 expired로 마킹.

Schema v1.0
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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
SCHEMA_VERSION = "1.0"

STATE_DIR = PLUGIN_ROOT / "state"
SESSIONS_DIR = STATE_DIR / "sessions"
MAX_RETRIES = 5


def _retry_callback(hook: dict, event: dict) -> bool:
    callback_type = hook.get("callback_type", "file_watch")
    target = hook.get("callback_target", "")
    if callback_type == "file_watch":
        return True  # nothing to retry
    if callback_type == "exec":
        try:
            result = subprocess.run(
                target.split(), input=json.dumps(event),
                text=True, capture_output=True, timeout=5,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    if callback_type == "process_signal":
        try:
            os.kill(int(target), 10)
            return True
        except (OSError, ValueError):
            return False
    return False


def process_dlq(dlq_path: Path) -> tuple[int, int, int]:
    """Process one DLQ file. Returns (succeeded, expired, still_pending)."""
    if not dlq_path.is_file():
        return (0, 0, 0)
    try:
        lines = dlq_path.read_text(encoding="utf-8").strip().split("\n")
    except OSError:
        return (0, 0, 0)

    succeeded = 0
    expired = 0
    remaining = []

    for line in lines:
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        retry_count = int(entry.get("retry_count", 0))
        if retry_count >= MAX_RETRIES:
            entry["expired"] = True
            expired += 1
            remaining.append(entry)
            continue

        ok = _retry_callback(entry.get("failed_hook", {}), entry.get("event", {}))
        if ok:
            succeeded += 1
            continue

        entry["retry_count"] = retry_count + 1
        entry["last_retry_ts"] = datetime.now(timezone.utc).isoformat()
        remaining.append(entry)

    # Rewrite DLQ with remaining entries
    if remaining:
        dlq_path.write_text(
            "\n".join(json.dumps(e, ensure_ascii=False) for e in remaining) + "\n",
            encoding="utf-8",
        )
    else:
        try:
            dlq_path.unlink()
        except OSError:
            pass

    return (succeeded, expired, len(remaining))


def main() -> int:
    if not SESSIONS_DIR.is_dir():
        return 0

    total_succeeded = 0
    total_expired = 0
    total_pending = 0

    for session_dir in SESSIONS_DIR.iterdir():
        if not session_dir.is_dir():
            continue
        dlq_path = session_dir / "dlq.jsonl"
        if not dlq_path.is_file():
            continue
        s, e, p = process_dlq(dlq_path)
        total_succeeded += s
        total_expired += e
        total_pending += p

    if total_succeeded + total_expired + total_pending > 0:
        sys.stderr.write(
            f"[event_consumer_dlq] succeeded={total_succeeded}, "
            f"expired={total_expired}, pending={total_pending}\n"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
