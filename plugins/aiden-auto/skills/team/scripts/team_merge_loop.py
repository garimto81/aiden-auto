#!/usr/bin/env python3
"""team_merge_loop.py — /team Phase 7: rebase + ff-merge + push with retry.

Usage:
  python team_merge_loop.py --repo REPO --branch BRANCH [--max-retry 3]

- Team 세션: BRANCH (work/team{N}/_team-<ts>) → rebase on main → ff-merge → push → delete branch
- Conductor: BRANCH 비어있으면 main 직접 push

Output: stdout 에 진행 상황 + 최종 JSON summary

Exit:
  0 — push 성공
  1 — rebase conflict (user 해결 필요)
  2 — push 실패 (retry 3회 모두 실패)
  3 — 기타 git 오류

NOTE: v4.1 PR-mode implementation moved to repo-local `tools/team_pr_merge.py`
to respect Self-Modification boundary on user-global skills. Use that tool
from /team Phase 7 via wrapper invocation.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def team_merge(repo: Path, branch: str, max_retry: int = 3) -> dict:
    result = {
        "branch": branch,
        "attempts": [],
        "success": False,
        "final_sha": None,
        "error": None,
    }

    for attempt in range(1, max_retry + 1):
        attempt_log = {"attempt": attempt, "steps": []}

        # 1. fetch
        rc, _, err = _run(["git", "fetch", "origin"], repo)
        attempt_log["steps"].append({"step": "fetch", "rc": rc})
        if rc != 0:
            attempt_log["error"] = err[:200]
            result["attempts"].append(attempt_log)
            result["error"] = "fetch failed"
            return result

        # 2. main 으로 이동 + rebase
        _run(["git", "checkout", "main"], repo)
        rc, _, err = _run(["git", "pull", "--rebase", "origin", "main"], repo)
        attempt_log["steps"].append({"step": "main rebase", "rc": rc})
        if rc != 0:
            # abort rebase if in progress
            _run(["git", "rebase", "--abort"], repo)
            result["error"] = "main rebase conflict"
            result["attempts"].append(attempt_log)
            return result

        # 3. work 브랜치를 main 에 rebase
        rc, _, err = _run(["git", "checkout", branch], repo)
        attempt_log["steps"].append({"step": "checkout work", "rc": rc})
        if rc != 0:
            attempt_log["error"] = err[:200]
            result["attempts"].append(attempt_log)
            result["error"] = f"checkout {branch} failed"
            return result

        rc, _, err = _run(["git", "rebase", "main"], repo)
        attempt_log["steps"].append({"step": "rebase work→main", "rc": rc})
        if rc != 0:
            _run(["git", "rebase", "--abort"], repo)
            _run(["git", "checkout", branch], repo)
            result["error"] = "work→main rebase conflict"
            result["attempts"].append(attempt_log)
            return result

        # 4. ff-merge
        _run(["git", "checkout", "main"], repo)
        rc, _, err = _run(["git", "merge", "--ff-only", branch], repo)
        attempt_log["steps"].append({"step": "ff-merge", "rc": rc})
        if rc != 0:
            result["error"] = "ff-merge failed (non-ff state)"
            result["attempts"].append(attempt_log)
            return result

        # 5. push
        rc, _, err = _run(["git", "push", "origin", "main"], repo)
        attempt_log["steps"].append({"step": "push", "rc": rc})
        if rc == 0:
            # 성공
            _run(["git", "branch", "-D", branch], repo)
            result["success"] = True
            rc, sha, _ = _run(["git", "rev-parse", "--short", "HEAD"], repo)
            result["final_sha"] = sha.strip() if rc == 0 else None
            result["attempts"].append(attempt_log)
            return result

        # push rejected — retry
        attempt_log["error"] = err[:200]
        result["attempts"].append(attempt_log)
        if attempt < max_retry:
            print(f"  ⚠ push rejected (attempt {attempt}/{max_retry}), retrying...")

    result["error"] = f"push failed after {max_retry} attempts"
    return result


def conductor_push(repo: Path, max_retry: int = 3) -> dict:
    result = {
        "branch": "main",
        "attempts": [],
        "success": False,
        "final_sha": None,
        "error": None,
    }
    for attempt in range(1, max_retry + 1):
        attempt_log = {"attempt": attempt, "steps": []}
        _run(["git", "fetch", "origin"], repo)
        rc, _, err = _run(["git", "pull", "--rebase", "origin", "main"], repo)
        attempt_log["steps"].append({"step": "rebase", "rc": rc})
        if rc != 0:
            _run(["git", "rebase", "--abort"], repo)
            result["error"] = "main rebase conflict"
            result["attempts"].append(attempt_log)
            return result
        rc, _, err = _run(["git", "push", "origin", "main"], repo)
        attempt_log["steps"].append({"step": "push", "rc": rc})
        result["attempts"].append(attempt_log)
        if rc == 0:
            result["success"] = True
            rc, sha, _ = _run(
                ["git", "rev-parse", "--short", "HEAD"], repo
            )
            result["final_sha"] = sha.strip() if rc == 0 else None
            return result
    result["error"] = f"push failed after {max_retry} attempts"
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", default="",
                    help="work branch name (empty=conductor)")
    ap.add_argument("--max-retry", type=int, default=3)
    ap.add_argument("--no-pr", action="store_true",
                    help="legacy direct push 모드 (기본: team=PR, conductor=direct)")
    args = ap.parse_args()

    repo = Path(args.repo)
    if args.branch:
        # Team session — v4.1 기본 PR 모드, --no-pr 시 direct
        if args.no_pr:
            result = team_merge_direct(repo, args.branch, args.max_retry)
        else:
            result = team_merge_pr(repo, args.branch, args.max_retry)
    else:
        # Conductor — direct push 유지. 플랫폼 차단 시 사용자 안내
        result = conductor_push(repo, args.max_retry)

    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["success"]:
        return 0
    if result.get("error", "").startswith(("main rebase", "work→main rebase")):
        return 1
    if "push failed" in (result.get("error") or "") or "PR flow failed" in (result.get("error") or ""):
        return 2
    return 3


if __name__ == "__main__":
    sys.exit(main())
