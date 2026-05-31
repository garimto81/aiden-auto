#!/usr/bin/env python
"""PostToolUse(Agent) hook — 모든 Agent() 호출의 실제 사용 model 을 JSONL 로 기록.

목적:
- 진단 도구: 실제 어떤 subagent_type 가 어떤 model 로 실행되는지 측정
- enforcer hook 의 modify 응답이 실제 적용됐는지 검증
- 누적 분배 확인 (4:3:3 목표 vs 실측)

설계 원칙 (feedback_restore_builtin_first):
- 차단 절대 안 함, 침묵 통과만
- log 실패는 작업 차단 사유 아님
- {"decision": "approve"} 반환 금지

설계 출처: ~/.claude/plans/opus-atomic-spark.md Round 6
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()) / ".claude" / "state" / "agent_model_decisions.jsonl"  # 외부배포 HIGH-1: 하드코딩 제거


def main() -> None:
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            sys.exit(0)
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "Agent":
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})

    # 실제 사용된 model 추출 (tool_response 에 있을 수도, tool_input 에 있을 수도)
    used_model = tool_input.get("model") or tool_response.get("model") or "<unknown>"
    subagent_type = tool_input.get("subagent_type", "")

    record = {
        "ts": datetime.utcnow().isoformat(),
        "phase": "postToolUse",
        "subagent_type": subagent_type,
        "actual_model": used_model,
        "duration_ms": tool_response.get("duration_ms"),
        "tokens": tool_response.get("total_tokens"),
    }

    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass

    # 항상 통과
    sys.exit(0)


if __name__ == "__main__":
    main()
