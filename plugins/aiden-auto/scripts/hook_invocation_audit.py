#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hook_invocation_audit.py — 진짜 검증 (B3).

~/.claude/logs/hook-events.db SQLite WAL 분석 + 등록 hook 의 실제 발동 흔적 검증.

PRD: aiden-auto-self-replication.prd.md v3 (Reality Validation B3)
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

GLOBAL_CLAUDE = Path.home() / ".claude"
LOG_DB = GLOBAL_CLAUDE / "logs" / "hook-events.db"
REGISTRY_DIR = GLOBAL_CLAUDE / "hooks" / "registry"


# 기대 hook (registry 에 등록된 + 발동 흔적 있어야)
EXPECTED_HOOKS = {
    "PostToolUse": [
        "bidirectional_sync",
        "machine_framework_watcher",
        "quantification_tracker",
    ],
    "SessionStart": [
        "bootstrap",
        "harness_cycle_runner",
        "usage-refresh",
        "atlassian-auth",  # _disabled/ 격리됨 — registry 부재 의도
    ],
    "SessionEnd": [
        "framework_github_sync",
        "session_cleanup",
    ],
    "PreToolUse": [
        "framework_edit_guard",
        "pretool_md_check",
    ],
}


def get_registered_hooks() -> dict:
    """registry/{event}/*.json 의 등록된 hook 목록."""
    registered = {}
    if not REGISTRY_DIR.is_dir():
        return registered
    for event_dir in REGISTRY_DIR.iterdir():
        if not event_dir.is_dir() or event_dir.name.startswith("_") or event_dir.name.startswith("."):
            continue
        event = event_dir.name
        hooks = []
        for f in event_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                hooks.append(data.get("name", f.stem))
            except (json.JSONDecodeError, OSError):
                pass
        registered[event] = hooks
    return registered


def get_invocation_counts(hours: int = 168) -> dict:
    """logs/hook-events.db 에서 최근 N 시간 hook 발동 수.

    Returns:
        {hook_name: count, ...}
    """
    if not LOG_DB.exists():
        return {}
    try:
        conn = sqlite3.connect(str(LOG_DB), timeout=2.0)
        cursor = conn.cursor()
        cutoff = time.time() - hours * 3600
        cursor.execute("""
            SELECT hook_name, COUNT(*) AS cnt
            FROM hook_events
            WHERE ts >= datetime(?, 'unixepoch')
            GROUP BY hook_name
        """, (cutoff,))
        counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return counts
    except sqlite3.Error as e:
        return {"_error": str(e)}


def get_recent_errors(hours: int = 168) -> list:
    """최근 N 시간 hook 에러 (exit_code != 0)."""
    if not LOG_DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(LOG_DB), timeout=2.0)
        cursor = conn.cursor()
        cutoff = time.time() - hours * 3600
        cursor.execute("""
            SELECT ts, hook_name, exit_code, error
            FROM hook_events
            WHERE ts >= datetime(?, 'unixepoch') AND exit_code != 0
            ORDER BY ts DESC
            LIMIT 20
        """, (cutoff,))
        errors = [{"ts": r[0], "hook_name": r[1], "exit_code": r[2], "error": r[3]} for r in cursor.fetchall()]
        conn.close()
        return errors
    except sqlite3.Error:
        return []


def analyze_hook_health() -> dict:
    """각 등록 hook 의 health 분석.

    Health states:
        ACTIVE — 최근 발동 흔적 (≥1 호출)
        REGISTERED_BUT_DORMANT — 등록되었으나 발동 0 (event 미발생 가능)
        UNKNOWN — registry 자체 부재
    """
    registered = get_registered_hooks()
    counts = get_invocation_counts(hours=168)  # 1주

    analysis = {}
    for event, hooks in registered.items():
        for hook_name in hooks:
            count = counts.get(hook_name, 0)
            state = "ACTIVE" if count > 0 else "REGISTERED_BUT_DORMANT"
            analysis[hook_name] = {
                "event": event,
                "state": state,
                "invocations_7d": count,
            }
    return analysis


def compute_hook_invocation_score(analysis: dict) -> dict:
    """B3 통합 점수 (0-10) v2 — 의도된 차단 vs 진짜 에러 구분.

    공식:
      active_ratio = ACTIVE hooks / total registered hooks
      score = active_ratio × 10
      - 진짜 에러 감점 (각 -0.2점, floor=0)
      - circuit_breaker / framework_edit_guard 의 의도된 차단은 error 카운트 제외
    """
    if not analysis:
        return {"score": 0.0, "basis": "no hooks analyzed", "active": 0, "total": 0}

    total = len(analysis)
    active = sum(1 for h in analysis.values() if h["state"] == "ACTIVE")
    base_score = (active / total * 10) if total > 0 else 0

    # 의도된 차단 hook (exit≠0 이 정책 위반 차단 의미) — error 카운트 제외
    INTENTIONAL_BLOCK_HOOKS = {"circuit_breaker", "framework_edit_guard"}

    all_errors = get_recent_errors(hours=168)
    real_errors = [e for e in all_errors if e["hook_name"] not in INTENTIONAL_BLOCK_HOOKS]

    # 진짜 에러만 페널티 (각 -0.2점)
    error_penalty = min(len(real_errors) * 0.2, base_score)
    final_score = max(0, base_score - error_penalty)

    return {
        "score": round(final_score, 2),
        "active": active,
        "total": total,
        "active_ratio": round(active / total * 100, 1) if total > 0 else 0,
        "all_errors_7d": len(all_errors),
        "intentional_blocks_7d": len(all_errors) - len(real_errors),
        "real_errors_7d": len(real_errors),
        "error_penalty": round(error_penalty, 2),
        "basis": f"{active}/{total} hooks ACTIVE, {len(real_errors)} real errors ({len(all_errors) - len(real_errors)} intentional blocks excluded)",
    }


def main():
    parser = argparse.ArgumentParser(description="진짜 검증 도구 (B3) — hook 실제 발동 분석")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--score-only", action="store_true")
    parser.add_argument("--hours", type=int, default=168, help="분석 기간 (시간, default 7일)")
    args = parser.parse_args()

    if not LOG_DB.exists():
        result = {"error": "logs/hook-events.db 부재 — dispatcher 미가동", "score": 0.0}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1

    analysis = analyze_hook_health()
    score = compute_hook_invocation_score(analysis)
    recent_errors = get_recent_errors(hours=args.hours)[:10]

    result = {
        "score": score,
        "hook_analysis": analysis,
        "recent_errors_sample": recent_errors,
    }

    if args.score_only:
        print(json.dumps(score, indent=2, ensure_ascii=False))
    elif args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    else:
        print(f"=== Hook Invocation Audit (Reality, B3) ===\n")
        print(f"  Score: {score['score']}/10")
        print(f"  Basis: {score['basis']}\n")
        print(f"  Hook 상태 ({len(analysis)} 개):")
        for name, h in sorted(analysis.items()):
            mark = "✅" if h["state"] == "ACTIVE" else "⚠"
            print(f"    {mark} {h['event']:>15}/{name:<30} — {h['state']:<25} ({h['invocations_7d']:>4} invocations)")
        if recent_errors:
            print(f"\n  최근 에러 ({len(recent_errors)}):")
            for e in recent_errors[:5]:
                print(f"    {e['ts']}  {e['hook_name']}  exit={e['exit_code']}")

    return 0 if score["score"] >= 5.0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
