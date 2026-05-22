#!/usr/bin/env python3
"""Plugin SSOT 무결성 audit + 자율 sync.

목적:
- 두 plugin mirror (project source + marketplaces mirror) 의 drift 자동 감지
- 비파괴 자율 정정: marketplaces → project source mirror

설계 원칙 (rule 19 plugin-ssot-policy.md v2.0 준수):
- ~/.claude/ 가 SSOT (Global 정본)
- 실제 CC 로드 위치 = ~/.claude/plugins/cache/garimto81-aiden-auto/aiden-auto/28.3.0/
- marketplaces/ 폴더 = marketplace 메타데이터 저장소 (참조용)
- 본 script 의 CACHE_MIRROR 변수명은 historical (Cycle 1-22). 실제로는 marketplaces 비교.
  cache 비교 추가는 별도 cycle (Cycle 23 critic A-28 docstring 정합화).
- runtime artifact (__pycache__, *.pyc) 자동 제외

A-28 (Cycle 23 critic HIGH-1): docstring rule 19 v2.0 정합화. 코드 동작 그대로 유지
(변수명 rename 은 외부 호출자 영향 가능, 별도 cycle 권고).
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_MIRROR = Path("C:/claude/plugins/aiden-auto")
# CACHE_MIRROR: historical 변수명. 실제로는 marketplaces mirror 비교 (rule 19 v2.0 정합).
# cache (CC 실제 로드) 비교는 별도 cycle 에서 추가 권고.
CACHE_MIRROR = Path.home() / ".claude" / "plugins" / "marketplaces" / "garimto81-aiden-auto" / "plugins" / "aiden-auto"
OUTPUT_PATH = Path("C:/claude/.claude/state/plugin-ssot-mapping.json")

# Sync 제외 패턴 (runtime artifact)
EXCLUDE_PATTERNS = ["__pycache__", ".pyc"]


def is_excluded(path: Path) -> bool:
    return any(p in path.parts or path.name.endswith(p) for p in EXCLUDE_PATTERNS)


def collect(root: Path) -> dict[str, str]:
    """root 아래 모든 파일의 (relative_path, sha256[:12]) 매핑."""
    if not root.is_dir():
        return {}
    result = {}
    for p in root.rglob("*"):
        if p.is_file() and not is_excluded(p):
            rel = p.relative_to(root).as_posix()
            result[rel] = hashlib.sha256(p.read_bytes()).hexdigest()[:12]
    return result


def audit() -> dict:
    proj = collect(PROJECT_MIRROR)
    cache = collect(CACHE_MIRROR)

    proj_keys = set(proj.keys())
    cache_keys = set(cache.keys())
    common = proj_keys & cache_keys
    proj_only = proj_keys - cache_keys
    cache_only = cache_keys - proj_keys

    drift_paths = [k for k in common if proj[k] != cache[k]]
    same_count = len(common) - len(drift_paths)

    # 보고용 sliced view + sync용 전체 view 분리 (Cycle 9 HIGH-5: silent data loss 수정)
    sorted_drift = sorted(drift_paths)
    sorted_proj_only = sorted(proj_only)
    sorted_cache_only = sorted(cache_only)

    return {
        "ts": datetime.now().isoformat(),
        "project_mirror": str(PROJECT_MIRROR),
        "cache_mirror": str(CACHE_MIRROR),
        "summary": {
            "proj_total": len(proj),
            "cache_total": len(cache),
            "same": same_count,
            "drift": len(drift_paths),
            "proj_only": len(proj_only),
            "cache_only": len(cache_only),
            "is_perfect_mirror": proj_keys == cache_keys and not drift_paths,
        },
        "drift_paths": sorted_drift[:50],            # 보고용 (상위 50)
        "proj_only_paths": sorted_proj_only[:50],
        "cache_only_paths": sorted_cache_only[:50],
        # sync 용 전체 리스트 (truncate 안 함)
        "_all_drift_paths": sorted_drift,
        "_all_proj_only_paths": sorted_proj_only,
        "_all_cache_only_paths": sorted_cache_only,
    }


def sync_cache_to_project(report: dict, dry_run: bool = True) -> dict:
    """cache → project source mirror (drift, proj_only, cache_only 모두 해결).

    원칙: cache 가 정본 (Claude Code 가 로드). project source 가 cache 와 동일하게.
    proj_only 파일은 제거. cache_only 파일은 추가. drift 는 cache 값으로 덮어쓰기.
    """
    actions = []

    # Cycle 9 HIGH-5: report에서 sliced 가 아닌 _all_* 전체 리스트 사용 (silent data loss 방지)
    drift_list = report.get("_all_drift_paths", report.get("drift_paths", []))
    cache_only_list = report.get("_all_cache_only_paths", report.get("cache_only_paths", []))
    proj_only_list = report.get("_all_proj_only_paths", report.get("proj_only_paths", []))

    # drift: cache → project (전체 sync)
    for rel in drift_list:
        src = CACHE_MIRROR / rel
        dst = PROJECT_MIRROR / rel
        actions.append({"op": "overwrite", "path": rel, "reason": "drift"})
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # cache_only: 추가
    for rel in cache_only_list:
        src = CACHE_MIRROR / rel
        dst = PROJECT_MIRROR / rel
        actions.append({"op": "add", "path": rel, "reason": "cache_only"})
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # proj_only: 제거 (cache 에 없으므로)
    for rel in proj_only_list:
        dst = PROJECT_MIRROR / rel
        actions.append({"op": "remove", "path": rel, "reason": "proj_only"})
        if not dry_run:
            if dst.is_file():
                dst.unlink()

    # Cycle 11 MEDIUM: 로그 가시성 — truncation 명시 마커
    return {
        "dry_run": dry_run,
        "action_count": len(actions),
        "actions": actions[:20],
        "actions_truncated": len(actions) > 20,
        "actions_omitted": max(0, len(actions) - 20),
    }


def print_report(report: dict) -> None:
    s = report["summary"]
    print(f"\n=== Plugin SSOT Audit Report ({report['ts']}) ===\n")
    print(f"  Project mirror: {report['project_mirror']}")
    print(f"  Cache mirror:   {report['cache_mirror']}")
    print()
    print(f"  proj total: {s['proj_total']}")
    print(f"  cache total: {s['cache_total']}")
    print(f"  same content: {s['same']}")
    print(f"  drift: {s['drift']}")
    print(f"  proj_only: {s['proj_only']}")
    print(f"  cache_only: {s['cache_only']}")
    print()

    if s["is_perfect_mirror"]:
        print("  STATUS: ✓ PERFECT MIRROR (정책 준수)")
    else:
        print("  STATUS: ⚠ DRIFT (sync 필요)")
        if report["drift_paths"]:
            print(f"\n  drift 샘플 (상위 5):")
            for p in report["drift_paths"][:5]:
                print(f"    - {p}")
        if report["proj_only_paths"]:
            print(f"\n  proj_only 샘플 (상위 5):")
            for p in report["proj_only_paths"][:5]:
                print(f"    - {p}")
        if report["cache_only_paths"]:
            print(f"\n  cache_only 샘플 (상위 5):")
            for p in report["cache_only_paths"][:5]:
                print(f"    - {p}")


def main() -> int:
    report = audit()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print_report(report)
    print(f"\nSaved to: {OUTPUT_PATH}")

    # 옵션 처리
    auto_sync = "--sync" in sys.argv
    dry_run = "--dry-run" in sys.argv or not auto_sync

    if not report["summary"]["is_perfect_mirror"]:
        if auto_sync:
            print("\n--- 자율 sync 실행 (cache → project source) ---")
            result = sync_cache_to_project(report, dry_run=False)
            print(f"  {result['action_count']} actions applied")
            if result.get('actions_truncated'):
                print(f"  ({result['actions_omitted']} more actions logged, see audit JSON)")
        elif dry_run:
            print("\n--- dry-run: --sync 옵션으로 실제 적용 ---")
            result = sync_cache_to_project(report, dry_run=True)
            print(f"  {result['action_count']} actions would be applied")
            if result.get('actions_truncated'):
                print(f"  ({result['actions_omitted']} more actions logged, see audit JSON)")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
