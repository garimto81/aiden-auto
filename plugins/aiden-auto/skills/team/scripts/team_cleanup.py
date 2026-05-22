#!/usr/bin/env python3
"""Phase 8 — Manifest Cleanup.

/team 종료 시 호출. status 전환 후 30초 retention 또는 즉시 삭제.
Deferred 가 있으면 "다음 /team 에서 재시도" 프롬프트용 flag 파일 작성.

사용:
    python team_cleanup.py --sid <sid> --status success
    python team_cleanup.py --sid <sid> --status abort
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import team_manifest  # noqa: E402


def _repo_root() -> Path:
    import os
    p = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path.cwd()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True)
    ap.add_argument("--status", choices=["success", "abort"], required=True)
    args = ap.parse_args()

    m = team_manifest.get(args.sid)
    if m is None:
        print(json.dumps({"ok": False, "reason": "manifest not found"}))
        return 0  # idempotent

    deferred = m.get("deferred", []) or []
    team_id = m.get("team_id", "unknown")

    if args.status == "success":
        # retain for 30s for observability
        team_manifest.complete(args.sid, deferred)

        # deferred flag for next /team (per-team)
        if deferred:
            flag_dir = _repo_root() / ".claude" / ".deferred-queue"
            flag_dir.mkdir(parents=True, exist_ok=True)
            flag_path = flag_dir / f"{team_id}.json"
            payload = {
                "from_sid": args.sid,
                "task_description": m.get("task_description"),
                "deferred": deferred,
                "ratio": m.get("cohesion_ratio"),
                "at": m.get("heartbeat_at"),
            }
            flag_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                                 encoding="utf-8")

        print(json.dumps({
            "ok": True,
            "action": "completed",
            "deferred_count": len(deferred),
        }))
    else:
        # abort — 즉시 삭제
        team_manifest.abort(args.sid)
        print(json.dumps({"ok": True, "action": "aborted"}))

    # stale 청소는 매 cleanup 에서 시행
    removed = team_manifest.cleanup_stale()
    if removed:
        sys.stderr.write(f"[team-cleanup] removed {removed} stale manifests\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
