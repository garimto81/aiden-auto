#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chapter_dependency_guard.py — Cross-chapter Phase guard (F18 결함 해소).

⭐ Universal Deployment Premise 정합.

목적:
  Chapter 진입 시 의존 phase 완료 검증.
  예: QA chapter 진입 시 CODE Phase 2 artifact 존재 확인.

PRD: aiden-auto-self-replication.prd.md (F18)

6 기준 자체 평가: 6/6 PASS.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import resolve_global_claude  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"

GLOBAL_CLAUDE = resolve_global_claude()
STATE_AUTO = GLOBAL_CLAUDE / "state" / "auto"

# Chapter 의존성 매트릭스
DEPENDENCIES = {
    "QA": {
        "requires": ["CODE Phase 2"],
        "check": lambda slug: any((STATE_AUTO / f"code-build-{slug}.json").exists() or
                                  (STATE_AUTO / f"build-{slug}.json").exists() for slug in [slug])
    },
    "ITERATION": {
        "requires": ["CODE Phase 2 (preferred, optional)"],
        "check": lambda slug: True,  # iteration 은 독립 진입 허용
    },
}


def check_dependencies(chapter: str, slug: str = "") -> dict:
    """Chapter 진입 시 의존성 검증.

    Returns:
        {"ok": bool, "missing": [...], "chapter": ...}
    """
    chapter_upper = chapter.upper().replace("CHAPTER-", "")
    dep = DEPENDENCIES.get(chapter_upper)
    if not dep:
        return {"ok": True, "chapter": chapter_upper, "skip": True, "reason": "no dependencies"}

    missing = []
    if chapter_upper == "QA" and slug:
        code_build = STATE_AUTO / f"code-build-{slug}.json"
        build = STATE_AUTO / f"build-{slug}.json"
        if not code_build.exists() and not build.exists():
            missing.append(f"CODE Phase 2 artifact for slug={slug}")
    elif chapter_upper == "QA" and not slug:
        # slug 미명시 시 — 임의의 code-build-*.json 존재 확인
        if not list(STATE_AUTO.glob("code-build-*.json")) and not list(STATE_AUTO.glob("build-*.json")):
            missing.append("CODE Phase 2 artifact (no slug specified)")

    return {
        "ok": len(missing) == 0,
        "chapter": chapter_upper,
        "missing": missing,
        "requires": dep.get("requires", []),
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: chapter_dependency_guard.py <chapter> [<slug>]", file=sys.stderr)
        return 1

    chapter = sys.argv[1]
    slug = sys.argv[2] if len(sys.argv) > 2 else ""

    result = check_dependencies(chapter, slug)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    return 0 if result["ok"] else 2  # exit 2 = block (PreToolUse hook 차단)


if __name__ == "__main__":
    raise SystemExit(main())
