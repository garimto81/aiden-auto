"""event_schema.py — v28.2 Section 14 Multi-Session Progress Hook Events

Schema v1.0 — file-based event stream + HMAC + idempotency + DLQ.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

SCHEMA_VERSION = "1.0"

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
HMAC_SECRET_FILE = STATE_DIR / ".hmac-secret"
HMAC_SECRET_PREV_FILE = STATE_DIR / ".hmac-secret-prev"

EventStatus = Literal["INITIATED", "IN_PROGRESS", "COMPLETED", "ERROR"]


@dataclass
class ProgressMeta:
    current_step: int = 0
    total_steps: int = 1
    phase: str = ""
    percent: int = 0


@dataclass
class EventPayload:
    type: str  # phase_complete | artifact_emitted | error | log | checkpoint
    data: dict = field(default_factory=dict)


@dataclass
class Event:
    schema_version: str
    event_id: str
    timestamp: str
    session_id: str
    parent_task: str
    status: EventStatus
    progress_meta: dict
    payload: dict
    hmac: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class EventBuilder:
    """Section 14.2 create event with auto-generated event_id + HMAC."""

    @staticmethod
    def create(
        session_id: str,
        status: EventStatus,
        progress_meta: ProgressMeta | dict | None = None,
        payload: EventPayload | dict | None = None,
        parent_task: str = "",
    ) -> Event:
        ts = datetime.now(timezone.utc).isoformat()
        ts_ns = time.time_ns()
        eid_hash = hashlib.sha256(f"{session_id}-{ts_ns}".encode()).hexdigest()[:4]
        event_id = f"E-{session_id.replace(':', '_')}-{ts_ns}-{eid_hash}"

        pm = asdict(progress_meta) if isinstance(progress_meta, ProgressMeta) else (progress_meta or {})
        pl = asdict(payload) if isinstance(payload, EventPayload) else (payload or {"type": "log", "data": {}})

        ev = Event(
            schema_version=SCHEMA_VERSION,
            event_id=event_id,
            timestamp=ts,
            session_id=session_id,
            parent_task=parent_task,
            status=status,
            progress_meta=pm,
            payload=pl,
        )
        ev.hmac = sign_event(ev)
        return ev


def _get_secret() -> str:
    """Returns HMAC secret. Generates if missing."""
    env = os.environ.get("AIDEN_AUTO_HMAC_SECRET")
    if env:
        return env
    if HMAC_SECRET_FILE.is_file():
        try:
            return HMAC_SECRET_FILE.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    # Generate
    HMAC_SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_secret = hashlib.sha256(os.urandom(32)).hexdigest()
    HMAC_SECRET_FILE.write_text(new_secret, encoding="utf-8")
    try:
        os.chmod(HMAC_SECRET_FILE, 0o600)
    except OSError:
        pass
    return new_secret


def sign_event(ev: Event) -> str:
    """Section 14.6: HMAC-SHA256 over canonical fields (excluding payload.data)."""
    secret = _get_secret()
    canonical = f"{ev.event_id}|{ev.session_id}|{ev.status}|{ev.timestamp}"
    sig = hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
    return f"sha256:{sig}"


def verify_event(ev: Event | dict) -> bool:
    """Verify HMAC. Try current secret then -prev (30-day rotation grace)."""
    if isinstance(ev, dict):
        try:
            ev = Event(**{k: v for k, v in ev.items() if k in Event.__dataclass_fields__})
        except TypeError:
            return False
    if not ev.hmac.startswith("sha256:"):
        return False
    sig_given = ev.hmac[len("sha256:"):]
    canonical = f"{ev.event_id}|{ev.session_id}|{ev.status}|{ev.timestamp}"

    # Try current secret
    current_sig = hmac.new(_get_secret().encode(), canonical.encode(), hashlib.sha256).hexdigest()
    if hmac.compare_digest(sig_given, current_sig):
        return True

    # Try previous (rotation grace)
    if HMAC_SECRET_PREV_FILE.is_file():
        try:
            prev_secret = HMAC_SECRET_PREV_FILE.read_text(encoding="utf-8").strip()
            prev_sig = hmac.new(prev_secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()
            if hmac.compare_digest(sig_given, prev_sig):
                return True
        except OSError:
            pass
    return False


def events_jsonl_path(session_id: str) -> Path:
    """Section 14.1: per-session event stream location."""
    safe = session_id.replace(":", "_")
    return STATE_DIR / "sessions" / safe / "events.jsonl"


def dlq_jsonl_path(session_id: str) -> Path:
    """Section 14.5: DLQ location for failed callbacks."""
    safe = session_id.replace(":", "_")
    return STATE_DIR / "sessions" / safe / "dlq.jsonl"


def append_event(ev: Event) -> None:
    """Append event to events.jsonl. Atomic + fsync."""
    path = events_jsonl_path(ev.session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(ev.to_dict(), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
        f.flush()
        try:
            os.fsync(f.fileno())
        except OSError:
            pass


def tail_events(session_id: str, n: int = 10) -> list[dict]:
    """Read last N events from events.jsonl. Used by statusline_compose.py."""
    path = events_jsonl_path(session_id)
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        events = []
        for line in lines[-n:]:
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return events
    except OSError:
        return []


if __name__ == "__main__":
    # Smoke test
    ev = EventBuilder.create(
        session_id="aiden-auto:S-test-VISUAL-0001",
        status="IN_PROGRESS",
        progress_meta=ProgressMeta(current_step=3, total_steps=5, phase="phase-2-build", percent=60),
        payload=EventPayload(type="phase_complete", data={"from": "phase-1", "to": "phase-2"}),
        parent_task="goal-test",
    )
    append_event(ev)
    print(f"event_id={ev.event_id}")
    print(f"hmac={ev.hmac[:32]}...")
    print(f"verify={verify_event(ev)}")
    print(f"tailed={len(tail_events(ev.session_id))} event(s)")
