#!/usr/bin/env python3
"""framework_edit_guard.py — PreToolUse hook (Edit|Write|MultiEdit)

v4 정책 (2026-05-14 plan v4): ~/.claude/ 가 source of truth.
plugin/cache/marketplaces 위치는 read-only auto-mirror.

이 hook은 보호된 경로의 Edit/Write 시도를 차단하고
~/.claude/ 동일 위치에서 작업하도록 안내.

쌍 hook: PostToolUse machine_framework_watcher.py (자동 sync).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

USER_CLAUDE = Path(r"C:\Users\AidenKim\.claude").resolve()

PROTECTED_PATHS = [
    Path(r"C:\claude\plugins").resolve(),
    USER_CLAUDE / "plugins" / "cache",
    USER_CLAUDE / "plugins" / "marketplaces",
]

# Plugin 루트 파일: ~/.claude/ mirror 없는 plugin 배포 메타데이터.
# guard 차단 범위(plugin 전체) > watcher sync 범위(SYNC_DIRS 7개) 사각지대 해소.
# Edit 허용 조건: parent == PLUGIN_ROOT AND filename in WHITELIST (하위 디렉토리 보호 유지).
PLUGIN_ROOT = Path(r"C:\claude\plugins\aiden-auto").resolve()
ROOT_FILE_WHITELIST = {
    ".gitignore",
    "CLAUDE.md",
    "INTRODUCTION.md",
    "plugin.json",
    "README.md",
}


def find_redirect_path(target_str: str) -> str | None:
    """plugin/cache/marketplaces 경로를 ~/.claude/ 대응 경로로 변환."""
    norm = target_str.replace("\\", "/")
    # plugin/aiden-auto/{rest} -> ~/.claude/{rest}
    markers = [
        "plugins/aiden-auto/",
        "plugins/cache/garimto81-aiden-auto/aiden-auto/",
        "plugins/marketplaces/garimto81-aiden-auto/plugins/aiden-auto/",
    ]
    for marker in markers:
        if marker in norm:
            rest = norm.split(marker, 1)[1]
            # cache marker에서는 다음 path component가 version (e.g., "28.2.0/")
            if marker.endswith("aiden-auto/") and "/cache/" in marker:
                parts = rest.split("/", 1)
                if len(parts) > 1 and parts[0].count(".") >= 1:
                    rest = parts[1]
            return str(USER_CLAUDE / rest).replace("\\", "/")
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # parse 실패 시 silently 통과

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""

    if not file_path:
        return 0

    try:
        target = Path(file_path).resolve()
    except Exception:
        return 0

    # Plugin distribution metadata bypass: ~/.claude/ mirror 없으므로 in-place edit 허용
    if target.parent == PLUGIN_ROOT and target.name in ROOT_FILE_WHITELIST:
        return 0

    for protected in PROTECTED_PATHS:
        try:
            target.relative_to(protected)
        except ValueError:
            continue

        # 보호된 경로 안의 Edit 시도 — block + redirect 안내
        redirect = find_redirect_path(str(target))
        msg_lines = [
            f"[v4 정책 차단] 보호된 경로 편집 시도: {target}",
            "plugin/cache/marketplaces는 read-only auto-mirror입니다.",
        ]
        if redirect:
            msg_lines.append(f"대신 ~/.claude/ 위치에서 작업하세요: {redirect}")
            msg_lines.append(
                "machine_framework_watcher.py가 자동으로 plugin/cache/marketplaces로 sync합니다."
            )
        print("\n".join(msg_lines), file=sys.stderr)
        return 2  # exit code 2 = block tool execution (CC convention)

    return 0


if __name__ == "__main__":
    sys.exit(main())
