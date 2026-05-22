#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""measure-replication.py — Universal Deployment Premise 정량 메트릭.

⭐ Premise (글로벌 CLAUDE.md HIGHEST PRIORITY):
   본 framework 는 전사 universal deployment 아키텍처. 자기복제율 ≥95% 의무.

본 도구는 CANONICAL 자산 (~/.claude/ 정본) 대비 TARGET PC 의
universal 자산 보유율을 측정한다.

self_replication_rate =
  (target 의 universal 자산 개수) / (canonical 의 universal 자산 개수) × 100%

목표: ≥95% (premise #1 통과 기준)

PRD: docs/00-prd/aiden-auto-self-replication.prd.md §7
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set

CANONICAL = Path.home() / ".claude"

# Universal 자산 디렉토리 (모든 PC 동일해야 함)
UNIVERSAL_DIRS = [
    "agents", "skills", "hooks", "commands", "rules",
    "references", "hud", "lib", "scripts",
]

# 자산 카운트 제외 (개인화 / 임시 파일)
EXCLUDE_PARTS = {
    "__pycache__", ".git", ".cache", "node_modules",
    "state", "projects", "oauth_tokens", "logs", "tmp",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo", ".log", ".swp", ".swo", ".bak", ".tmp"}
EXCLUDE_NAMES = {
    "settings.json", "settings.local.json", ".credentials.json", ".env",
}


def should_count(p: Path, rel: Path) -> bool:
    """파일을 universal 자산으로 카운트할지."""
    if not p.is_file():
        return False
    if p.name.startswith("."):
        return False
    if p.name in EXCLUDE_NAMES:
        return False
    if p.suffix in EXCLUDE_SUFFIXES:
        return False
    if any(part in EXCLUDE_PARTS for part in rel.parts):
        return False
    return True


def count_universal_assets(root: Path, verbose: bool = False) -> Dict[str, int]:
    """root/{universal_dir}/ 의 자산 카운트.

    Returns:
        {dir_name: count, ...}
    """
    counts: Dict[str, int] = {}
    if not root.is_dir():
        return {d: 0 for d in UNIVERSAL_DIRS}
    for d in UNIVERSAL_DIRS:
        subdir = root / d
        c = 0
        if subdir.is_dir():
            for f in subdir.rglob("*"):
                rel = f.relative_to(subdir)
                if should_count(f, rel):
                    c += 1
        counts[d] = c
        if verbose:
            print(f"  {d}: {c}")
    return counts


def find_missing_files(canonical_root: Path, target_root: Path) -> List[str]:
    """canonical 에 있고 target 에 없는 universal 파일 목록."""
    missing: List[str] = []
    if not canonical_root.is_dir() or not target_root.is_dir():
        return missing
    for d in UNIVERSAL_DIRS:
        c_sub = canonical_root / d
        t_sub = target_root / d
        if not c_sub.is_dir():
            continue
        for f in c_sub.rglob("*"):
            rel = f.relative_to(c_sub)
            if not should_count(f, rel):
                continue
            t_f = t_sub / rel
            if not t_f.exists():
                missing.append(f"{d}/{rel.as_posix()}")
    return missing


def measure(canonical_root: Path, target_root: Path, verbose: bool = False) -> Dict:
    """자기복제율 측정."""
    canonical_counts = count_universal_assets(canonical_root, verbose=False)
    target_counts = count_universal_assets(target_root, verbose=False)

    total_canonical = sum(canonical_counts.values())
    total_target = sum(target_counts.values())
    rate = (total_target / total_canonical * 100) if total_canonical > 0 else 0.0

    result = {
        "canonical_root": str(canonical_root),
        "target_root": str(target_root),
        "canonical_total": total_canonical,
        "target_total": total_target,
        "self_replication_rate": round(rate, 1),
        "premise_pass": rate >= 95.0,
        "by_directory": {
            d: {"canonical": canonical_counts.get(d, 0), "target": target_counts.get(d, 0)}
            for d in UNIVERSAL_DIRS
        },
    }

    if verbose:
        result["missing_files"] = find_missing_files(canonical_root, target_root)[:50]  # 상위 50개만

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Universal Deployment 자기복제율 측정 (premise #1)",
    )
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Target PC ~/.claude/ root (또는 .claude/ 부모 디렉토리)",
    )
    parser.add_argument(
        "--canonical", "-c",
        default=str(CANONICAL),
        help="Canonical (정본) ~/.claude/ 경로 (default: %(default)s)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    canonical_root = Path(args.canonical)
    target_root = Path(args.target)
    # target 이 .claude/ 부모인 경우 자동 보정
    if not (target_root / "skills").exists() and (target_root / ".claude" / "skills").exists():
        target_root = target_root / ".claude"

    result = measure(canonical_root, target_root, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"=== Self-Replication Rate ===")
        print(f"  canonical: {result['canonical_total']} assets ({result['canonical_root']})")
        print(f"  target:    {result['target_total']} assets ({result['target_root']})")
        print(f"  rate:      {result['self_replication_rate']}%")
        print(f"  premise pass (≥95%): {'✅ PASS' if result['premise_pass'] else '❌ FAIL'}")
        if args.verbose:
            print(f"\n  by directory:")
            for d, c in result["by_directory"].items():
                print(f"    {d:<14}  canonical={c['canonical']:>4}  target={c['target']:>4}")
            if "missing_files" in result and result["missing_files"]:
                print(f"\n  missing files (top {len(result['missing_files'])}):")
                for m in result["missing_files"][:20]:
                    print(f"    - {m}")

    return 0 if result["premise_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
