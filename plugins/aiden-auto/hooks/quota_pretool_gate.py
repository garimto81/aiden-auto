#!/usr/bin/env python
"""quota_pretool_gate.py — PreToolUse(Task) hook for v28.2 quota advisor pipeline.

Flow:
  PreToolUse(Task) → quota-executor (3Q) → if escalate → quota-advisor (5Q weighted)
                                          → apply verdict (PROCEED / DOWNGRADE_ECO / DEFER / BLOCK)

Non-blocking design: executor 100ms target, advisor 1-2s budget.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    hooks/ 폴더 기준: parent = hooks/, parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"

try:
    sys.path.insert(0, str(PLUGIN_ROOT))
    from lib.quota.usage_reader import read_usage_cache
except ImportError:
    read_usage_cache = None
CIRCUIT_BREAKER_FILE = STATE_DIR / "circuit-breaker.json"
ADVISOR_PENDING_FLAG = STATE_DIR / "quota-advisor-pending.flag"
DECISIONS_FILE_TEMPLATE = "quota-decisions-{date}.json"


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default if default is not None else {}


def _atomic_write(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _append_decision(decision: dict) -> None:
    file = STATE_DIR / DECISIONS_FILE_TEMPLATE.format(date=_today())
    existing = _read_json(file, default=[])
    if not isinstance(existing, list):
        existing = []
    existing.append(decision)
    _atomic_write(file, existing)


def _executor_3q(snap, hook_input: dict) -> dict:
    """3-question gate. Returns verdict dict."""
    five_h = snap.five_h_pct if snap else 0
    weekly = snap.weekly_pct if snap else 0
    requested_model = hook_input.get("model_class", "sonnet")
    cb = _read_json(CIRCUIT_BREAKER_FILE)
    active_mode = cb.get("active_eco_mode", "default")
    pending_spawns = int(hook_input.get("pending_spawns", 0))

    q1 = (five_h >= 70) or (weekly >= 60)
    q2 = (requested_model == "opus") and (active_mode == "default")
    q3 = pending_spawns >= 3

    if not q1 and not q2 and not q3:
        verdict = "PROCEED"
    elif q1 and (70 <= five_h < 85) and not q2 and not q3:
        verdict = "DOWNGRADE_ECO"
    else:
        verdict = "ESCALATE"

    # Circuit breaker forced escalate
    qd_count = int(cb.get("quota_downgrade", 0))
    if qd_count >= 5 and verdict == "DOWNGRADE_ECO":
        verdict = "ESCALATE"

    return {
        "schema_version": "1.0",
        "tier": "executor",
        "verdict": verdict,
        "signals": {"q1_quota_pressure": q1, "q2_opus_default": q2, "q3_pending_spawns": q3},
        "snapshot": {
            "five_h_pct": five_h,
            "weekly_pct": weekly,
            "quota_band": snap.quota_band() if snap else "NA",
        },
        "ts": datetime.now(timezone.utc).isoformat(),
    }


def _spawn_advisor_pending(executor_result: dict, hook_input: dict) -> None:
    """Writes pending flag for quota-advisor agent to pick up."""
    flag_payload = {
        "schema_version": "1.0",
        "session_id": hook_input.get("session_id", "unknown"),
        "signals": executor_result["signals"],
        "snapshot": executor_result["snapshot"],
        "hook_input": hook_input,
        "ts": executor_result["ts"],
    }
    _atomic_write(ADVISOR_PENDING_FLAG, flag_payload)


def _apply_verdict(verdict: str) -> int:
    """Returns exit code (0=allow, 2=block)."""
    if verdict == "BLOCK":
        sys.stderr.write(
            "[aiden-auto quota-advisor] BLOCK: weekly quota critical. "
            "Use !override to bypass.\n"
        )
        return 2
    if verdict == "DEFER":
        sys.stderr.write(
            "[aiden-auto quota-advisor] DEFER: quota high. Consider waiting for reset.\n"
        )
        return 0  # advisory only
    if verdict == "DOWNGRADE_ECO":
        cb = _read_json(CIRCUIT_BREAKER_FILE)
        cur = cb.get("active_eco_mode", "default")
        next_mode = {"default": "eco", "eco": "eco-2", "eco-2": "eco-3", "eco-3": "eco-3"}.get(cur, "eco")
        cb["active_eco_mode"] = next_mode
        cb["quota_downgrade"] = int(cb.get("quota_downgrade", 0)) + 1
        _atomic_write(CIRCUIT_BREAKER_FILE, cb)
        sys.stderr.write(f"[aiden-auto quota-advisor] DOWNGRADE_ECO: {cur} → {next_mode}\n")
        return 0
    return 0  # PROCEED


def main() -> int:
    # Read hook input (Claude Code PreToolUse contract: JSON on stdin)
    try:
        hook_input = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        hook_input = {}

    # User override
    user_msg = hook_input.get("user_message", "")
    if "!override" in user_msg:
        return 0
    if "!eco-only" in user_msg:
        # skip advisor, allow executor DOWNGRADE only
        snap = read_usage_cache() if read_usage_cache else None
        result = _executor_3q(snap, hook_input)
        if result["verdict"] == "ESCALATE":
            result["verdict"] = "DOWNGRADE_ECO"  # forced safe
        _append_decision(result)
        return _apply_verdict(result["verdict"])

    snap = read_usage_cache() if read_usage_cache else None
    exec_result = _executor_3q(snap, hook_input)
    _append_decision(exec_result)

    if exec_result["verdict"] != "ESCALATE":
        return _apply_verdict(exec_result["verdict"])

    # Escalate to advisor — spawn pending flag; actual advisor agent picks up
    _spawn_advisor_pending(exec_result, hook_input)
    # In CC hook context we cannot await agent. Emit advisory and let Stop hook re-check.
    sys.stderr.write(
        "[aiden-auto quota-executor] ESCALATE: quota-advisor invoked. "
        "Pending flag written.\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
