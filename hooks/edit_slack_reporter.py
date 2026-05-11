#!/usr/bin/env python3
"""
PostToolUse Hook — 코드 수정 시 Slack 자동 보고 (5분 쿨다운 배치)

매 Edit/Write마다 JSONL 로그에 누적하고, 5분 경과 시 배치 전송.
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

CHANGE_LOG = Path(r"C:\claude\.claude\logs\edit_changes.jsonl")
COOLDOWN_FILE = Path(r"C:\claude\.claude\logs\edit_slack_last.txt")
COOLDOWN_SEC = 300  # 5분
SLACK_CHANNEL = "C0985UXQN6Q"
MAX_FILES_DISPLAY = 10

SKIP_PATTERNS = [
    "node_modules", ".git/", ".venv", "dist/", "build/",
    "__pycache__", ".pytest_cache", ".pyc", ".min.",
    "package-lock.json", "yarn.lock",
]


def should_skip(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return any(p in normalized for p in SKIP_PATTERNS)


def append_log(file_path: str, tool_name: str):
    """변경 로그에 항목 추가."""
    CHANGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = json.dumps({
        "file": file_path.replace("\\", "/"),
        "ts": datetime.now().isoformat(),
        "tool": tool_name,
    })
    with open(CHANGE_LOG, "a", encoding="utf-8") as f:
        f.write(entry + "\n")


def is_in_cooldown() -> bool:
    try:
        if COOLDOWN_FILE.exists():
            last = float(COOLDOWN_FILE.read_text().strip())
            return (datetime.now().timestamp() - last) < COOLDOWN_SEC
    except Exception:
        pass
    return False


def set_cooldown():
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(str(datetime.now().timestamp()))


def read_and_clear_log() -> list[dict]:
    """로그 읽고 truncate."""
    entries = []
    if not CHANGE_LOG.exists():
        return entries
    try:
        with open(CHANGE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entries.append(json.loads(line))
        CHANGE_LOG.write_text("")  # truncate
    except Exception:
        pass
    return entries


def get_git_info() -> tuple[str, str]:
    """프로젝트명과 브랜치 반환."""
    project, branch = "unknown", "unknown"
    try:
        cwd = os.environ.get("CLAUDE_PROJECT_DIR", r"C:\claude")
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd, capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
        project = Path(cwd).name
    except Exception:
        pass
    return project, branch


def send_slack(entries: list[dict]):
    """누적 변경 요약을 Slack으로 전송."""
    if not entries:
        return

    # 고유 파일 목록 (순서 보존)
    seen = set()
    files = []
    for e in entries:
        f = e.get("file", "")
        if f and f not in seen:
            seen.add(f)
            files.append(f)

    # 시간 범위
    timestamps = [e.get("ts", "") for e in entries if e.get("ts")]
    first = timestamps[0][:5] if timestamps else "?"  # HH:MM
    last = timestamps[-1][:5] if timestamps else "?"
    # ISO → HH:MM
    try:
        first = datetime.fromisoformat(timestamps[0]).strftime("%H:%M")
        last = datetime.fromisoformat(timestamps[-1]).strftime("%H:%M")
    except Exception:
        pass

    project, branch = get_git_info()

    # 파일 목록 포맷
    display_files = files[:MAX_FILES_DISPLAY]
    file_lines = "\n".join(f"  • {f}" for f in display_files)
    extra = len(files) - MAX_FILES_DISPLAY
    if extra > 0:
        file_lines += f"\n  ... 외 {extra}개"

    msg = (
        f"✏️ 코드 수정 알림\n\n"
        f"프로젝트: {project} ({branch})\n"
        f"시간: {first}~{last}\n"
        f"수정 파일 ({len(files)}개):\n{file_lines}"
    )

    try:
        subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.path.insert(0, r'C:\\claude'); "
             "from lib.slack.client import SlackClient; "
             "SlackClient().send_message(sys.argv[1], sys.stdin.read())",
             SLACK_CHANNEL],
            input=msg, capture_output=True, text=True, timeout=10,
        )
    except Exception:
        pass  # silent fail — 사용자 작업 블로킹 방지


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return

        data = json.loads(input_data)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path or should_skip(file_path):
            return

        tool_name = data.get("tool_name", "unknown")
        append_log(file_path, tool_name)

        if is_in_cooldown():
            return

        # 쿨다운 경과 → 배치 전송
        entries = read_and_clear_log()
        if entries:
            set_cooldown()
            send_slack(entries)

    except Exception:
        pass


if __name__ == "__main__":
    main()
