#!/usr/bin/env python3
"""machine_framework_watcher.py — PostToolUse hook (Edit|Write|MultiEdit)

v4 정책 (2026-05-14 plan v4): ~/.claude/ 가 source of truth.
Edit/Write 발생 시 plugin/cache/marketplaces 4 mirror로 즉시 자동 sync.

사용자 진입점 0 — 사용자가 ~/.claude/ 만 편집하면 plugin은 hook이 자동 mirror.
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

USER_CLAUDE = Path.home() / ".claude"
# ⭐ Universal Deployment Layer B (2026-05-23, v4.0):
# hardcoded path 제거. path_resolution 모듈로 위임.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import resolve_plugin_source  # type: ignore[import-not-found]
except ImportError:
    # 외부배포 HIGH-1 (2026-05-31): 하드코딩 device 경로 제거 — cwd 상대 후보 + None.
    def resolve_plugin_source():
        c = Path.cwd() / "plugins" / "aiden-auto"
        return c if c.is_dir() else None

# P5 (B-018 critic 2026-05-28): layer-독립 파일 누출 차단.
# bidirectional_sync 의 EXCLUDE 정책 + SYNC_DIRS 를 재사용 (단일 소스 — drift 방지).
# settings.json / CLAUDE.md / .env / _silent_wrap.cmd 등이 watcher 로 전파되지 않도록.
# SYNC_DIRS 단일 소스화 (2026-05-29 3축 동기화 critic iter1): 옛 watcher 로컬 정의는 7개(hud/scripts 누락)라
#   bidirectional(9개)과 비대칭 → 백업 sync layer 가 hud/scripts 를 미동기화하던 결함. import 로 영구 정합.
try:
    from bidirectional_sync import is_excluded_path as _is_excluded, SYNC_DIRS, get_active_cache_versions  # type: ignore[import-not-found]
except ImportError:
    def _is_excluded(rel):  # graceful fallback (bidirectional 부재 시 기존 동작)
        return (False, "")
    SYNC_DIRS = {"agents", "skills", "hooks", "rules", "references", "commands", "lib", "hud", "scripts", "workflows"}  # fallback = 10개 (bidirectional 정합, +workflows v28.9)
    def get_active_cache_versions():  # fallback — junction dedup + 버전명 정렬 (3축 critic iter1 정합)
        if not CACHE_ROOT.exists():
            return []
        seen, uniq = set(), []
        for p in CACHE_ROOT.iterdir():
            if p.is_dir() and p.resolve() not in seen:
                seen.add(p.resolve()); uniq.append(p)
        def _vk(x):
            try: return tuple(int(i) for i in x.name.split("."))
            except ValueError: return (0,)
        uniq.sort(key=_vk, reverse=True); return uniq

# Lazy + backward compat (legacy code 참조 시 — 현재 미사용, None 가능)
# 외부배포 HIGH-1 (2026-05-31): 하드코딩 device 경로 폴백 제거.
PROJECT_SOURCE = resolve_plugin_source()
CACHE_ROOT = USER_CLAUDE / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"
MARKETPLACES = USER_CLAUDE / "plugins" / "marketplaces" / "garimto81-aiden-auto" / "plugins" / "aiden-auto"

LOG_FILE = USER_CLAUDE / "state" / "machine-framework-sync.log"


def log(msg: str) -> None:
    """간단한 stderr + 파일 로깅."""
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


# get_active_cache_versions: bidirectional_sync 에서 import (단일 소스 — 위 import 블록).
# 옛 로컬 def (mtime 정렬) 제거 (2026-05-29 3축 critic iter1): junction dedup + 버전명 정렬로 단일화.


def is_self_edit(rel_parts: tuple) -> bool:
    """이 hook 자체를 sync에서 제외 (무한 루프 방지)."""
    if len(rel_parts) >= 2 and rel_parts[0] == "hooks" and "machine_framework_watcher" in rel_parts[-1]:
        return True
    return False


def sync_to_mirrors(source: Path, rel: Path) -> tuple[int, list[str]]:
    """source 파일을 3+ mirror 위치에 atomic 복사 + 백업.

    v4 Phase 2.5 보강:
    - 백업: 기존 파일을 ~/.claude/.backup/{timestamp}/ 로 보존
    - Atomic write: tmp 파일 + os.replace (rollback 안전)
    - drift 감지: dst가 source와 다르면 백업 (overwrite 손실 방지)
    """
    import os

    ts = time.strftime("%Y%m%d_%H%M%S")
    backup_dir = USER_CLAUDE / ".backup" / ts

    # Plugin-source + Marketplaces deregister — 2026-05-30. cache(런타임 로드)만 mirror.
    # marketplaces 는 CC 관리 git clone (GitHub pull 로 덮어씀 → 직접 sync 불필요+충돌). Project 는 bidirectional_sync 담당.
    targets = [(cache_v / rel) for cache_v in get_active_cache_versions()]

    success = 0
    errors = []
    for dst in targets:
        tmp = None
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)

            # 백업 (기존 dst 보존 — drift 감지 시 손실 방지)
            if dst.exists():
                try:
                    safe_name = str(dst).replace("\\", "/").replace(":", "").replace("/", "_")[-150:]
                    backup_path = backup_dir / safe_name
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dst, backup_path)
                except Exception:
                    pass  # 백업 실패는 sync 중단 X (best-effort)

            # Atomic write: tmp -> os.replace
            tmp = dst.with_suffix(dst.suffix + f".tmp_{os.getpid()}")
            shutil.copy2(source, tmp)
            os.replace(tmp, dst)
            tmp = None  # success
            success += 1
        except Exception as e:
            errors.append(f"{dst}: {e}")
            # tmp 정리
            if tmp is not None and tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
    return success, errors


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # stdin payload 없음 — skip silently

    tool_input = payload.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""

    if not file_path:
        return 0

    p = Path(file_path)
    if not p.exists():
        return 0  # 삭제된 파일 — skip

    # ~/.claude/ 안의 파일인지 확인
    try:
        rel = p.resolve().relative_to(USER_CLAUDE.resolve())
    except ValueError:
        return 0  # ~/.claude/ 밖 — skip

    # SYNC_DIRS에 속하는지 확인
    if not rel.parts or rel.parts[0] not in SYNC_DIRS:
        return 0

    # 자기 자신 sync 방지
    if is_self_edit(rel.parts):
        return 0

    # P5 (B-018 critic): EXCLUDE 검사 — layer-독립 파일(settings/CLAUDE.md/_silent_wrap 등) 차단
    excluded, _reason = _is_excluded(rel)
    if excluded:
        return 0

    # 3+ mirror sync
    success, errors = sync_to_mirrors(p, rel)
    log(f"synced {rel} -> {success} mirror(s)" + (f" | errors: {errors}" if errors else ""))

    return 0


if __name__ == "__main__":
    sys.exit(main())
