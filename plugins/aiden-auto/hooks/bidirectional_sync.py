#!/usr/bin/env python3
"""bidirectional_sync.py — Plan B 3축 통합 sync hook (v2.0)

사용자 결정 (2026-05-15): 단일 정본 SSOT 불가 시 Plan B 적용.
"3축 어느 곳에서 편집해도 나머지 자동 sync — 어떤 것도 제거하지 않음"

v2.0 변화 (2026-05-15 QA 결과):
    machine_framework_watcher.py 가 work.md 변경 시 발동 안 함 확인.
    원인 추정: project settings.json PostToolUse 매처가 global 매처를 override.
    해결: 본 hook 이 watcher 책임도 흡수. 5 mirror 모두 단독 처리.

흐름:
    Global edit  (~/.claude/)           ──► Project + Plugin source + cache + marketplaces
    Project edit (C:\\claude\\.claude\\) ──► Global + Plugin source + cache + marketplaces

Plugin 영역은 framework_edit_guard.py 차단으로 사용자 편집 불가 — 수신만.

방어 4중:
    1. SHA256 비교 — sync 후 동일하면 skip (loop 방지)
    2. mtime newest — race condition 시 newer wins
    3. is_self_edit() — watcher/sync hook 자체 제외 (recursion 방지)
    4. atomic write — tmp + os.replace (Windows rollback 안전)

PostToolUse Edit|Write|MultiEdit 매처로 등록.
"""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

# ⭐ Universal Deployment Layer B (2026-05-23, v4.0):
# hardcoded path 제거 — env > autodetect > graceful None 패턴.
# 본 hook 이 import 가능하도록 hooks/ 가 sys.path 에 있어야 함 (CC dispatcher 가 처리).
sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import (  # type: ignore[import-not-found]
        resolve_plugin_source,
        resolve_project_claude,
        resolve_cache_root as _resolve_cache_root_latest,
        resolve_marketplaces_dir,
    )
except ImportError:
    # path_resolution.py 부재 시 graceful fallback (backward compat)
    def resolve_plugin_source(): return Path(r"C:\claude\plugins\aiden-auto") if Path(r"C:\claude\plugins\aiden-auto").is_dir() else None
    def resolve_project_claude(): return Path(r"C:\claude\.claude") if Path(r"C:\claude\.claude").is_dir() else None
    def _resolve_cache_root_latest(): return None
    def resolve_marketplaces_dir(): return None

USER_CLAUDE = Path.home() / ".claude"
# Lazy resolution (각 sync call 마다 재평가 — env 변경 / 디렉토리 생성 반영)
def _get_project_claude(): return resolve_project_claude()
def _get_plugin_source(): return resolve_plugin_source()
# Backward compat constants (legacy code 참조 시 graceful — None 일 수 있음)
PROJECT_CLAUDE = resolve_project_claude() or Path(r"C:\claude\.claude")  # backward compat
PLUGIN_SOURCE = resolve_plugin_source() or Path(r"C:\claude\plugins\aiden-auto")  # backward compat
CACHE_ROOT = USER_CLAUDE / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"
MARKETPLACES = USER_CLAUDE / "plugins" / "marketplaces" / "garimto81-aiden-auto" / "plugins" / "aiden-auto"

SYNC_DIRS = {"agents", "skills", "hooks", "rules", "references", "commands", "lib"}

# EXCLUDE 패턴 (2026-05-15 Part 9 — critic E1 적용)
# node_modules 등 빌드 산출물 + 캐시가 5축 sync 폭발 방지
EXCLUDE_DIR_NAMES = {
    "node_modules",      # JS/TS 의존성 (1만개+ 파일)
    "__pycache__",       # Python 바이트코드 캐시
    "dist",              # 빌드 출력
    ".venv", "venv",     # Python 가상환경
    ".next",             # Next.js 빌드
    ".git",              # git 내부 데이터
    ".cache",            # 일반 캐시
    "build",             # 빌드 산출물
    ".pytest_cache",     # pytest 캐시
    ".mypy_cache",       # mypy 캐시
    ".ruff_cache",       # ruff 캐시
    "coverage",          # 커버리지 산출물
    "htmlcov",           # HTML 커버리지
}

EXCLUDE_FILE_SUFFIXES = {
    ".pyc", ".pyo",      # Python 컴파일
    ".log",              # 로그 파일
    ".swp", ".swo",      # vim swap
    ".bak",              # 백업 파일 (settings.json.pre-dispatcher.bak 등)
}

# EXCLUDE_FILE_NAMES (2026-05-19 critic Agent B S5 + R6 적용)
# 각 layer 의 독립성을 보호하는 파일은 layer 간 sync 차단 필요.
# settings.json — 각 layer 의 hook 등록은 독립이어야 함 (dispatcher pattern 도입 후 핵심).
# CLAUDE.md — 각 layer 의 instructions 는 독립 (Global vs Project).
# .env — 환경 변수 secret 은 layer 간 공유 안 함.
# _silent_wrap.cmd — wrapper 본문이 어떤 layer 에서 변경되어도 다른 layer 로 자동 전파되지 않도록
#                    차단 (본 cycle critic Agent B R6 — lock 폭탄 자동 복귀 사례 방지).
EXCLUDE_FILE_NAMES = {
    "settings.json",
    "settings.local.json",
    "CLAUDE.md",
    ".env",
    ".env.local",
    ".credentials.json",
    "_silent_wrap.cmd",
    "_silent_wrap.cmd.bak",
}


