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
SYNC_DIRS = {"agents", "skills", "hooks", "rules", "references", "commands", "lib"}

# ⭐ Universal Deployment Layer B (2026-05-23, v4.0):
# hardcoded path 제거. path_resolution 모듈로 위임.
import sys as _sys
_sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import resolve_plugin_source  # type: ignore[import-not-found]
except ImportError:
    def resolve_plugin_source(): return Path(r"C:\claude\plugins\aiden-auto") if Path(r"C:\claude\plugins\aiden-auto").is_dir() else None

# P5 (B-018 critic 2026-05-28): layer-독립 파일 누출 차단.
# bidirectional_sync 의 EXCLUDE 정책을 재사용 (단일 소스 — EXCLUDE drift 방지).
# settings.json / CLAUDE.md / .env / _silent_wrap.cmd 등이 watcher 로 전파되지 않도록.
try:
    from bidirectional_sync import is_excluded_path as _is_excluded  # type: ignore[import-not-found]
except ImportError:
    def _is_excluded(rel):  # graceful fallback (bidirectional 부재 시 기존 동작)
        return (False, "")

# Lazy + backward compat (legacy code 참조 시)
PROJECT_SOURCE = resolve_plugin_source() or Path(r"C:\claude\plugins\aiden-auto")  # backward compat
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


def get_active_cache_versions() -> list[Path]:
    """cache의 모든 버전 디렉토리 반환 (mtime 최신 우선)."""
    if not CACHE_ROOT.exists():
        return []
    versions = [p for p in CACHE_ROOT.iterdir() if p.is_dir()]
    versions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return versions


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

    targets = [PROJECT_SOURCE / rel]
    targets.extend((cache_v / rel) for cache_v in get_active_cache_versions())
    targets.append(MARKETPLACES / rel)

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
