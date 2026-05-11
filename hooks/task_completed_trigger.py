#!/usr/bin/env python3
"""
task_completed_trigger.py — PostToolUse(TaskUpdate) Hook
Task 완료 시 다음 단계 알림 로그 생성 + Phase 전환 감지

요구사항:
- TaskUpdate(status=completed) 감지 시 stderr 알림
- Phase 접두사 기반 Phase 전환 감지 (P2→P3 등)
- task-transitions.jsonl에 전환 기록
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def get_unix_ms():
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def main():
    try:
        raw = sys.stdin.read().strip()
        if not raw:
            print(json.dumps({"continue": True}))
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            print(json.dumps({"continue": True}))
            return

        # PostToolUse 이벤트에서 tool_name과 tool_input 확인
        tool_name = data.get("tool_name", "")
        if tool_name != "TaskUpdate":
            print(json.dumps({"continue": True}))
            return

        tool_input = data.get("tool_input", {})
        new_status = tool_input.get("status", "")
        task_id = tool_input.get("taskId", "")

        if new_status != "completed":
            print(json.dumps({"continue": True}))
            return

        # Phase 접두사 감지 (TaskCreate의 subject에서)
        tool_output = data.get("tool_output", "")
        phase_prefix = ""
        if "[P2-" in str(tool_output) or f"Task #{task_id}" in str(tool_output):
            # Phase 전환 가능성 감지
            phase_prefix = "P2"

        # 전환 기록
        log_dir = Path.home() / ".claude" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "task-transitions.jsonl"

        record = {
            "ts": get_unix_ms(),
            "task_id": task_id,
            "status": "completed",
            "phase_hint": phase_prefix,
        }

        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

        # stderr 알림
        print(
            f"[TASK-COMPLETED] Task #{task_id} completed",
            file=sys.stderr,
        )

    except Exception as e:
        try:
            print(f"[task-trigger] error: {e}", file=sys.stderr)
        except Exception:
            pass
    finally:
        try:
            print(json.dumps({"continue": True}))
        except Exception:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