def is_excluded_path(rel: Path) -> tuple[bool, str]:
    """경로가 EXCLUDE 대상인지 확인. 반환: (excluded, reason)."""
    for part in rel.parts:
        if part in EXCLUDE_DIR_NAMES:
            return True, f"excluded_dir:{part}"
    if rel.name in EXCLUDE_FILE_NAMES:
        return True, f"excluded_filename:{rel.name}"
    if rel.suffix in EXCLUDE_FILE_SUFFIXES:
        return True, f"excluded_suffix:{rel.suffix}"
    return False, ""


LOG_FILE = USER_CLAUDE / "state" / "bidirectional-sync.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def sha256_file(p: Path) -> str:
    if not p.exists():
        return ""
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return ""


def is_self_edit(rel_parts: tuple) -> bool:
    """이 hook + machine_framework_watcher 자체 제외 (loop 방지)."""
    if len(rel_parts) >= 2 and rel_parts[0] == "hooks":
        name = rel_parts[-1]
        if any(x in name for x in ("machine_framework_watcher", "bidirectional_sync")):
            return True
    return False


def get_active_cache_versions() -> list[Path]:
    """cache의 모든 버전 디렉토리 (mtime 최신 우선)."""
    if not CACHE_ROOT.exists():
        return []
    versions = [p for p in CACHE_ROOT.iterdir() if p.is_dir()]
    versions.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return versions


def determine_source_and_dests(p: Path) -> tuple[Path | None, list[Path], Path | None]:
    """편집된 파일이 어느 영역인지 감지 + 나머지 모든 mirror 결정.

    Returns:
        (source_root, [dest_root_paths], rel) or (None, [], None) if skip
    """
    p_resolved = p.resolve()

    # Global edit?
    try:
        rel = p_resolved.relative_to(USER_CLAUDE.resolve())
        if rel.parts and rel.parts[0] in SYNC_DIRS and not is_self_edit(rel.parts):
            # EXCLUDE 패턴 검사 (Part 9 E1 적용)
            excluded, reason = is_excluded_path(rel)
            if excluded:
                return None, [], None
            dests = [PROJECT_CLAUDE, PLUGIN_SOURCE]
            dests.extend(get_active_cache_versions())
            dests.append(MARKETPLACES)
            return USER_CLAUDE, dests, rel
    except ValueError:
        pass

    # Project edit?
    try:
        rel = p_resolved.relative_to(PROJECT_CLAUDE.resolve())
        if rel.parts and rel.parts[0] in SYNC_DIRS and not is_self_edit(rel.parts):
            # EXCLUDE 패턴 검사 (Part 9 E1 적용)
            excluded, reason = is_excluded_path(rel)
            if excluded:
                return None, [], None
            dests = [USER_CLAUDE, PLUGIN_SOURCE]
            dests.extend(get_active_cache_versions())
            dests.append(MARKETPLACES)
            return PROJECT_CLAUDE, dests, rel
    except ValueError:
        pass

    return None, [], None


def sync_one(source: Path, dest: Path) -> str:
    """단일 파일 sync. Loop 방지 + atomic + mtime newest.

    Returns: status string ("synced", "skip_same", "skip_newer", "error")
    """
    if not source.exists():
        return "skip_deleted"

    # Loop 방지: SHA 동일하면 skip
    if dest.exists() and sha256_file(source) == sha256_file(dest):
        return "skip_same"

    # Race condition: dest mtime 이 source 보다 newer 면 skip
    if dest.exists():
        try:
            if dest.stat().st_mtime > source.stat().st_mtime + 1:  # 1초 tolerance
                return "skip_newer"
        except OSError:
            pass

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + f".tmp_{os.getpid()}")
        shutil.copy2(source, tmp)
        os.replace(tmp, dest)
        return "synced"
    except Exception as e:
        log(f"sync error: {source} -> {dest}: {e}")
        return "error"


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
        return 0  # 삭제됨 — skip

    source_root, dest_roots, rel = determine_source_and_dests(p)
    if source_root is None or rel is None or not dest_roots:
        return 0  # SYNC_DIRS 밖 또는 self-edit

    synced_count = 0
    skipped_count = 0
    error_count = 0

    for dest_root in dest_roots:
        dest_path = dest_root / rel
        status = sync_one(p, dest_path)
        if status == "synced":
            synced_count += 1
        elif status.startswith("skip"):
            skipped_count += 1
        elif status == "error":
            error_count += 1

    if synced_count > 0 or error_count > 0:
        msg = f"{rel} : {source_root.name} -> {synced_count} synced"
        if skipped_count > 0:
            msg += f" / {skipped_count} skipped"
        if error_count > 0:
            msg += f" / {error_count} errors"
        log(msg)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"FATAL: {e}")
        sys.exit(0)  # hook 실패는 tool 차단 X
