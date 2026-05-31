#!/usr/bin/env python
"""Super Harness Framework v3.2 — Daily Autonomous Loop (5-step).

SessionStart hook. Runs once per day (last_run.json 24h guard).

5 Steps:
  1. Receipts auto-analyze (bad >= 3 in stage → flag routing update)
  2. Blog auto-fetch (claude.com/blog new posts, recognition >= 5000 → routing add)
  3. Plugin replacement auto-decide (NIH inventory evidence → redirect plan)
  4. New veteran auto-discover (GitHub trending claude-code-*, recognition >= 8000)
  5. Daily report append (receipts.jsonl meta-daily entry)

Status: STUB v0.1 — minimal implementation. Real logic added in future iterations.
PRD reference: C:\\claude\\docs\\00-prd\\super-harness-framework.prd.md §9
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Paths
PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()  # 외부배포 HIGH-1: 하드코딩 제거
RECEIPTS = Path(PROJECT_DIR) / ".claude" / "state" / "absorption-receipts.jsonl"
LAST_RUN = Path(PROJECT_DIR) / ".claude" / "state" / "daily-loop-last-run.json"

# 24h guard threshold (seconds)
GUARD_SECONDS = 24 * 3600


def already_ran_today() -> bool:
    if not LAST_RUN.exists():
        return False
    try:
        last = json.loads(LAST_RUN.read_text(encoding="utf-8"))
        last_ts = datetime.fromisoformat(last["timestamp"])
        delta = (datetime.now(timezone.utc) - last_ts).total_seconds()
        return delta < GUARD_SECONDS
    except Exception:
        return False


def step_1_analyze_receipts() -> dict:
    """Analyze recent receipts for bad outcome patterns."""
    if not RECEIPTS.exists():
        return {"bad_count": 0, "stages_flagged": []}
    bad_by_stage: dict[str, int] = {}
    try:
        for line in RECEIPTS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("outcome") == "bad":
                stage = entry.get("stage", "unknown")
                bad_by_stage[stage] = bad_by_stage.get(stage, 0) + 1
    except Exception:
        pass
    flagged = [s for s, c in bad_by_stage.items() if c >= 3]
    return {"bad_count": sum(bad_by_stage.values()), "stages_flagged": flagged}


def step_2_blog_fetch() -> dict:
    """STUB — Blog fetch not implemented in v0.1.
    Future: WebFetch claude.com/blog, filter, recognition score.
    """
    return {"new_posts": 0, "absorbed": 0, "note": "stub v0.1"}


def step_3_plugin_replacement() -> dict:
    """STUB — Plugin replacement evidence not implemented in v0.1."""
    return {"candidates": 0, "auto_redirect": 0, "note": "stub v0.1"}


def step_4_new_veteran_discover() -> dict:
    """STUB — GitHub trending discovery not implemented in v0.1."""
    return {"discovered": 0, "added_to_roster": 0, "note": "stub v0.1"}


def step_5_report_append(summary: dict) -> None:
    """Append daily meta entry to receipts.jsonl."""
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "stage": "meta-daily",
        "sub_phase": None,
        "authority": "meta",
        "executor_model": "hook",
        "advisor_calls": 0,
        "retry_count": 0,
        "screenshots": [],
        "verify_gates": {},
        "intent": "daily autonomous loop (5-step stub v0.1)",
        "outcome": "good" if summary["bad_count"] < 3 else "neutral",
        "notes": json.dumps(summary, ensure_ascii=False),
    }
    RECEIPTS.parent.mkdir(parents=True, exist_ok=True)
    with RECEIPTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    if already_ran_today():
        return 0  # silent skip
    summary = {
        "step_1": step_1_analyze_receipts(),
        "step_2": step_2_blog_fetch(),
        "step_3": step_3_plugin_replacement(),
        "step_4": step_4_new_veteran_discover(),
    }
    summary["bad_count"] = summary["step_1"]["bad_count"]
    step_5_report_append(summary)
    LAST_RUN.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN.write_text(
        json.dumps({"timestamp": datetime.now(timezone.utc).isoformat()}),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
