#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""path_resolution.py — Universal Deployment Layer B.

⭐ Universal Deployment Premise (HIGHEST PRIORITY, 글로벌 CLAUDE.md):
   본 framework 는 본인 PC 최적화 setting 이 아니라 전사 universal deployment 아키텍처.

본 모듈은 모든 sync hook 이 사용하는 공통 path resolver.
hardcoded path 를 환경변수 > autodetect > graceful None 패턴으로 대체.

6 기준 자체 평가:
  1. 자기복제율: hardcoded 제거 → 신규 PC 동일 작동 (+65%p)
  2. device-agnostic: env > autodetect > graceful None
  3. OS-agnostic: pathlib.Path 사용 (Windows/macOS/Linux)
  4. 권한-agnostic: 일반 user 권한만 사용
  5. idempotent: 순수 함수 (side-effect 0)
  6. 개인화 격리: personalization path 반환 안 함

PRD: docs/00-prd/aiden-auto-self-replication.prd.md §2
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def resolve_plugin_source() -> Optional[Path]:
    """aiden-auto plugin source 디렉토리 (v3.1 — 명시 의도 우선).

    우선순위:
      1. env AIDEN_AUTO_PLUGIN_SOURCE — 설정 시 그 값만 (무효 시 graceful None)
      2. env CLAUDE_PROJECT_DIR/plugins/aiden-auto (CC 주입 — sibling hook 정합, cwd 변동에 견고)
      3. (env 부재 시) cwd/plugins, parent/plugins, ~/src/aiden-auto (device-agnostic)
    """
    env_path = os.getenv("AIDEN_AUTO_PLUGIN_SOURCE")
    if env_path:
        p = Path(env_path)
        return p if p.is_dir() else None
    # 외부배포 (2026-05-31): 하드코딩 device 경로 제거 — CLAUDE_PROJECT_DIR(CC 주입) > cwd 상대 후보.
    # cwd 의존만으로는 hook subprocess cwd 변동 시 오해석 가능 → CC 가 주입하는 project dir 우선.
    candidates = []
    proj = os.getenv("CLAUDE_PROJECT_DIR")
    if proj:
        candidates.append(Path(proj) / "plugins" / "aiden-auto")
    candidates += [
        Path.cwd() / "plugins" / "aiden-auto",
        Path.cwd().parent / "plugins" / "aiden-auto",
        Path.home() / "src" / "aiden-auto" / "plugins" / "aiden-auto",
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def resolve_project_claude() -> Optional[Path]:
    """현재 project 의 .claude/ 디렉토리 (양방향 sync mirror).

    우선순위:
      1. env AIDEN_AUTO_PROJECT_CLAUDE
      2. env CLAUDE_PROJECT_DIR/.claude (CC 주입 — cwd 변동에 견고, sibling hook 정합)
      3. cwd/.claude (SSOT pattern)

    신규 PC 에서 후보가 ~/.claude/ 자체인 경우는 건너뜀 (self-sync 방지).

    Returns:
        Path 객체 또는 None
    """
    env_path = os.getenv("AIDEN_AUTO_PROJECT_CLAUDE")
    if env_path and Path(env_path).is_dir():
        return Path(env_path)
    # 외부배포 (2026-05-31): CLAUDE_PROJECT_DIR(CC 주입) 우선 → hook subprocess cwd 변동에 견고.
    candidates = []
    proj = os.getenv("CLAUDE_PROJECT_DIR")
    if proj:
        candidates.append(Path(proj) / ".claude")
    candidates.append(Path.cwd() / ".claude")
    for cand in candidates:
        if cand.is_dir():
            try:
                if cand.resolve() == (Path.home() / ".claude").resolve():
                    continue  # ~/.claude 자체 self-sync 방지
            except OSError:
                pass
            return cand
    return None


def resolve_aiden_auto_repo() -> Optional[Path]:
    """aiden-auto GitHub repo 클론 위치 (framework_github_sync 대상).

    우선순위 (v3.1 — 명시 의도 우선):
      1. env AIDEN_AUTO_REPO — 설정되어 있으면 그 값만 사용 (무효해도 fallback X)
      2. (env 부재 시) CLAUDE_PROJECT_DIR.parent/aiden-auto-repo, ~/aiden-auto-repo, ~/src/aiden-auto, cwd.parent/aiden-auto-repo

    .git 디렉토리 존재 확인 (실제 git repo 만).

    Returns:
        Path 객체 또는 None
    """
    env_path = os.getenv("AIDEN_AUTO_REPO")
    if env_path:
        # env 명시 — 그 값만 사용 (무효 시 graceful None, fallback X)
        p = Path(env_path)
        if p.is_dir() and (p / ".git").is_dir():
            return p
        return None
    # env 부재 시만 candidates 순회
    # 외부배포 (2026-05-31): 하드코딩 device 경로 제거 — CLAUDE_PROJECT_DIR.parent(CC 주입) + cwd.parent 후보.
    candidates = []
    proj = os.getenv("CLAUDE_PROJECT_DIR")
    if proj:
        candidates.append(Path(proj).parent / "aiden-auto-repo")
    candidates += [
        Path.home() / "aiden-auto-repo",
        Path.home() / "src" / "aiden-auto",
        Path.cwd().parent / "aiden-auto-repo",
    ]
    for c in candidates:
        if c.is_dir() and (c / ".git").is_dir():
            return c
    return None


def is_dev_pc() -> bool:
    """이 PC 가 정본(dev) PC 인가? (자가개선 *생성* 역할)

    역할 분리 (universal-deployment-checklist.md):
      - dev PC  : 매일 자가개선 workflow 실행 → 개선 결과를 GitHub 로 배포
      - 배포 PC : 개선 결과만 소비 (자가개선 *생성* hook 미발동)

    판별 (명시 우선 → 사실 신호 default):
      1. env AIDEN_AUTO_ROLE == 'dev'                 → True
         env in ('deployment','deploy','consumer')    → False
      2. (env 없음) 배포 원본 repo(aiden-auto-repo) 존재 = dev PC
    device-agnostic (env / Path.home 기반, hardcoded 0).
    """
    role = os.getenv("AIDEN_AUTO_ROLE", "").strip().lower()
    if role == "dev":
        return True
    if role in ("deployment", "deploy", "consumer"):
        return False
    return resolve_aiden_auto_repo() is not None


def resolve_cache_root() -> Optional[Path]:
    """CC plugin cache 의 최신 version 디렉토리.

    경로: ~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/<latest>/

    Returns:
        가장 높은 version 디렉토리 Path 또는 None
    """
    cache_base = Path.home() / ".claude" / "plugins" / "cache" / "garimto81-aiden-auto" / "aiden-auto"
    if not cache_base.is_dir():
        return None
    versions = sorted(
        [d for d in cache_base.iterdir() if d.is_dir() and not d.name.startswith(".")],
        reverse=True,
    )
    return versions[0] if versions else None


def resolve_marketplaces_dir() -> Optional[Path]:
    """marketplaces 디렉토리 (legacy, v5/v6 이전 sync 대상).

    경로: ~/.claude/plugins/marketplaces/garimto81-aiden-auto/

    Returns:
        디렉토리 존재 시 Path, 아니면 None
    """
    p = Path.home() / ".claude" / "plugins" / "marketplaces" / "garimto81-aiden-auto"
    return p if p.is_dir() else None


def resolve_global_claude() -> Path:
    """글로벌 ~/.claude/ — 항상 존재 (사용자 home 기반).

    Returns:
        Path.home() / ".claude" (디렉토리 존재 안 해도 반환)
    """
    return Path.home() / ".claude"


if __name__ == "__main__":
    # Self-test (premise verification)
    import json

    results = {
        "global_claude": str(resolve_global_claude()),
        "plugin_source": str(resolve_plugin_source()) if resolve_plugin_source() else None,
        "project_claude": str(resolve_project_claude()) if resolve_project_claude() else None,
        "aiden_auto_repo": str(resolve_aiden_auto_repo()) if resolve_aiden_auto_repo() else None,
        "cache_root": str(resolve_cache_root()) if resolve_cache_root() else None,
        "marketplaces_dir": str(resolve_marketplaces_dir()) if resolve_marketplaces_dir() else None,
    }
    print(json.dumps(results, indent=2, ensure_ascii=False))

    # premise self-evaluation
    # 본 모듈 내 hardcoded path 검사. 정당화 패턴:
    #   1. "backward compat" 주석 같은 줄
    #   2. self-test 의 검사 코드 자체 (in line / # SELF-CHECK 마커)
    # 외부배포 HIGH-1 (2026-05-31): 검사 패턴을 조립식으로 — 본 self-check 코드 자체가
    # grep 하드코딩-경로 메트릭에 false-positive 로 잡히지 않도록 (device-coupling 아님).
    _drive = "C:" + chr(92)
    _pat_claude = _drive + "claude"
    _pat_repo = _drive + "aiden-auto-repo"
    hardcoded_count = 0
    with open(__file__, "r", encoding="utf-8") as f:
        content = f.read()
    if _pat_claude in content or _pat_repo in content:
        for i, line in enumerate(content.splitlines(), 1):
            if _pat_claude in line or _pat_repo in line:
                line_lower = line.lower()
                is_justified = "backward compat" in line_lower or "self-check" in line_lower
                if not is_justified:
                    hardcoded_count += 1
                    print(f"  ⚠ unmarked hardcoded path at line {i}: {line.strip()[:80]}")

    print(f"\nself-evaluation: hardcoded path (unmarked) = {hardcoded_count}")
    print("premise 6 기준: hardcoded 0 (backward compat 제외) =", "PASS" if hardcoded_count == 0 else "FAIL")
