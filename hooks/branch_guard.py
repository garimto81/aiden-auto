#!/usr/bin/env python3
"""
브랜치 보호 Hook - main 브랜치에서 코드 수정 차단

PreToolUse(Edit|Write) 이벤트에서 실행됩니다.
"""

import json
import subprocess
import sys
import os
from pathlib import Path


def _get_project_dir() -> str:
    """프로젝트 디렉토리를 동적으로 감지"""
    if env_dir := os.environ.get("CLAUDE_PROJECT_DIR"):
        return env_dir
    # 스크립트 위치 기반 감지
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent.parent
    if (project_root / ".claude").exists():
        return str(project_root)
    return os.getcwd()


PROJECT_DIR = _get_project_dir()

# 수정 허용 파일 패턴 (main에서도 가능)
ALLOWED_PATTERNS = [
    "CLAUDE.md",
    ".claude/",
    "docs/",
    "README.md",
    "CHANGELOG.md",
    ".gitignore",
]


def get_current_branch() -> str:
    """현재 브랜치 이름 반환"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=PROJECT_DIR,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def is_allowed_file(file_path: str) -> bool:
    """main에서도 수정 허용되는 파일인지 확인"""
    # Windows/Unix 경로 호환을 위해 슬래시로 통일
    normalized_path = file_path.replace("\\", "/")
    for pattern in ALLOWED_PATTERNS:
        if pattern in normalized_path:
            return True
    return False


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "approve"}))
            return

        data = json.loads(input_data)
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path", "")

        branch = get_current_branch()

        # main/master 브랜치에서 코드 수정 시 차단
        if branch in ["main", "master"]:
            if file_path and not is_allowed_file(file_path):
                print(
                    json.dumps(
                        {
                            "decision": "block",
                            "reason": f"🚫 main 브랜치에서 코드 수정 금지\n\n"
                            f"📁 파일: {file_path}\n"
                            f"📌 현재 브랜치: {branch}\n\n"
                            f"✅ 해결방법:\n"
                            f"   git checkout -b feat/issue-N-description\n"
                            f"   또는 /issue create로 이슈 먼저 생성",
                        }
                    )
                )
                return

        print(json.dumps({"decision": "approve"}))

    except Exception as e:
        # 에러 시 허용 (Hook 실패로 작업 차단 방지)
        print(json.dumps({"decision": "approve", "error": str(e)}))


if __name__ == "__main__":
    main()
