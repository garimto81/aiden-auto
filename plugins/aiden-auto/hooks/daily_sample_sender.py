#!/usr/bin/env python3
"""
PostToolUse Hook — /daily 관련 파일 수정 시 샘플 보고서 Slack 자동 전송

트리거 파일:
  - skills/daily/SKILL.md
  - secretary/config/projects.json
  - secretary/scripts/morning_briefing.py
  - secretary/scripts/work_tracker/ (daily 관련)
"""

import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path

DAILY_PATTERNS = [
    "skills/daily/",
    "secretary/config/projects.json",
    "secretary/scripts/morning_briefing.py",
    "work_tracker/cli.py",
    "daily_report_",
]

SECRETARY_DIR = Path(r"C:\claude\secretary")
COOLDOWN_FILE = Path(r"C:\claude\.claude\logs\daily_sample_last.txt")


def is_daily_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    return any(p in normalized for p in DAILY_PATTERNS)


def is_in_cooldown() -> bool:
    """5분 쿨다운 — 연속 수정 시 중복 전송 방지."""
    try:
        if COOLDOWN_FILE.exists():
            last = float(COOLDOWN_FILE.read_text().strip())
            if (datetime.now().timestamp() - last) < 300:
                return True
    except Exception:
        pass
    return False


def set_cooldown():
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(str(datetime.now().timestamp()))


def find_latest_report() -> Path | None:
    data_dir = SECRETARY_DIR / "data"
    if not data_dir.exists():
        return None
    reports = sorted(data_dir.glob("daily_report_*.md"), reverse=True)
    return reports[0] if reports else None


def send_sample():
    report = find_latest_report()
    if not report:
        return

    try:
        subprocess.run(
            [
                sys.executable, "-m", "scripts.work_tracker",
                "post", "--confirm",
                "--report-file", str(report),
            ],
            cwd=SECRETARY_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        pass


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            return

        data = json.loads(input_data)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        if not file_path or not is_daily_file(file_path):
            return

        if is_in_cooldown():
            return

        set_cooldown()
        send_sample()

    except Exception:
        pass


if __name__ == "__main__":
    main()
