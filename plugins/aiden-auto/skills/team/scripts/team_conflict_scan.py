#!/usr/bin/env python3
"""Phase 0.5 — Conflict Scan.

모든 활성 session manifest 를 스캔하여 내 planned_writes 와 충돌 검사.

사용:
    python team_conflict_scan.py --sid <my-sid>

stdout: JSON {
    conflicts: [file, ...],               # 충돌 파일
    conflicted_sessions: [{sid, team, task, files}, ...],
    stale_cleaned: N,                     # 정리된 stale manifest 수
}
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import team_manifest  # noqa: E402


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def _file_matches_globs(path: str, globs: list[str]) -> bool:
    np = _norm(path)
    for g in globs:
        # fnmatch 는 ** 제한적 → 간이 처리
        ng = _norm(g).replace("**", "*")
        if fnmatch.fnmatch(np, ng) or np.startswith(ng.rstrip("/*")):
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True, help="내 session id (자기 제외용)")
    args = ap.parse_args()

    me = team_manifest.get(args.sid)
    if me is None:
        print(json.dumps({"error": "manifest not found", "sid": args.sid}))
        return 1

    my_writes = set(_norm(p) for p in me.get("planned_writes", []))

    # stale 먼저 정리
    stale_cleaned = team_manifest.cleanup_stale()

    others = [m for m in team_manifest.list_all() if m.get("sid") != args.sid]

    conflicts: set[str] = set()
    conflicted_sessions: list[dict] = []

    for other in others:
        if other.get("status") != "active":
            continue
        other_writes = set(_norm(p) for p in other.get("planned_writes", []))
        other_globs = other.get("planned_writes_globs", [])

        # precise intersection
        overlap = my_writes & other_writes

        # glob intersection (내 파일이 타 glob 에 매치)
        for mp in my_writes:
            if _file_matches_globs(mp, other_globs):
                overlap.add(mp)

        # 타 파일이 내 glob 에 매치
        my_globs = me.get("planned_writes_globs", [])
        for op in other_writes:
            if _file_matches_globs(op, my_globs):
                overlap.add(op)

        if overlap:
            conflicts.update(overlap)
            conflicted_sessions.append({
                "sid": other["sid"],
                "team": other.get("team_id"),
                "task": other.get("task_description", "")[:80],
                "started_at": other.get("started_at"),
                "files": sorted(overlap),
            })

    result = {
        "my_sid": args.sid,
        "conflicts": sorted(conflicts),
        "conflicted_sessions": conflicted_sessions,
        "conflict_count": len(conflicts),
        "other_active_count": len([o for o in others if o.get("status") == "active"]),
        "stale_cleaned": stale_cleaned,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
