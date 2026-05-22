#!/usr/bin/env python3
"""Phase 0 — Declaration.

/team 시작 시 LLM 이 예측한 수정 대상을 manifest 에 기록.
team-policy.json 의 decision_owner 참조로 ownership 체크 (R2).

사용:
    python team_declare.py \
        --team team1 \
        --task "Hand_History.md 신설 + UI.md 사이드바" \
        --writes "docs/.../Hand_History.md,docs/.../UI.md" \
        --globs "docs/2. Development/2.1 Frontend/Lobby/**"

stdout: JSON { sid, manifest_path, ownership_warnings: [...] }
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import team_manifest  # noqa: E402


def _repo_root() -> Path:
    p = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())).resolve()
    while p != p.parent:
        if (p / ".git").exists():
            return p
        p = p.parent
    return Path(os.getcwd()).resolve()


def _load_policy() -> dict:
    policy_path = _repo_root() / "docs" / "2. Development" / "2.5 Shared" / "team-policy.json"
    if not policy_path.exists():
        return {}
    try:
        return json.loads(policy_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _path_matches(path: str, prefix: str) -> bool:
    """path 가 prefix 로 시작하는지 (포함 매칭). Windows 경로 호환."""
    p = path.replace("\\", "/").lstrip("./")
    pfx = prefix.replace("\\", "/").rstrip("/*").lstrip("./")
    return p.startswith(pfx)


def _check_ownership(my_team: str, planned_writes: list[str], policy: dict) -> list[dict]:
    """선언한 파일이 다른 팀 decision_owner 경로에 해당하면 warning.

    team-policy.json 구조: teams = {team_id: {owns: [path_prefix, ...]}}
    Returns: [{path, owning_team, my_team, owned_prefix}] list.
    """
    warnings = []
    teams = policy.get("teams", {}) or {}
    # teams 가 list 형태인 경우도 허용 (backward compat)
    if isinstance(teams, list):
        ownership_map = {t.get("id"): (t.get("owns") or []) for t in teams if isinstance(t, dict)}
    elif isinstance(teams, dict):
        ownership_map = {tid: (spec.get("owns") or [])
                         for tid, spec in teams.items()
                         if isinstance(spec, dict)}
    else:
        ownership_map = {}

    for path in planned_writes:
        for team_id, prefixes in ownership_map.items():
            if not team_id or team_id == my_team:
                continue
            for pfx in prefixes:
                if _path_matches(path, pfx):
                    warnings.append({
                        "path": path,
                        "owning_team": team_id,
                        "my_team": my_team,
                        "owned_prefix": pfx,
                    })
                    break
    return warnings


def main() -> int:
    ap = argparse.ArgumentParser(description="Phase 0 Declaration")
    ap.add_argument("--team", required=True, help="conductor / team1-4")
    ap.add_argument("--task", required=True)
    ap.add_argument("--writes", default="", help="CSV")
    ap.add_argument("--globs", default="", help="CSV")
    ap.add_argument("--reads", default="", help="CSV")
    ap.add_argument("--priority", type=int, default=0)
    args = ap.parse_args()

    writes = [s.strip() for s in args.writes.split(",") if s.strip()]
    globs = [s.strip() for s in args.globs.split(",") if s.strip()]
    reads = [s.strip() for s in args.reads.split(",") if s.strip()]

    # R2 — team-policy.json 참조
    policy = _load_policy()
    ownership_warnings = _check_ownership(args.team, writes, policy)

    # manifest 생성
    m = team_manifest.create(
        team_id=args.team,
        task=args.task,
        planned_writes=writes,
        planned_writes_globs=globs,
        planned_reads=reads,
        priority=args.priority,
    )

    result = {
        "sid": m["sid"],
        "manifest_path": str(team_manifest._manifest_path(m["sid"])),
        "team_id": args.team,
        "original_count": len(writes),
        "ownership_warnings": ownership_warnings,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
