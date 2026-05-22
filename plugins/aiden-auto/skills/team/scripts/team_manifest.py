#!/usr/bin/env python3
"""Team Manifest/Lease CRUD — v4.0 Pre-Declaration 충돌 방지의 핵심 인프라.

각 /team 호출은 `.claude/.session-manifests/{sid}.json` 에 lease 를 기록.
- TTL + heartbeat (Kubernetes Lease 패턴)
- atomic write (tmp → rename)
- stale auto-cleanup (5분 TTL)
- atexit 정리

사용:
    python team_manifest.py create --team team1 --task "..." --writes "a.md,b.md"
    python team_manifest.py heartbeat --sid <sid>
    python team_manifest.py update --sid <sid> --phase 4
    python team_manifest.py complete --sid <sid>
    python team_manifest.py list
    python team_manifest.py cleanup-stale
    python team_manifest.py get --sid <sid>  # stdout JSON
"""
from __future__ import annotations

import argparse
import atexit
import datetime
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# --- 상수 ---
SCHEMA_VERSION = "1.0"
LEASE_TTL_SEC = 300  # 5분 (Kubernetes Lease default 와 정합)
COMPLETED_RETENTION_SEC = 30  # completed 후 30초 유지 (observability)


def _repo_root() -> Path:
    """EBS 레포 루트 탐색. cwd 또는 env."""
    p = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path(os.getcwd()).resolve()


def _manifest_dir() -> Path:
    d = _repo_root() / ".claude" / ".session-manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_ts() -> float:
    return time.time()


def _parse_iso(iso: str) -> float:
    try:
        return datetime.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc).timestamp()
    except Exception:
        return 0.0


def _make_sid(team_id: str) -> str:
    """세션 ID 생성: {team}-{pid}-{iso_ts}."""
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{team_id}-{os.getpid()}-{ts}"


def _atomic_write(path: Path, data: dict) -> None:
    """atomic write via tmp + rename (JSON race 방지)."""
    tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _manifest_path(sid: str) -> Path:
    return _manifest_dir() / f"{sid}.json"


# --- CRUD ---

def create(team_id: str, task: str, planned_writes: list[str],
           planned_writes_globs: list[str] | None = None,
           planned_reads: list[str] | None = None,
           priority: int = 0) -> dict:
    """신규 manifest 생성."""
    sid = _make_sid(team_id)
    now = _now_iso()
    m = {
        "schema_version": SCHEMA_VERSION,
        "sid": sid,
        "team_id": team_id,
        "task_description": task,
        "revised_task": None,
        "started_at": now,
        "heartbeat_at": now,
        "phase": 0,
        "status": "active",
        "planned_writes": sorted(set(planned_writes or [])),
        "planned_writes_globs": sorted(set(planned_writes_globs or [])),
        "planned_reads": sorted(set(planned_reads or [])),
        "actual_writes": [],
        "deferred": [],
        "excluded_count": 0,
        "original_count": len(planned_writes or []),
        "cohesion_ratio": 1.0,
        "priority": priority,
        "lease_ttl_sec": LEASE_TTL_SEC,
    }
    _atomic_write(_manifest_path(sid), m)
    return m


def get(sid: str) -> dict | None:
    p = _manifest_path(sid)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def update(sid: str, **fields: Any) -> dict | None:
    m = get(sid)
    if m is None:
        return None
    m.update(fields)
    m["heartbeat_at"] = _now_iso()
    _atomic_write(_manifest_path(sid), m)
    return m


def heartbeat(sid: str) -> bool:
    m = get(sid)
    if m is None:
        return False
    m["heartbeat_at"] = _now_iso()
    _atomic_write(_manifest_path(sid), m)
    return True


def complete(sid: str, deferred: list[str] | None = None) -> None:
    """Phase 8 종료. 30초 후 삭제를 위해 status 만 변경."""
    m = get(sid)
    if m is None:
        return
    m["status"] = "completed"
    m["heartbeat_at"] = _now_iso()
    if deferred is not None:
        m["deferred"] = deferred
    _atomic_write(_manifest_path(sid), m)


def abort(sid: str) -> None:
    """실패 시 즉시 삭제."""
    p = _manifest_path(sid)
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


