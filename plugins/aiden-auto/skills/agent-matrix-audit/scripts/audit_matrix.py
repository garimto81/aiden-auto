#!/usr/bin/env python3
"""enforcer.py MATRIX_NORMAL 무결성 감사 — 모든 agent의 실제 파일 위치 매핑.

목적:
- 매트릭스에 등록된 모든 agent 가 실제로 어디 있는지 확인
- phantom entry (매트릭스에만 존재, 파일 없음) 탐지
- 중복 정의 (여러 경로에 동일 이름) 탐지
- built-in agent (파일 없이 시스템 내장) 식별

출력: 표 + JSON. JSON 경로: .claude/state/agent-matrix-mapping.json

설계 원칙:
- read-only (enforcer.py 자체 수정 안 함, 권고만)
- 짧고 빠름 (5초 이내)
- 인간/AI 모두 읽기 좋은 출력
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

# 공유 helper import (stub-aware classification)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "_shared"))
try:
    from audit_helpers import (
        BENIGN_INTENTS,
        classify_duplicate_intent,
        is_in_shadow_marketplace,
        parse_frontmatter_simple,
        read_text_safe,
    )
    _HAS_HELPERS = True
except ImportError:
    _HAS_HELPERS = False
    # fallback BENIGN_INTENTS — helper와 반드시 동기화
    # A-8 (2026-05-18 audit-loop critic DI-1): plugin_multi_version_cache + external_plugin_internal_drift 추가
    BENIGN_INTENTS = frozenset({
        "shadow_marketplace", "byte_identical_mirror", "redirect_stub",
        "project_global_mirror", "plugin_namespaced",
        "priority_resolution_local_wins", "priority_resolution_global_wins",
        "localization_override",
        "plugin_multi_version_cache", "external_plugin_internal_drift",
    })

# Anthropic built-in agents (파일 없이 시스템 내장. 매트릭스에 있어도 정상)
BUILTIN_AGENTS = {"Explore", "Plan", "general-purpose"}

PROJECT_AGENTS_DIR = Path("C:/claude/.claude/agents")
GLOBAL_AGENTS_DIR = Path.home() / ".claude" / "agents"
# Rule 19 v2.0 정합화 (2026-05-18 audit-loop): marketplaces + cache 양쪽 스캔
# cache 가 실제 CC 로드 위치이므로 PHANTOM 오분류 방지 (FN 해소)
PLUGIN_MARKETPLACE_ROOT = Path.home() / ".claude" / "plugins" / "marketplaces"
PLUGIN_CACHE_ROOT = Path.home() / ".claude" / "plugins" / "cache"
PLUGIN_SCAN_ROOTS = [PLUGIN_MARKETPLACE_ROOT, PLUGIN_CACHE_ROOT]
ENFORCER_PATH = Path("C:/claude/.claude/hooks/agent_model_enforcer.py")
OUTPUT_PATH = Path("C:/claude/.claude/state/agent-matrix-mapping.json")


def load_matrix() -> dict[str, str]:
    """enforcer.py 의 MATRIX_NORMAL 을 안전하게 import 하여 dict 반환.

    enforcer.py 파싱/실행 실패 또는 MATRIX_NORMAL 미정의 시 빈 dict 반환.
    """
    try:
        spec = importlib.util.spec_from_file_location("enforcer", ENFORCER_PATH)
        if spec is None or spec.loader is None:
            return {}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return getattr(module, "MATRIX_NORMAL", {})
    except Exception as e:
        print(f"[WARN] load_matrix failed: {e}", file=sys.stderr)
        return {}


def find_agent(name: str) -> list[Path]:
    """agent 의 .md 파일을 4 경로에서 검색. 발견 순서 = 우선순위.

    plugin scan 은 marketplaces + cache 양쪽 (Rule 19 v2.0 정합).
    junction/symlink 중복은 resolve() set 으로 제거.
    """
    found: list[Path] = []
    # 1) project local (최우선)
    p = PROJECT_AGENTS_DIR / f"{name}.md"
    if p.is_file():
        found.append(p)
    # 2) global user
    g = GLOBAL_AGENTS_DIR / f"{name}.md"
    if g.is_file():
        found.append(g)
    # 3) plugin (marketplaces + cache, recursive) — agents 디렉토리 한정
    seen_resolved: set[Path] = set()
    for root in PLUGIN_SCAN_ROOTS:
        if not root.is_dir():
            continue
        for path in root.rglob(f"{name}.md"):
            if not (path.is_file() and "agents" in path.parts):
                continue
            # Windows junction / symlink 중복 제거
            try:
                resolved = path.resolve()
            except OSError:
                resolved = path
            if resolved in seen_resolved:
                continue
            seen_resolved.add(resolved)
            found.append(path)
    return found


def classify(name: str, paths: list[Path]) -> str:
    """결과 분류."""
    if name in BUILTIN_AGENTS:
        return "BUILT_IN" if not paths else "BUILT_IN_SHADOWED"
    if not paths:
        return "PHANTOM"
    if len(paths) > 1:
        return "DUPLICATE"
    p = paths[0]
    if p.is_relative_to(PROJECT_AGENTS_DIR):
        return "LOCAL"
    if p.is_relative_to(GLOBAL_AGENTS_DIR):
        return "GLOBAL"
    return "PLUGIN"


def audit() -> dict:
    matrix = load_matrix()
    results: list[dict] = []
    summary = {"LOCAL": 0, "GLOBAL": 0, "PLUGIN": 0, "BUILT_IN": 0,
              "BUILT_IN_SHADOWED": 0, "DUPLICATE": 0, "PHANTOM": 0}

    for name, model in matrix.items():
        paths = find_agent(name)
        status = classify(name, paths)
        summary[status] += 1
        record = {
            "name": name,
            "matrix_model": model,
            "status": status,
            "paths": [p.as_posix() for p in paths],
        }
        # DUPLICATE 인 경우 intent 분류 추가
        if status == "DUPLICATE" and _HAS_HELPERS:
            bodies: list[str] = []
            fms: list[dict] = []
            for p in paths:
                text = read_text_safe(p)
                fm, body = parse_frontmatter_simple(text)
                bodies.append(body)
                fms.append(fm)
            record["intent"] = classify_duplicate_intent(paths, bodies, fms)
        results.append(record)

    # intent 분포 (DUPLICATE 세분화)
    intent_summary: dict[str, int] = {}
    for r in results:
        if r["status"] == "DUPLICATE":
            intent = r.get("intent", "unclassified")
            intent_summary[intent] = intent_summary.get(intent, 0) + 1

    return {
        "ts": datetime.now().isoformat(),
        "matrix_total": len(matrix),
        "summary": summary,
        "intent_summary": intent_summary,
        "results": results,
    }


def print_report(report: dict) -> None:
    print(f"\n=== Matrix Audit Report ({report['ts']}) ===\n")
    print(f"Matrix entries: {report['matrix_total']}\n")

    # 분포
    print("Status distribution:")
    for status, count in report["summary"].items():
        if count > 0:
            print(f"  {status:20s}: {count:3d}")

    # intent 분포 (DUPLICATE 세분화) — 단일 BENIGN_INTENTS 사용
    intent_summary = report.get("intent_summary", {})
    if intent_summary:
        print("\nDUPLICATE intent breakdown:")
        for intent, count in sorted(intent_summary.items()):
            tag = "OK" if intent in BENIGN_INTENTS else "WARN"
            print(f"  [{tag:4s}] {intent:25s}: {count:3d}")

    # real issue: PHANTOM, BUILT_IN_SHADOWED 는 항상 issue
    # DUPLICATE 는 intent 가 benign 아닐 때만 issue
    issues = [
        r for r in report["results"]
        if r["status"] in {"PHANTOM", "BUILT_IN_SHADOWED"}
        or (r["status"] == "DUPLICATE" and r.get("intent") not in BENIGN_INTENTS)
    ]
    if issues:
        print(f"\nReal issues (action needed): {len(issues)}\n")
        for r in issues:
            intent_info = f" intent={r['intent']}" if r.get("intent") else ""
            print(f"  [{r['status']:18s}] {r['name']:30s}{intent_info} model={r['matrix_model']}")
            for p in r["paths"]:
                print(f"      → {p}")
    else:
        print("\nNo real issues found. All duplicates classified as intended.\n")

    # 정상 케이스 요약 (이름만)
    plugin_agents = [r["name"] for r in report["results"] if r["status"] == "PLUGIN"]
    if plugin_agents:
        print(f"\nPlugin-located agents ({len(plugin_agents)}):")
        for name in sorted(plugin_agents):
            print(f"  - {name}")


def save(report: dict) -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nSaved to: {OUTPUT_PATH}")


def main() -> int:
    report = audit()
    print_report(report)
    save(report)
    phantom_count = report["summary"]["PHANTOM"]
    real_dup = report.get("intent_summary", {}).get("real_duplicate", 0)
    real_dup += report.get("intent_summary", {}).get("unclassified", 0)
    return 1 if (phantom_count > 0 or real_dup > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
