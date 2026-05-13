#!/usr/bin/env python3
"""
aiden_bootstrap.py — SessionStart 부트스트랩

세션 시작 시:
1. 환경 자동 감지 (OS, profile, eco mode)
2. state/runtime.yml 작성
3. 결과를 stdout으로 알림 (Claude에게 컨텍스트 주입)

사용자 진입점 0회. 100% 자율.
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

# lib/path_abstraction를 import 가능하도록 sys.path 추가
PLUGIN_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))


def main():
    try:
        from lib.path_abstraction import detect_runtime, write_runtime_file
    except ImportError as e:
        print(json.dumps({"decision": "approve", "warning": f"path_abstraction import failed: {e}"}))
        return

    # stdin에서 hook 페이로드 받기 (있다면)
    try:
        payload_raw = sys.stdin.read()
        payload = json.loads(payload_raw) if payload_raw.strip() else {}
    except Exception:
        payload = {}

    project_dir = (
        payload.get("project_dir")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )

    runtime = detect_runtime(project_dir=project_dir)
    runtime_file = PLUGIN_ROOT / "state" / "runtime.yml"
    write_runtime_file(runtime, runtime_file)

    # Claude에게 컨텍스트 주입 (SessionStart additional context)
    context_msg = (
        f"aiden-auto v28.0 bootstrap complete\n"
        f"  OS: {runtime.os} | Shell: {runtime.shell}\n"
        f"  Profile: {runtime.profile} | Eco: {runtime.eco_mode}\n"
        f"  Plugin root: {runtime.plugin_root}\n"
        f"  Project dir: {runtime.project_dir}\n"
        f"  Runtime file: {runtime_file}"
    )

    result = {
        "decision": "approve",
        "additional_context": context_msg,
        "runtime": runtime.to_dict(),
    }
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
