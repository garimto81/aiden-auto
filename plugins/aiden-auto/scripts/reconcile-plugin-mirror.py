#!/usr/bin/env python3
"""reconcile-plugin-mirror.py — 정본 → plugin mirror 전체 1회 동기화.

배경 (2026-05-28):
    증분 sync (bidirectional_sync.py / machine_framework_watcher.py) 는 PostToolUse 로
    "편집된 파일 1개씩"만 mirror 로 복사한다. 따라서 sync hook 등록 이전에 만들어졌거나
    그 이후 한 번도 편집되지 않은 자산은 plugin mirror (C:\\claude\\plugins\\aiden-auto) 에
    영구 누락된다 (관측: agents 79개 중 7개만 존재).

    본 스크립트는 정본 ~/.claude/{SYNC_DIRS} 전체를 EXCLUDE 적용하며 plugin mirror 로
    1회 reconcile 하여 부분 mirror 를 완전화한다.

설계 (Universal Deployment Premise 정합):
    - hardcoded path 0: path_resolution.resolve_plugin_source() 사용
    - idempotent: bidirectional_sync.sync_one() 의 SHA256 비교로 동일 파일 skip
    - 개인화 격리: SYNC_DIRS 만 대상 (state/projects/memory 등 비포함)
                  + bidirectional_sync.EXCLUDE_FILE_NAMES (settings/credentials 등) 적용
    - graceful: plugin source 부재 (신규 PC 등) 시 에러 아닌 skip

사용: python ~/.claude/scripts/reconcile-plugin-mirror.py [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

try:
    from path_resolution import resolve_plugin_source  # type: ignore[import-not-found]
except ImportError:
    def resolve_plugin_source():
        p = Path(r"C:\claude\plugins\aiden-auto")
        return p if p.is_dir() else None

from bidirectional_sync import SYNC_DIRS, is_excluded_path, sync_one  # type: ignore[import-not-found]

USER_CLAUDE = Path.home() / ".claude"


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    dest_root = resolve_plugin_source()
    if dest_root is None:
        print("reconcile: plugin source 부재 — graceful skip")
        return 0

    print(f"reconcile: 정본 {USER_CLAUDE} -> mirror {dest_root}  (dry_run={dry_run})")
    synced = skipped = errors = would = 0

    for d in sorted(SYNC_DIRS):
        src_dir = USER_CLAUDE / d
        if not src_dir.is_dir():
            continue
        for sp in src_dir.rglob("*"):
            if not sp.is_file():
                continue
            rel = sp.relative_to(USER_CLAUDE)
            excluded, _ = is_excluded_path(rel)
            if excluded:
                continue
            dest = dest_root / rel
            if dry_run:
                if not dest.exists():
                    would += 1
                continue
            st = sync_one(sp, dest)
            if st == "synced":
                synced += 1
            elif st == "error":
                errors += 1
            else:
                skipped += 1

    if dry_run:
        print(f"reconcile dry-run: {would} files missing in mirror (would sync)")
    else:
        print(f"reconcile done: {synced} synced, {skipped} skipped (same/newer), {errors} errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
