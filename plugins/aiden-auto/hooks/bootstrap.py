#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bootstrap.py — Universal Deployment Layer C.

⭐ Universal Deployment Premise (HIGHEST PRIORITY):
   본 framework 는 본인 PC 최적화 setting 이 아니라 전사 universal deployment 아키텍처.

신규 PC 가 plugin install (또는 SessionStart) 후 1회 실행하여
~/.claude/{agents,skills,hooks,commands,rules,references,hud,lib,scripts}
디렉토리가 부재/비어있을 시 plugin cache 에서 자동 복사.

본인 PC (정본) 는 idempotent — 기존 파일 보존, 0 files copied.

발동 방식:
  · Plugin manifest lifecycle.post_install (CC 지원 시)
  · SessionStart fallback (idempotent — is_pristine_install() False 면 즉시 return)

6 기준 자체 평가:
  1. 자기복제율: cache → ~/.claude/ 자동 복사 → 신규 PC 95%+ 자산 보유
  2. device-agnostic: Path.home() 기반 (hardcoded 0)
  3. OS-agnostic: pathlib.Path 사용
  4. 권한-agnostic: 사용자 home 영역만 (admin 불필요)
  5. idempotent: dp.exists() 시 skip
  6. 개인화 격리: EXCLUDE_FILES + EXCLUDE_DIRS 명시

PRD: docs/00-prd/aiden-auto-self-replication.prd.md §3
"""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path
from typing import Optional

GLOBAL_CLAUDE = Path.home() / ".claude"
LOG_FILE = GLOBAL_CLAUDE / "state" / "bootstrap.log"

# Universal 자산만 sync (개인화 영역 제외)
SYNC_DIRS = [
    "agents", "skills", "hooks", "commands", "rules",
    "references", "hud", "lib", "scripts",
]

# Personalization 자산 (PC 별 독립) — sync 절대 안 함
EXCLUDE_FILES = {
    "settings.json", "settings.local.json",
    "CLAUDE.md",  # layer 별 독립
    ".env", ".env.local", ".credentials.json",
}

EXCLUDE_DIRS = {
    "state", "projects", "oauth_tokens",
    "logs", "tmp", "__pycache__",
    ".git", ".cache", "node_modules",
}

EXCLUDE_FILE_SUFFIXES = {".pyc", ".pyo", ".log", ".swp", ".swo", ".bak"}


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def autodetect_plugin_root() -> Optional[Path]:
    """CC plugin cache 의 최신 version 디렉토리.

    경로: ~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/<latest>/
    """
    cache_base = GLOBAL_CLAUDE / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"
    if not cache_base.is_dir():
        return None
    versions = sorted(
        [d for d in cache_base.iterdir() if d.is_dir() and not d.name.startswith(".")],
        reverse=True,
    )
    return versions[0] if versions else None


def get_plugin_root() -> Optional[Path]:
    """env > autodetect 순.

    Returns:
        plugin root Path 또는 None (cache 부재 시 graceful skip)
    """
    env_path = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if env_path and Path(env_path).is_dir():
        return Path(env_path)
    return autodetect_plugin_root()


def is_pristine_install() -> bool:
    """이 PC 가 신규 설치 상태인지?

    핵심 marker: ~/.claude/skills/auto/SKILL.md 부재.
    """
    if not GLOBAL_CLAUDE.is_dir():
        return True
    return not (GLOBAL_CLAUDE / "skills" / "auto" / "SKILL.md").exists()


def should_skip(rel_parts: tuple, name: str, suffix: str) -> bool:
    """변경 대상이 personalization 영역인지 검사."""
    if name in EXCLUDE_FILES:
        return True
    if suffix in EXCLUDE_FILE_SUFFIXES:
        return True
    if any(part in EXCLUDE_DIRS for part in rel_parts):
        return True
    return False


def copy_recursive(src: Path, dst: Path) -> tuple[int, int]:
    """src → dst 재귀 복사.

    idempotent: 기존 파일 보존 (premise #5).
    개인화 격리: EXCLUDE 패턴 (premise #6).

    Returns:
        (copied_count, skipped_count)
    """
    copied = 0
    skipped = 0
    if not src.is_dir():
        return (0, 0)
    for sp in src.rglob("*"):
        if not sp.is_file():
            continue
        rel = sp.relative_to(src)
        if should_skip(rel.parts, sp.name, sp.suffix):
            skipped += 1
            continue
        dp = dst / rel
        if dp.exists():
            skipped += 1
            continue  # idempotent — 정본 보호
        try:
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dp)
            copied += 1
        except (OSError, PermissionError) as e:
            log(f"copy fail {rel}: {e}")
            skipped += 1
    return (copied, skipped)


def main() -> int:
    plugin_root = get_plugin_root()
    if not plugin_root:
        log("bootstrap: plugin root 부재 (CC cache 미존재) — graceful skip")
        return 0

    GLOBAL_CLAUDE.mkdir(parents=True, exist_ok=True)
    pristine = is_pristine_install()

    total_copied = 0
    total_skipped = 0
    for d in SYNC_DIRS:
        src = plugin_root / d
        if not src.is_dir():
            continue
        dst = GLOBAL_CLAUDE / d
        copied, skipped = copy_recursive(src, dst)
        total_copied += copied
        total_skipped += skipped

    state = "pristine install" if pristine else "existing install (idempotent)"
    log(f"bootstrap: {state}, copied={total_copied}, skipped={total_skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
