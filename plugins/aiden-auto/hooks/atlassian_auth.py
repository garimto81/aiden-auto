#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Atlassian MCP Auth Executor (on-demand)
=======================================

⚠ v1.1 (2026-05-22): SessionStart 자동 발동 폐기. 사용자 피드백 정정:
   "Atlassian 안 쓰는 프로젝트에서 매 SessionStart 발동은 over-engineered."

발동 시점:
  - /auto Phase -1.5 Part E 자율 판단에서 "Atlassian 사용 감지" 시에만
  - 또는 사용자가 명시 호출 시 (e.g., `python atlassian_auth.py`)

호출 위치: Claude(Lead) 가 Phase -1.5 휴리스틱 충족 시 subprocess로 직접 호출.
SessionStart hook registry 에서는 비활성 (_disabled/ 격리됨).

Pairs with agent spec: ~/.claude/agents/meta/atlassian-auth-executor.md
PRD: C:/claude/docs/00-prd/aiden-auto-atlassian-mcp-auth-automation.prd.md

Spec contract:
  - READ: state/atlassian-auth-failures-{date}.json,
          state/atlassian-auth-last-success.json,
          state/atlassian-auth-prompt-history.json,
          state/circuit-breaker.json
  - WRITE: state/atlassian-auth-decisions-{date}.json (append),
           state/atlassian-auth-advisor-pending.flag (only on escalate)

Exit codes:
  0 = success (silent or verdict-emitted)
  always 0 — failures are logged but never block caller

Safe path target: ≤100ms (mostly small JSON reads + 3 comparisons).
"""
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

HOME = Path(os.path.expanduser("~"))
STATE_DIR = HOME / ".claude" / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

TODAY = date.today().isoformat()
FAILURES_FILE = STATE_DIR / f"atlassian-auth-failures-{TODAY}.json"
LAST_SUCCESS_FILE = STATE_DIR / "atlassian-auth-last-success.json"
PROMPT_HISTORY_FILE = STATE_DIR / "atlassian-auth-prompt-history.json"
DECISIONS_FILE = STATE_DIR / f"atlassian-auth-decisions-{TODAY}.json"
ADVISOR_FLAG = STATE_DIR / "atlassian-auth-advisor-pending.flag"
BREAKER_FILE = STATE_DIR / "circuit-breaker.json"


def load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    return default


def append_decision(record: dict) -> None:
    log = load_json(DECISIONS_FILE, {"entries": []})
    log.setdefault("entries", []).append(record)
    try:
        DECISIONS_FILE.write_text(json.dumps(log, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass  # log failure must never block SessionStart


def count_recent_failures(failures: dict, hours: int) -> int:
    cutoff_ms = int(time.time() * 1000) - hours * 3600 * 1000
    entries = failures.get("entries", []) if isinstance(failures, dict) else []
    return sum(1 for e in entries if isinstance(e, dict) and e.get("ts", 0) >= cutoff_ms)


def check_circuit_breaker() -> bool:
    """Return True if breaker tripped (atlassian_auth count >= 5)."""
    breaker = load_json(BREAKER_FILE, {})
    entry = breaker.get("atlassian_auth", {})
    if isinstance(entry, dict):
        return entry.get("count", 0) >= entry.get("limit", 5)
    return False


def evaluate() -> dict:
    """Run the 3-question evaluation and produce a verdict."""
    now_ms = int(time.time() * 1000)
    failures = load_json(FAILURES_FILE, {"entries": []})
    last_success = load_json(LAST_SUCCESS_FILE, {"ts": 0})
    prompt_history = load_json(PROMPT_HISTORY_FILE, {"last": 0})

    signals = {
        "auth_failure_burst": count_recent_failures(failures, hours=24) >= 3,
        "stale_token": (now_ms - last_success.get("ts", 0)) > 7 * 24 * 3600 * 1000,
        "user_unresponded": (
            prompt_history.get("last", 0) > 0
            and (now_ms - prompt_history.get("last", 0)) > 4 * 3600 * 1000
            and last_success.get("ts", 0) < prompt_history.get("last", 0)
        ),
    }

    # First-run guard: no prior success and no failures = brand new install. PASS.
    is_first_run = last_success.get("ts", 0) == 0 and not failures.get("entries")

    if check_circuit_breaker():
        return {
            "verdict": "BLOCKED_BY_BREAKER",
            "tier": "executor",
            "rationale": "circuit breaker tripped — manual reset required",
            "signals": signals,
            "timestamp": now_ms,
        }

    if is_first_run or not any(signals.values()):
        return {
            "verdict": "PASS_THROUGH",
            "tier": "executor",
            "rationale": "no signals" if not is_first_run else "first-run, no prior state",
            "signals": signals,
            "timestamp": now_ms,
        }

    # stale_token single signal → AUTO_REFRESH (cost-saving short-circuit)
    if signals["stale_token"] and not signals["auth_failure_burst"] and not signals["user_unresponded"]:
        return {
            "verdict": "AUTO_REFRESH",
            "tier": "executor",
            "confidence": "HIGH",
            "rationale": "stale_token only — plugin MCP self-refresh attempt delegated",
            "signals": signals,
            "timestamp": now_ms,
        }

    # Ambiguous/risky → escalate to advisor
    return {
        "verdict": "ESCALATE",
        "tier": "executor",
        "rationale": "mixed signals — advisor decision required",
        "signals": signals,
        "failures_count": len(failures.get("entries", [])),
        "last_success_ts": last_success.get("ts", 0),
        "timestamp": now_ms,
    }


def main() -> int:
    try:
        result = evaluate()
        verdict = result["verdict"]

        if verdict == "ESCALATE":
            try:
                ADVISOR_FLAG.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass

        append_decision(result)
        # SessionStart hooks must produce no visible stdout for silent pass-through
        return 0
    except Exception as exc:
        # Defensive: never block SessionStart on hook failure
        append_decision({
            "verdict": "HOOK_ERROR",
            "tier": "executor",
            "rationale": f"unexpected error: {type(exc).__name__}",
            "timestamp": int(time.time() * 1000),
        })
        return 0


if __name__ == "__main__":
    sys.exit(main())
