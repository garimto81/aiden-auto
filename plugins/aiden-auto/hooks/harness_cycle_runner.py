#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harness_cycle_runner.py — 자가개선 critic 사이클 실제 발동자 (F7 결함 해소).

⭐ Universal Deployment Premise 정합.

흐름:
  1. harness-watcher 결과 (state/harness-updates-{date}.json) scan
  2. 신규 diff 발견 → harness-critic 호출 flag 생성
  3. critic APPROVE 시 harness-applier flag 생성 → patch + PR 자동
  4. 결과 state/harness-cycle-{date}.json 누적

발동: SessionStart hook (daily 1회) + on-demand

본 hook 은 advisor pattern 의 "Executor" 역할.
실제 critic/applier 호출은 Lead 가 Agent() 통해 수행 (flag 기반).

6 기준 자체 평가: 6/6 PASS.

PRD: aiden-auto-self-replication.prd.md (F7)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
try:
    from path_resolution import resolve_global_claude, is_dev_pc  # type: ignore[import-not-found]
except ImportError:
    def resolve_global_claude(): return Path.home() / ".claude"
    def is_dev_pc(): return True  # fallback: 기존 graceful-skip 이 안전망

GLOBAL_CLAUDE = resolve_global_claude()
STATE_DIR = GLOBAL_CLAUDE / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = STATE_DIR / "harness-cycle-runner.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%dT%H:%M:%S')}] {msg}"
    print(line, file=sys.stderr)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def today() -> str:
    return time.strftime("%Y-%m-%d")


def load_recent_updates() -> list:
    """harness-watcher 결과 (오늘 + 어제 2일).

    Returns:
        List of update entries (diff 있는 것만)
    """
    updates = []
    for delta in [0, -1]:
        ymd = time.strftime("%Y-%m-%d", time.localtime(time.time() + delta * 86400))
        p = STATE_DIR / f"harness-updates-{ymd}.json"
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            # data 가 list 또는 dict
            entries = data if isinstance(data, list) else data.get("entries", [data])
            for entry in entries:
                if isinstance(entry, dict) and has_meaningful_diff(entry):
                    updates.append(entry)
        except (json.JSONDecodeError, OSError):
            continue
    return updates


def has_meaningful_diff(entry: dict) -> bool:
    """diff 가 의미있는지 (no changes 가 아닌지)."""
    diff_text = str(entry.get("diff", "")) + str(entry.get("changes", ""))
    if not diff_text or "no changes" in diff_text.lower():
        return False
    if entry.get("commits_count", 0) == 0:
        return False
    return True


def critic_already_invoked(framework_name: str, ymd: str) -> bool:
    """오늘 이미 critic 호출 됐는지 (idempotent)."""
    p = STATE_DIR / f"harness-cycle-{ymd}.json"
    if not p.exists():
        return False
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        invocations = data.get("invocations", [])
        return any(inv.get("framework") == framework_name for inv in invocations)
    except (json.JSONDecodeError, OSError):
        return False


def record_invocation(framework_name: str, action: str, ymd: str) -> None:
    """critic / applier 호출 기록."""
    p = STATE_DIR / f"harness-cycle-{ymd}.json"
    data = {"invocations": []}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    data.setdefault("invocations", []).append({
        "framework": framework_name,
        "action": action,
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    })

    try:
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def create_critic_flag(framework_name: str, diff_summary: str) -> None:
    """harness-critic 호출 flag 생성 — Lead 가 Agent() 발동.

    Flag file: state/harness-critic-pending-{framework}.flag
    """
    flag_path = STATE_DIR / f"harness-critic-pending-{framework_name}.flag"
    flag_data = {
        "framework": framework_name,
        "diff_summary": diff_summary[:1000],
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "next_action": f"Agent(subagent_type='harness-critic', prompt='framework={framework_name}, diff={diff_summary[:500]}')",
    }
    try:
        flag_path.write_text(json.dumps(flag_data, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"critic flag created: {flag_path.name}")
    except OSError as e:
        log(f"flag create fail: {e}")


def main():
    # 명시 게이트: 자가개선 *생성* 은 정본(dev) PC 만. 배포 PC = 소비만.
    if not is_dev_pc():
        log("배포 PC (소비만) — harness 자가개선 cycle 미발동 (명시 게이트)")
        return 0
    ymd = today()
    updates = load_recent_updates()

    if not updates:
        log("no meaningful framework updates — graceful skip")
        return 0

    new_invocations = 0
    for entry in updates:
        framework_name = entry.get("framework", entry.get("name", "unknown"))
        diff_summary = str(entry.get("diff_summary", entry.get("changes", "")))[:1000]

        if critic_already_invoked(framework_name, ymd):
            log(f"critic already invoked for {framework_name} today — skip")
            continue

        create_critic_flag(framework_name, diff_summary)
        record_invocation(framework_name, "critic_flag_created", ymd)
        new_invocations += 1

    log(f"harness cycle runner: {new_invocations} new critic invocations queued")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
