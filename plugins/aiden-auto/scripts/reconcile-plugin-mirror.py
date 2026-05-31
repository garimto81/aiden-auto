#!/usr/bin/env python3
"""reconcile-plugin-mirror.py — 정본 → 전체 mirror 1회 동기화 (P1).

배경 (2026-05-28):
    증분 sync (bidirectional_sync.py / machine_framework_watcher.py) 는 PostToolUse 로
    "편집된 파일 1개씩"만 mirror 로 복사한다. 따라서 sync hook 등록 이전에 만들어졌거나
    그 이후 한 번도 편집되지 않은 자산은 mirror 에 영구 누락된다
    (관측: plugin source agents 79개 중 7개만 존재).

    본 스크립트는 정본 ~/.claude/{SYNC_DIRS} 전체를 EXCLUDE 적용하며 plugin mirror
    (Plugin source + cache 버전들 + Marketplaces) 로 1회 reconcile 하여 부분 mirror 를 완전화한다.
    Project (C:/claude/.claude) + marketplaces 는 dest 제외 — collect_dests() 주석 참조.

P1 확장 (2026-05-28):
    기존엔 Plugin source 1곳만 reconcile 했다. bidirectional_sync 의
    determine_source_and_dests 가 사용하는 dest 패턴을 재사용하여 전체 mirror 로 확장.

설계 (Universal Deployment Premise 정합):
    - 방향: Global(~/.claude/) → mirror 단방향만. Project→Global 역방향 자동 동기화 금지
            (의미 차원 — 사용자 결정 영역). sync_one 이 mtime newest + SHA 비교로
            dest 가 newer 면 skip_newer 보존 → Project 최신 편집 자동 보호.
    - hardcoded path 0: path_resolution / bidirectional_sync 재사용
    - idempotent: bidirectional_sync.sync_one() 의 SHA256 비교로 동일 파일 skip (재실행 0 쓰기)
    - 개인화 격리: SYNC_DIRS 만 대상 + is_excluded_path (settings/CLAUDE.md/.env/credentials 차단)
    - graceful: 각 dest 부재 (신규 PC 등) 시 에러 아닌 skip

사용: python ~/.claude/scripts/reconcile-plugin-mirror.py [--dry-run]
"""
from __future__ import annotations

import sys
from pathlib import Path

HOOKS = Path.home() / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

try:
    from path_resolution import (  # type: ignore[import-not-found]
        resolve_plugin_source,
        resolve_project_claude,
        resolve_marketplaces_dir,
    )
except ImportError:
    def resolve_plugin_source():
        p = Path(r"C:\claude\plugins\aiden-auto")  # backward compat
        return p if p.is_dir() else None

    def resolve_project_claude():
        return None  # graceful — Project 부재 취급

    def resolve_marketplaces_dir():
        return None

from bidirectional_sync import (  # type: ignore[import-not-found]
    SYNC_DIRS,
    is_excluded_path,
    sync_one,
    get_active_cache_versions,
    EXCLUDE_DIR_NAMES,
    # MARKETPLACES 제거 (v3.15 2026-05-30) — marketplaces deregister 후 dest 미사용
)

import os

USER_CLAUDE = Path.home() / ".claude"


def collect_dests() -> list[tuple[str, Path]]:
    """전체 mirror dest 목록 — (label, root). 부재면 graceful skip (목록에서 제외).

    bidirectional_sync.determine_source_and_dests 의 Global edit dest 패턴 재사용:
        Project + Plugin source + cache 버전들 + Marketplaces.
    """
    dests: list[tuple[str, Path]] = []

    # Project (C:\claude\.claude) 는 reconcile dest 에서 제외 (2026-05-28 정정 — autonomous iteration).
    # 이유: (1) rule 19 책임 매트릭스 — Project 는 project-only hooks(4개)만, 글로벌 전체 mirror 아님.
    #       (2) dispatcher 가 Global + Project registry 둘 다 스캔 → 글로벌 hook 사본이 Project 에 있으면
    #           모든 hook double-fire (P2b 의 대규모 재현).
    #       (3) Resolution Priority — Project 부재 시 Global fallback 이므로 전체 mirror 불필요.
    # Plugin source / cache / marketplaces 만 글로벌 전체 mirror 대상 (aiden-auto 배포 mirror).
    # (증분 양방향 sync 는 bidirectional_sync 가 Project↔Global 편집분만 처리 — 별개)

    # Plugin-source (C:\claude\plugins\aiden-auto) deregister — 2026-05-30 사용자 결정.
    # CC 안 읽음(cache 로드) + git 아님(배포=aiden-auto-repo). reconcile dest 에서 제외.
    # 폴더·내용 보존(deregister≠delete). resolve_plugin_source 는 다른 호출처 위해 import 유지.

    for cache_ver in get_active_cache_versions():
        dests.append((f"cache:{cache_ver.name}", cache_ver))

    # Marketplaces deregister — 2026-05-30 사용자 결정. marketplaces 는 CC 관리 git clone
    # (origin=github.com/garimto81/aiden-auto). `marketplace update` 시 CC 가 GitHub 에서 pull 하여
    # 우리 sync 를 덮어씀 → 직접 sync 는 불필요(런타임은 cache 로드)+충돌(tug-of-war, 실측 509 재sync).
    # 배포 경로: 정본 → aiden-auto-repo → GitHub → (CC pull) → marketplaces. READ 소비자 0 확인.
    # (옛 2026-05-29 "reconcile 포함" 정정은 marketplaces 가 CC-managed git clone 임을 모른 상태의 판단 — v3.15 재정정.)

    return dests


