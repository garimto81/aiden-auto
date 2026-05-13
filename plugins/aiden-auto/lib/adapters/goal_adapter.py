"""goal_adapter.py — v28.2 CC /goal mechanism 격리

/goal API + Stop hook 메커니즘의 schema 변화를 흡수. 코어 코드는 본 adapter만 호출.

Schema version: 1.0
Section 13.2 정합 — feature detection > 가정, try/except + graceful degradation.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["2.0+"]  # CC 2.x onwards

def _resolve_plugin_root() -> Path:
    """PLUGIN_ROOT 결정: env var → __file__ 기반 fallback.
    lib/adapters/ 기준: parent.parent.parent = plugin root.
    """
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent.parent


PLUGIN_ROOT = _resolve_plugin_root()
STATE_DIR = PLUGIN_ROOT / "state"


class EvaluatorVerdict(NamedTuple):
    achieved: bool
    reason: str
    raw_excerpt: str


def detect_goal_capability() -> bool:
    """Feature detection: does this CC version support /goal?"""
    try:
        result = subprocess.run(
            ["claude", "--help"], capture_output=True, text=True, timeout=5
        )
        return "/goal" in result.stdout or "goal" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False  # graceful: assume no, use Stop hook fallback


def emit_goal_command(condition: str, headless: bool = True) -> tuple[bool, str]:
    """Invoke /goal via CC. Returns (success, output_or_error).

    headless=True uses `claude -p` (non-interactive).
    """
    if not detect_goal_capability():
        return (False, "CC /goal not detected; using Stop hook fallback")
    try:
        if headless:
            result = subprocess.run(
                ["claude", "-p", f"/goal '{condition}'"],
                capture_output=True, text=True, timeout=10,
            )
            return (result.returncode == 0, result.stdout or result.stderr)
        # Interactive path — print user guidance instead
        return (True, f"User please type: /goal '{condition}'")
    except subprocess.SubprocessError as e:
        return (False, f"goal command error: {e}")


def parse_evaluator_feedback(transcript_chunk: str) -> EvaluatorVerdict:
    """Section 13.2: try new JSON format first, fallback to legacy text.

    /goal evaluator의 출력 형식이 변경돼도 본 함수만 수정.
    """
    # Try 1: JSON format (hypothetical future)
    try:
        for line in transcript_chunk.strip().split("\n"):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                data = json.loads(line)
                if "achieved" in data:
                    return EvaluatorVerdict(
                        achieved=bool(data["achieved"]),
                        reason=data.get("reason", ""),
                        raw_excerpt=line,
                    )
    except (json.JSONDecodeError, ValueError):
        pass

    # Try 2: legacy text patterns
    patterns_achieved = [
        r"goal\s+achieved",
        r"✓\s+achieved",
        r"condition\s+met",
        r"all\s+criteria\s+pass(ed)?",
    ]
    patterns_continue = [
        r"goal\s+not\s+met",
        r"continue\s+iteration",
        r"❌\s*fail",
    ]
    txt = transcript_chunk.lower()
    for p in patterns_achieved:
        if re.search(p, txt):
            return EvaluatorVerdict(achieved=True, reason="legacy pattern matched", raw_excerpt=p)
    for p in patterns_continue:
        if re.search(p, txt):
            return EvaluatorVerdict(achieved=False, reason="continue marker", raw_excerpt=p)

    # Default: not achieved (continue loop)
    return EvaluatorVerdict(achieved=False, reason="no terminal marker", raw_excerpt="")


def write_goal_state(session_id: str, condition: str, safety_clauses: list[str] | None = None) -> Path:
    """Lightweight wrapper around lib.goal.goal_writer.write_goal_from_explicit.

    Adapter layer — exposes single stable API even if goal_writer.py refactors.
    """
    sys.path.insert(0, str(PLUGIN_ROOT))
    from lib.goal.goal_writer import write_goal_from_explicit, append_safety_clauses
    cond = append_safety_clauses(condition, custom=safety_clauses)
    return write_goal_from_explicit(session_id, cond)


def read_goal_state(session_id: str) -> dict | None:
    path = STATE_DIR / f"active-goal-{session_id}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Schema migration check (Section 13.4)
        v = data.get("schema_version", "0.0")
        if v != SCHEMA_VERSION:
            return _migrate_schema(data, from_v=v, to_v=SCHEMA_VERSION)
        return data
    except (OSError, json.JSONDecodeError):
        return None


def _migrate_schema(data: dict, from_v: str, to_v: str) -> dict:
    """Section 13.4: N-1 automatic migration."""
    if from_v == "0.9" and to_v == "1.0":
        # Example: rename old field
        if "goal_text" in data and "condition" not in data:
            data["condition"] = data.pop("goal_text")
        data["schema_version"] = to_v
        return data
    return data  # unknown migration → return as-is


if __name__ == "__main__":
    print(f"goal_adapter: SUPPORTED={SUPPORTED_VERSIONS}, capability={detect_goal_capability()}")