def list_all(include_stale: bool = False) -> list[dict]:
    """전체 manifest 목록. stale 제외 옵션."""
    out = []
    now = _now_ts()
    for p in _manifest_dir().glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        age = now - _parse_iso(m.get("heartbeat_at", ""))
        m["_age_sec"] = age
        if not include_stale and age > m.get("lease_ttl_sec", LEASE_TTL_SEC):
            continue
        # completed 이면서 retention 지났으면 제외
        if m.get("status") == "completed" and age > COMPLETED_RETENTION_SEC:
            continue
        if m.get("status") == "aborted":
            continue
        out.append(m)
    return out


def cleanup_stale() -> int:
    """stale manifest 삭제. 반환: 삭제 건수."""
    count = 0
    now = _now_ts()
    for p in _manifest_dir().glob("*.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
            continue
        age = now - _parse_iso(m.get("heartbeat_at", ""))
        ttl = m.get("lease_ttl_sec", LEASE_TTL_SEC)
        if age > ttl:
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
        elif m.get("status") == "completed" and age > COMPLETED_RETENTION_SEC:
            try:
                p.unlink()
                count += 1
            except Exception:
                pass
    return count


# --- atexit ---

_MY_SID: str | None = None


def register_atexit(sid: str) -> None:
    global _MY_SID
    _MY_SID = sid
    atexit.register(_atexit_cleanup)


def _atexit_cleanup() -> None:
    if _MY_SID is not None:
        m = get(_MY_SID)
        if m and m.get("status") == "active":
            abort(_MY_SID)


# --- CLI ---

def main() -> int:
    ap = argparse.ArgumentParser(description="Team Manifest/Lease CRUD")
    sub = ap.add_subparsers(dest="cmd", required=True)

    c_create = sub.add_parser("create")
    c_create.add_argument("--team", required=True)
    c_create.add_argument("--task", required=True)
    c_create.add_argument("--writes", default="", help="CSV of file paths")
    c_create.add_argument("--globs", default="", help="CSV of glob patterns")
    c_create.add_argument("--reads", default="", help="CSV of read-only paths")
    c_create.add_argument("--priority", type=int, default=0)

    c_hb = sub.add_parser("heartbeat")
    c_hb.add_argument("--sid", required=True)

    c_up = sub.add_parser("update")
    c_up.add_argument("--sid", required=True)
    c_up.add_argument("--phase", type=int)
    c_up.add_argument("--status")
    c_up.add_argument("--revised-task")
    c_up.add_argument("--actual-write", action="append", default=[])

    c_cp = sub.add_parser("complete")
    c_cp.add_argument("--sid", required=True)
    c_cp.add_argument("--deferred", default="")

    c_ab = sub.add_parser("abort")
    c_ab.add_argument("--sid", required=True)

    sub.add_parser("list")
    sub.add_parser("cleanup-stale")

    c_get = sub.add_parser("get")
    c_get.add_argument("--sid", required=True)

    args = ap.parse_args()

    if args.cmd == "create":
        writes = [s.strip() for s in args.writes.split(",") if s.strip()]
        globs = [s.strip() for s in args.globs.split(",") if s.strip()]
        reads = [s.strip() for s in args.reads.split(",") if s.strip()]
        m = create(args.team, args.task, writes, globs, reads, args.priority)
        print(json.dumps({"sid": m["sid"], "path": str(_manifest_path(m["sid"]))}))
    elif args.cmd == "heartbeat":
        ok = heartbeat(args.sid)
        print(json.dumps({"ok": ok}))
    elif args.cmd == "update":
        fields = {}
        if args.phase is not None:
            fields["phase"] = args.phase
        if args.status:
            fields["status"] = args.status
        if args.revised_task:
            fields["revised_task"] = args.revised_task
        if args.actual_write:
            m = get(args.sid) or {}
            cur = set(m.get("actual_writes", []))
            cur.update(args.actual_write)
            fields["actual_writes"] = sorted(cur)
        m = update(args.sid, **fields)
        print(json.dumps({"ok": m is not None}))
    elif args.cmd == "complete":
        deferred = [s.strip() for s in args.deferred.split(",") if s.strip()]
        complete(args.sid, deferred)
        print(json.dumps({"ok": True}))
    elif args.cmd == "abort":
        abort(args.sid)
        print(json.dumps({"ok": True}))
    elif args.cmd == "list":
        lst = list_all()
        print(json.dumps(lst, indent=2, ensure_ascii=False))
    elif args.cmd == "cleanup-stale":
        n = cleanup_stale()
        print(json.dumps({"removed": n}))
    elif args.cmd == "get":
        m = get(args.sid)
        print(json.dumps(m, indent=2, ensure_ascii=False) if m else "null")
    return 0


if __name__ == "__main__":
    sys.exit(main())
