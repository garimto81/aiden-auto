#!/usr/bin/env python3
"""team_detect.py — /team Phase 1: cwd → team ID + 세션 상태 탐지.

Output: JSON to stdout
  {
    "team_id": "team1|team2|team3|team4|null(conductor)",
    "repo": "<absolute repo root>",
    "cwd_mode": "team_subdir|team_worktree|conductor|invalid",
    "has_uncommitted": bool,
    "current_branch": "<branch>",
    "repo_name": "<e.g. ebs>"
  }

Exit:
  0 — detect 성공
  2 — EBS 레포가 아님
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


TEAM_RE = re.compile(r"team([1-4])", re.I)


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, check=False
        )
        return r.returncode, r.stdout.strip()
    except FileNotFoundError:
        return 127, ""


def find_repo_root(start: Path) -> Path | None:
    """cwd 상위로 올라가며 .git 이 있는 폴더 찾기."""
    cur = start.resolve()
    while cur != cur.parent:
        if (cur / ".git").exists():
            return cur
        cur = cur.parent
    return None


def is_ebs_repo(repo: Path) -> bool:
    rc, out = _run(["git", "remote", "-v"], cwd=repo)
    return rc == 0 and "ebs" in out.lower()


def detect_team_from_path(cwd: Path, repo: Path) -> tuple[str | None, str]:
    """
    팀 ID + cwd_mode 판별.
    - team_subdir: cwd 가 repo/team{N}-*/ 아래
    - team_worktree: cwd 가 sibling dir ebs-team{N}-*
    - conductor: cwd == repo root
    """
    try:
        rel = cwd.resolve().relative_to(repo.resolve())
    except ValueError:
        # cwd 가 repo 하위가 아님 → worktree 가능성
        cwd_abs = cwd.resolve()
        cwd_name = cwd_abs.name
        # 예: ebs-team2-settings, ebs-team3-clock 등
        m = re.match(r".*-team([1-4])-", cwd_name)
        if m:
            return f"team{m.group(1)}", "team_worktree"
        m2 = TEAM_RE.match(cwd_name)
        if m2:
            return f"team{m2.group(1)}", "team_worktree"
        return None, "invalid"

    # cwd 가 repo 하위
    if str(rel) == ".":
        return None, "conductor"

    parts = str(rel).replace("\\", "/").split("/")
    if parts and parts[0]:
        m = re.match(r"team([1-4])-", parts[0])
        if m:
            return f"team{m.group(1)}", "team_subdir"

    # repo 하위 but team 폴더 아님 (e.g. docs/, tools/) → conductor
    return None, "conductor"


def has_uncommitted(repo: Path) -> bool:
    rc, out = _run(["git", "status", "--porcelain"], cwd=repo)
    return rc == 0 and bool(out.strip())


def current_branch(repo: Path) -> str:
    rc, out = _run(["git", "branch", "--show-current"], cwd=repo)
    return out if rc == 0 else ""


def main() -> int:
    cwd = Path.cwd()
    repo = find_repo_root(cwd)
    if repo is None:
        print(json.dumps({"error": "not in a git repo", "cwd": str(cwd)}))
        return 2

    if not is_ebs_repo(repo):
        print(json.dumps({
            "error": "not EBS repo",
            "repo": str(repo),
            "hint": "cd C:/claude/ebs 먼저",
        }))
        return 2

    team_id, cwd_mode = detect_team_from_path(cwd, repo)
    result = {
        "team_id": team_id,
        "repo": str(repo).replace("\\", "/"),
        "cwd_mode": cwd_mode,
        "has_uncommitted": has_uncommitted(repo),
        "current_branch": current_branch(repo),
        "repo_name": repo.name,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