def iter_source_files():
    """정본 SYNC_DIRS 의 EXCLUDE 미적용 파일을 (src_path, rel) 로 yield.

    C5 정정 (2026-05-28): rglob 대신 os.walk(topdown=True) + dirnames 가지치기.
    node_modules / __pycache__ 등 EXCLUDE_DIR_NAMES 디렉토리는 **진입 전 차단**
    → 수만 파일 stat 비용 회피 (timeout 60s 안전 마진 확보).
    """
    for d in sorted(SYNC_DIRS):
        src_dir = USER_CLAUDE / d
        if not src_dir.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(src_dir, topdown=True):
            # 디렉토리 레벨 가지치기 — node_modules / __pycache__ 등 진입 차단
            dirnames[:] = [dn for dn in dirnames if dn not in EXCLUDE_DIR_NAMES]
            for fn in filenames:
                sp = Path(dirpath) / fn
                rel = sp.relative_to(USER_CLAUDE)
                excluded, _ = is_excluded_path(rel)
                if excluded:
                    continue
                yield sp, rel


def main() -> int:
    dry_run = "--dry-run" in sys.argv

    dests = collect_dests()
    if not dests:
        print("reconcile: 모든 mirror dest 부재 — graceful skip")
        return 0

    print(f"reconcile: 정본 {USER_CLAUDE} -> {len(dests)} mirror(s)  (dry_run={dry_run})")

    source_files = list(iter_source_files())

    # dest 별 집계: missing(dry) / synced / skipped / errors
    totals = {label: {"missing": 0, "synced": 0, "skipped": 0, "errors": 0}
              for label, _ in dests}
    project_only = 0  # Project 에만 있고 Global 정본엔 부재 (보고만)

    for label, dest_root in dests:
        for sp, rel in source_files:
            dest = dest_root / rel
            if dry_run:
                if not dest.exists():
                    totals[label]["missing"] += 1
                continue
            st = sync_one(sp, dest, force=True)  # plugin mirror read-only → Global-SHA 무조건 승 (skip_newer 우회, skip_same 유지)
            if st == "synced":
                totals[label]["synced"] += 1
            elif st == "error":
                totals[label]["errors"] += 1
            else:
                totals[label]["skipped"] += 1

    # Project-only 항목 탐지 (Global 부재 — 자동 sync 안 함, 보고만).
    # ⚠ 현재 dead code: Project 가 collect_dests() dest 제외(2026-05-28, double-fire 방지)
    #    이후 project_root 항상 None → 본 블록 미진입. 미래 재활성화 대비 보존.
    # C5 정정 (2026-05-28): rglob → os.walk topdown 가지치기 (node_modules 등 진입 차단).
    project_root = next((root for lbl, root in dests if lbl == "project"), None)
    if project_root is not None:
        for d in sorted(SYNC_DIRS):
            pdir = project_root / d
            if not pdir.is_dir():
                continue
            for dirpath, dirnames, filenames in os.walk(pdir, topdown=True):
                dirnames[:] = [dn for dn in dirnames if dn not in EXCLUDE_DIR_NAMES]
                for fn in filenames:
                    pp = Path(dirpath) / fn
                    rel = pp.relative_to(project_root)
                    excluded, _ = is_excluded_path(rel)
                    if excluded:
                        continue
                    if not (USER_CLAUDE / rel).exists():
                        project_only += 1

    # 출력
    if dry_run:
        for label, _ in dests:
            t = totals[label]
            print(f"  [{label}] {t['missing']} files missing (would sync)")
        if project_root is not None:
            print(f"  [project-only] {project_only} files in Project but absent in Global "
                  f"(NOT auto-synced — 역방향 금지, 보고만)")
    else:
        for label, _ in dests:
            t = totals[label]
            print(f"  [{label}] {t['synced']} synced, {t['skipped']} skipped "
                  f"(same/newer), {t['errors']} errors")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
