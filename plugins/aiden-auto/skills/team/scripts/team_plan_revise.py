#!/usr/bin/env python3
"""Phase 0.6 — Plan Revision (Exclude + Revise).

충돌 파일을 planned_writes 에서 제외, deferred 기록, revised_task 갱신.

사용:
    python team_plan_revise.py --sid <sid> --conflicts "a.md,b.md"

stdout: JSON {
    sid, original_count, excluded_count, remaining_count,
    cohesion_ratio, revised_task, deferred
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import team_manifest  # noqa: E402


def _norm(p: str) -> str:
    return p.replace("\\", "/").lstrip("./")


def revise(sid: str, conflicts: list[str]) -> dict:
    m = team_manifest.get(sid)
    if m is None:
        return {"error": "manifest not found", "sid": sid}

    conflict_set = set(_norm(c) for c in conflicts)
    original = m.get("planned_writes", []) or []
    original_count = m.get("original_count") or len(original)

    remaining = [p for p in original if _norm(p) not in conflict_set]
    deferred_new = [p for p in original if _norm(p) in conflict_set]
    # 기존 deferred 와 병합 (이전 재시도)
    existing_deferred = m.get("deferred", []) or []
    deferred = sorted(set(existing_deferred + deferred_new))

    excluded_count = original_count - len(remaining)
    cohesion_ratio = (len(remaining) / original_count) if original_count > 0 else 1.0

    # revised_task 생성 (deterministic 서술, LLM 불필요)
    original_task = m.get("task_description", "")
    if deferred_new:
        short = ", ".join(Path(p).name for p in deferred_new[:3])
        if len(deferred_new) > 3:
            short += f" 외 {len(deferred_new) - 3}건"
        revised_task = f"{original_task} — 충돌 제외: {short}"
    else:
        revised_task = original_task

    team_manifest.update(
        sid,
        planned_writes=remaining,
        deferred=deferred,
        excluded_count=excluded_count,
        cohesion_ratio=round(cohesion_ratio, 3),
        revised_task=revised_task,
        phase=0.6,
    )

    return {
        "sid": sid,
        "original_count": original_count,
        "excluded_count": excluded_count,
        "remaining_count": len(remaining),
        "cohesion_ratio": round(cohesion_ratio, 3),
        "revised_task": revised_task,
        "deferred": deferred,
        "remaining": remaining,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sid", required=True)
    ap.add_argument("--conflicts", default="", help="CSV of conflicting files")
    args = ap.parse_args()

    conflicts = [s.strip() for s in args.conflicts.split(",") if s.strip()]
    result = revise(args.sid, conflicts)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())
