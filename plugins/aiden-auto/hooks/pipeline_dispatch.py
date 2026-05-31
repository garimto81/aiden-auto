#!/usr/bin/env python
"""Super Harness Framework v3.2 — Pipeline Dispatch (claude --bg auto).

Triggered on user plain-text "implement X" patterns. Auto-dispatches a
background session via `claude --bg` (agent-view pattern).

Detection patterns (Korean + English):
  - "implement", "make", "build", "create"
  - "만들어", "구현", "생성"

Status: STUB v0.1 — pattern detection only. Actual `claude --bg`
invocation is delegated to the user's Claude Code CLI v2.1.139+.
PRD reference: C:\\claude\\docs\\00-prd\\super-harness-framework.prd.md §10.1
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()  # 외부배포 HIGH-1: 하드코딩 제거
DISPATCH_LOG = Path(PROJECT_DIR) / ".claude" / "state" / "pipeline-dispatch-log.jsonl"

# Detection keywords for "implement X" intent
IMPLEMENT_PATTERNS = [
    r"\bimplement\b",
    r"\bbuild\b",
    r"\bmake\b",
    r"\bcreate\b",
    r"만들어",
    r"구현",
    r"생성",
]

IMPLEMENT_REGEX = re.compile("|".join(IMPLEMENT_PATTERNS), re.IGNORECASE)


def is_implement_intent(text: str) -> bool:
    if not text or len(text) < 4:
        return False
    return bool(IMPLEMENT_REGEX.search(text))


def log_dispatch_decision(text: str, dispatched: bool, reason: str) -> None:
    DISPATCH_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now().isoformat(),
        "text_preview": text[:120],
        "dispatched": dispatched,
        "reason": reason,
    }
    with DISPATCH_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def main() -> int:
    """Hook entry: analyze user input, log decision.

    NOTE: This stub does NOT actually invoke `claude --bg`. Real dispatch
    requires UserPromptSubmit hook integration and is a future v0.2 item.
    For v0.1, we only log detection decisions for later analysis.
    """
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        payload = {}
    user_text = payload.get("prompt") or payload.get("text") or ""

    if is_implement_intent(user_text):
        log_dispatch_decision(user_text, dispatched=False,
                              reason="detected — bg dispatch deferred to v0.2")
        verdict = {
            "would_dispatch": True,
            "command_hint": f'claude --bg "{user_text[:80]}"',
            "next_stage": "Stage 1 — PLAN (brainstorming)",
        }
    else:
        verdict = {"would_dispatch": False, "reason": "no implement intent"}

    print(json.dumps(verdict, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
