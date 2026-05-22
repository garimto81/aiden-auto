#!/usr/bin/env python3
"""team_verify.py — /team Phase 5: drift + test + scope guard.

Usage:
  python team_verify.py --team TEAM_ID --repo REPO --baseline BASELINE.json

Output: JSON to stdout
  {
    "drift_regression": [...],
    "test_result": {"tool": "pytest|dart", "rc": 0, "summary": "..."},
    "scope_check": {"other_team_files": [...], "notify": "team2|null"},
    "overall": "pass|warn|fail"
  }

Exit:
  0 — pass
  1 — warn (user confirm 필요)
  2 — fail (block)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


TEAM_OWNED = {
    "team1": ["team1-frontend/", "docs/2. Development/2.1 Frontend/"],
    "team2": ["team2-backend/", "docs/2. Development/2.2 Backend/"],
    "team3": ["team3-engine/", "docs/2. Development/2.3 Game Engine/"],
    "team4": ["team4-cc/", "docs/2. Development/2.4 Command Center/"],
}

TEST_CMDS = {
    "team1": {"tool": "dart", "args": ["dart", "analyze", "team1-frontend"]},
    "team2": {
        "tool": "pytest",
        "args": [
            "python", "-m", "pytest",
            "team2-backend/tests/",
            "--co", "-q",
            "--rootdir=team2-backend",
        ],
    },
    "team3": {
        "tool": "dart",
        "args": ["dart", "analyze", "team3-engine/ebs_game_engine"],
    },
    "team4": {"tool": "dart", "args": ["dart", "analyze", "team4-cc/src"]},
}


def run_drift_scan(repo: Path) -> dict:
    rc = subprocess.run(
        ["python", str(repo / "tools" / "spec_drift_check.py"),
         "--all", "--format=json"],
        capture_output=True, text=True, cwd=repo
    )
    if rc.returncode != 0:
        return {"error": rc.stderr[:500]}
    try:
        return json.loads(rc.stdout)
    except json.JSONDecodeError:
        return {"error": "json parse failed"}


def diff_drift(baseline: dict, current: dict) -> list[dict]:
    """회귀만 추출 — D1/D2/D3 증가 or D4 감소."""
    regressions = []
    base_c = baseline.get("drift", {}) if "drift" in baseline else baseline
    cur_c = current if "drift" not in current else current.get("drift", {})
    # spec_drift_check --format=json 의 실제 구조는 contract 배열.
    # 여기서는 간단히 비교.
    if isinstance(base_c, list) and isinstance(cur_c, list):
        base_map = {c.get("contract"): c for c in base_c}
        cur_map = {c.get("contract"): c for c in cur_c}
    elif isinstance(base_c, dict) and isinstance(cur_c, dict):
        base_map = base_c
        cur_map = cur_c
    else:
        return []

    for contract, cur in cur_map.items():
        base = base_map.get(contract, {})
        if not isinstance(cur, dict) or not isinstance(base, dict):
            continue
        for k in ("d1", "d2", "d3"):
            base_v = base.get(k, 0)
            cur_v = cur.get(k, 0)
            if isinstance(base_v, list):
                base_v = len(base_v)
            if isinstance(cur_v, list):
                cur_v = len(cur_v)
            if cur_v > base_v:
                regressions.append({
                    "contract": contract,
                    "type": k.upper(),
                    "before": base_v,
                    "after": cur_v,
                })
        base_d4 = base.get("d4_count", 0)
        cur_d4 = cur.get("d4_count", 0)
        if cur_d4 < base_d4:
            regressions.append({
                "contract": contract,
                "type": "D4",
                "before": base_d4,
                "after": cur_d4,
            })
    return regressions


def run_test(repo: Path, team_id: str) -> dict:
    if team_id not in TEST_CMDS:
        return {"tool": "none", "rc": 0, "summary": "conductor — no test"}
    spec = TEST_CMDS[team_id]
    r = subprocess.run(
        spec["args"], cwd=repo, capture_output=True, text=True
    )
    lines = r.stdout.strip().split("\n")
    summary = lines[-1] if lines else ""
    return {
        "tool": spec["tool"],
        "rc": r.returncode,
        "summary": summary[:200],
        "stderr": r.stderr[:200] if r.returncode != 0 else "",
    }


def scope_check(repo: Path, team_id: str | None) -> dict:
    r = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo, capture_output=True, text=True
    )
    if r.returncode != 0:
        return {"other_team_files": [], "notify": None}

    staged = [p for p in r.stdout.strip().split("\n") if p]
    if not team_id:
        # Conductor: 모든 경로 OK
        return {"other_team_files": [], "notify": None}

    owned = TEAM_OWNED.get(team_id, [])
    other = []
    for path in staged:
        norm = path.replace("\\", "/")
        is_owned = any(norm.startswith(o) for o in owned)
        if not is_owned:
            # 다른 팀 소유 판별
            for t, paths in TEAM_OWNED.items():
                if t == team_id:
                    continue
                if any(norm.startswith(p) for p in paths):
                    other.append({"path": norm, "owner": t})
                    break

    notify = None
    if other:
        owners = sorted({o["owner"] for o in other})
        notify = "/".join(owners)
    return {"other_team_files": other, "notify": notify}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--team", type=str, default=None)
    ap.add_argument("--repo", type=str, required=True)
    ap.add_argument("--baseline", type=str, default=None)
    args = ap.parse_args()

    repo = Path(args.repo)
    baseline = {}
    if args.baseline and Path(args.baseline).exists():
        try:
            baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        except Exception:
            baseline = {}

    # 1. drift
    drift_current = run_drift_scan(repo)
    regressions = diff_drift(
        baseline.get("drift", {}),
        drift_current,
    ) if baseline else []

    # 2. test
    test_result = run_test(repo, args.team) if args.team else {
        "tool": "none", "rc": 0, "summary": "conductor"
    }

    # 3. scope
    scope = scope_check(repo, args.team)

    # overall
    if test_result.get("rc", 0) != 0:
        overall = "fail"
    elif regressions:
        overall = "warn"
    elif scope.get("other_team_files"):
        overall = "warn"
    else:
        overall = "pass"

    result = {
        "drift_regression": regressions,
        "test_result": test_result,
        "scope_check": scope,
        "overall": overall,
        "drift_current_summary": drift_current if isinstance(drift_current, (list, dict)) else {},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return {"pass": 0, "warn": 1, "fail": 2}[overall]


if __name__ == "__main__":
    sys.exit(main())
