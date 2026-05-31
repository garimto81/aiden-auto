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
import os
import sys
from pathlib import Path

USER_CLAUDE = (Path.home() / ".claude").resolve()  # device-agnostic (2026-05-31, 외부배포 critic M1 — 옛 하드코딩 C:\Users\AidenKim 제거)


def _legacy_plugin_dir() -> Path | None:
    """옛 mirror 위치(deregistered) backward-compat 보호 — device-agnostic.

    외부배포 HIGH-1 (2026-05-31, 6관점 검증): 옛 하드코딩 `C:\\claude\\plugins` 리터럴 제거.
    이제 CLAUDE_LEGACY_PLUGIN_DIR env 가 set + 실재할 때만 보호 대상(미설정/부재 시 inert).
    → 다른 드라이브/macOS/Linux 신규 PC 에서 premise② hardcoded-path 0 충족.
    """
    raw = os.environ.get("CLAUDE_LEGACY_PLUGIN_DIR", "")
    if not raw:
        return None
    try:
        p = Path(raw).resolve()
        return p if p.exists() else None
    except Exception:
        return None


_LEGACY_PLUGINS_DIR = _legacy_plugin_dir()  # 1회 평가 (env-gated, 보통 None)

PROTECTED_PATHS = [
    p for p in (
        _LEGACY_PLUGINS_DIR,                        # backward compat (env-gated, 부재 시 None)
        USER_CLAUDE / "plugins" / "cache",
        USER_CLAUDE / "plugins" / "marketplaces",
    ) if p is not None
]

# Plugin 루트 파일: ~/.claude/ mirror 없는 plugin 배포 메타데이터.
# guard 차단 범위(plugin 전체) > watcher sync 범위(SYNC_DIRS 7개) 사각지대 해소.
# Edit 허용 조건: parent == PLUGIN_ROOT AND filename in WHITELIST (하위 디렉토리 보호 유지).
# 외부배포 HIGH-1: 하드코딩 device 경로 제거 — legacy mirror env 설정 시에만 활성(부재 시 None).
PLUGIN_ROOT = (_LEGACY_PLUGINS_DIR / "aiden-auto") if _LEGACY_PLUGINS_DIR else None
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
    if PLUGIN_ROOT is not None and target.parent == PLUGIN_ROOT and target.name in ROOT_FILE_WHITELIST:
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