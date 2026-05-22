#!/usr/bin/env python3
"""team_observe.py — /team Phase 2: 다른 세션 활동 + main 상태.

Usage:
  python team_observe.py [--since ISO_TIMESTAMP] [--team TEAM_ID]

Output: human-readable (stdout) + structured (stderr JSON for programmatic use)

Prints:
  📡 Other sessions since your last /team (Xm ago):
    ✓ team2  <sha>  <msg>  (+X −Y)  3m ago
    ⧗ team1  WIP    <file>                 (active-edits)

  Your branch: <current>
  Main ahead: N commits → auto-rebasing...
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str]:
    r = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )
    return r.returncode, r.stdout


def git_fetch(repo: Path) -> None:
    subprocess.run(["git", "fetch", "origin"], cwd=repo, capture_output=True)


def main_ahead_commits(repo: Path, my_team: str | None) -> list[dict]:
    """origin/main 중 최근 커밋 N개, team 분류."""
    rc, out = _run(
        ["git", "log", "origin/main", "-20",
         "--format=%h%x09%an%x09%ar%x09%s"],
        cwd=repo,
    )
    if rc != 0:
        return []

    commits = []
    for line in out.strip().split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        sha, author, relative, subject = parts
        # team 분류: commit msg 의 (teamN) scope or "team" keyword
        team_m = re.search(r"\((team[1-4])\)", subject)
        team = team_m.group(1) if team_m else None
        commits.append({
            "sha": sha[:7],
            "author": author,
            "relative": relative,
            "subject": subject,
            "team": team,
        })
    return commits


def local_vs_origin(repo: Path) -> dict:
    """local main vs origin/main ahead/behind."""
    rc, out = _run(
        ["git", "rev-list", "--left-right", "--count",
         "origin/main...main"],
        cwd=repo,
    )
    if rc != 0:
        return {"behind": 0, "ahead": 0}
    parts = out.strip().split()
    if len(parts) == 2:
        return {"behind": int(parts[0]), "ahead": int(parts[1])}
    return {"behind": 0, "ahead": 0}


def current_branch(repo: Path) -> str:
    rc, out = _run(["git", "branch", "--show-current"], cwd=repo)
    return out.strip() if rc == 0 else ""


def active_edits(repo: Path) -> dict:
    """meta/active-edits orphan branch 의 active.json 읽기 (있으면)."""
    rc, out = _run(
        ["git", "show", "meta/active-edits:active.json"], cwd=repo
    )
    if rc != 0:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {}


def format_report(
    commits: list[dict],
    lv_origin: dict,
    branch: str,
    my_team: str | None,
    edits: dict,
    since_minutes: int | None,
) -> str:
    lines = []
    # 다른 세션 최근 commit (내 team 제외 + wip 회색)
    other = [c for c in commits if c["team"] != my_team]

    if other:
        header = "📡 Other sessions recent commits (origin/main):"
        if since_minutes:
            header = f"📡 Other sessions since your last /team ({since_minutes}m ago):"
        lines.append(header)
        for c in other[:8]:
            prefix = "✓" if c["team"] and not c["subject"].lower().startswith("wip") else "⋯"
            team_display = c["team"] or "???"
            lines.append(
                f"  {prefix} {team_display:8} {c['sha']:8} "
                f"{c['subject'][:60]:60}  {c['relative']}"
            )
    else:
        lines.append("📡 다른 세션 활동 없음 (최근 20 커밋 기준)")

    # active-edits (WIP)
    if edits:
        lines.append("")
        lines.append("⧗ Active edits (in-progress):")
        for team, info in edits.items():
            if team == my_team:
                continue
            files = info.get("files", [])
            claimed = info.get("claimed_at", "?")
            lines.append(
                f"  ⧗ {team:8}  files={len(files)}  claimed_at={claimed}"
            )

    lines.append("")
    lines.append(f"Your branch: {branch or '(none)'}")

    if lv_origin["behind"] > 0:
        lines.append(
            f"Main ahead: {lv_origin['behind']} commits → auto-rebasing..."
        )
    elif lv_origin["ahead"] > 0:
        lines.append(
            f"Local ahead: {lv_origin['ahead']} commits (unpushed)"
        )
    else:
        lines.append("Main synced ✓")

    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", type=str, default=None,
                    help="ISO timestamp for 'since' filter")
    ap.add_argument("--team", type=str, default=None,
                    help="My team ID (team1~4 or omit for conductor)")
    ap.add_argument("--no-fetch", action="store_true")
    args = ap.parse_args()

    repo_env = Path.cwd()
    # 상위로 올라가며 .git 찾기
    while repo_env != repo_env.parent:
        if (repo_env / ".git").exists():
            break
        repo_env = repo_env.parent

    if not args.no_fetch:
        git_fetch(repo_env)

    commits = main_ahead_commits(repo_env, args.team)
    lv = local_vs_origin(repo_env)
    branch = current_branch(repo_env)
    edits = active_edits(repo_env)

    # since_minutes 계산 (선택)
    since_minutes = None
    if args.since:
        try:
            since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
            delta = datetime.now(timezone.utc) - since_dt
            since_minutes = int(delta.total_seconds() / 60)
        except ValueError:
            pass

    report = format_report(commits, lv, branch, args.team, edits, since_minutes)
    print(report)

    # structured (stderr)
    sys.stderr.write(json.dumps({
        "commits": commits,
        "local_vs_origin": lv,
        "branch": branch,
        "my_team": args.team,
        "active_edits": edits,
    }, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
