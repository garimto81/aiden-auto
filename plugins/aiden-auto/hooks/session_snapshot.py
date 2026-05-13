#!/usr/bin/env python3
"""
세션 스냅샷 Hook - 세션 종료 시 변경 파일/커밋 이력/주요 결정사항 자동 캡처

SessionEnd 이벤트에서 실행됩니다.
저장 위치: .claude/research/session-snapshots/
TTL: 30일 또는 최대 50개 (초과 시 오래된 순 삭제)
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
SNAPSHOT_DIR = PROJECT_DIR / ".claude" / "research" / "session-snapshots"
MAX_SNAPSHOTS = 50
TTL_DAYS = 30


def run_git(args: list[str]) -> str:
    """git 명령 실행 후 stdout 반환. 실패 시 빈 문자열."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(PROJECT_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def get_changed_files() -> list[str]:
    """HEAD 대비 변경된 파일 목록 (staged + unstaged + untracked)"""
    files = set()

    # staged
    staged = run_git(["diff", "--cached", "--name-only"])
    if staged:
        files.update(staged.splitlines())

    # unstaged
    unstaged = run_git(["diff", "--name-only"])
    if unstaged:
        files.update(unstaged.splitlines())

    # untracked (추적 안 된 신규 파일)
    untracked = run_git(["ls-files", "--others", "--exclude-standard"])
    if untracked:
        files.update(untracked.splitlines())

    return sorted(files)


def get_recent_commits(n: int = 5) -> list[dict]:
    """최근 n개 커밋 정보 (hash + subject + date)"""
    fmt = "%H|%s|%ai"
    log = run_git(["log", f"-{n}", f"--pretty=format:{fmt}"])
    commits = []
    for line in log.splitlines():
        parts = line.split("|", 2)
        if len(parts) == 3:
            commits.append(
                {"hash": parts[0][:8], "subject": parts[1], "date": parts[2][:19]}
            )
    return commits


def get_current_branch() -> str:
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"]) or "unknown"


def load_session_state() -> dict:
    """session_cleanup.py가 관리하는 세션 상태 파일 읽기"""
    state_file = PROJECT_DIR / ".claude" / "session_state.json"
    if state_file.exists():
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def purge_old_snapshots():
    """TTL 30일 초과 또는 50개 초과 스냅샷 삭제"""
    if not SNAPSHOT_DIR.exists():
        return

    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot-*.json"), key=lambda p: p.stat().st_mtime)
    now = datetime.now(timezone.utc).timestamp()

    # TTL 초과 삭제
    for snap in snapshots[:]:
        age_days = (now - snap.stat().st_mtime) / 86400
        if age_days > TTL_DAYS:
            try:
                snap.unlink()
                snapshots.remove(snap)
            except Exception:
                pass

    # 50개 초과 삭제 (오래된 순)
    while len(snapshots) >= MAX_SNAPSHOTS:
        try:
            snapshots.pop(0).unlink()
        except Exception:
            snapshots.pop(0)


def write_snapshot(snapshot: dict) -> Path:
    """스냅샷 JSON 저장"""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = SNAPSHOT_DIR / f"snapshot-{ts}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False)
    return path


def main():
    try:
        branch = get_current_branch()
        changed_files = get_changed_files()
        recent_commits = get_recent_commits(5)
        session_state = load_session_state()

        snapshot = {
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "branch": branch,
            "project_dir": str(PROJECT_DIR),
            "changed_files": changed_files,
            "recent_commits": recent_commits,
            "session_start": session_state.get("last_start"),
            "pending_tasks": session_state.get("pending_tasks", []),
        }

        # 오래된 스냅샷 정리 후 저장
        purge_old_snapshots()
        snap_path = write_snapshot(snapshot)

        summary_parts = [f"branch={branch}"]
        if changed_files:
            summary_parts.append(f"changed={len(changed_files)}files")
        if recent_commits:
            summary_parts.append(f"last_commit={recent_commits[0]['hash']}")

        print(
            json.dumps(
                {
                    "continue": True,
                    "message": f"[session_snapshot] 스냅샷 저장: {snap_path.name} ({', '.join(summary_parts)})",
                }
            )
        )

    except Exception as e:
        # 스냅샷 실패는 세션 종료를 막지 않음
        print(json.dumps({"continue": True, "error": f"session_snapshot: {e}"}))


if __name__ == "__main__":
    main()
