#!/usr/bin/env python3
"""
Agent Teams 프로토콜 강제 Hook - bare Agent() 호출 차단

PreToolUse(Agent) 이벤트에서 실행됩니다.
team_name 없이 실행형 에이전트를 스폰하는 것을 물리적으로 차단합니다.
"""

import json
import sys

# team_name 없이도 허용되는 에이전트 타입 (단순 조회/탐색용)
EXEMPT_TYPES = {
    "Explore",
    "Plan",
    "general-purpose",
    # statusline-setup 등 시스템 에이전트
    "statusline-setup",
}

# 항상 차단 대상인 실행형 에이전트 접두사
EXECUTION_PREFIXES = [
    "executor",
    "architect",
    "code-reviewer",
    "designer",
    "qa-tester",
    "writer",
    "planner",
    "critic",
    "researcher",
    "scientist",
    "security-reviewer",
    "tdd-guide",
    "build-fixer",
    "feature-dev:",
    "superpowers:",
    "code-simplifier:",
]


def is_execution_agent(subagent_type: str) -> bool:
    """실행형 에이전트인지 판별"""
    if not subagent_type:
        return True  # 타입 없으면 general-purpose → 실행 가능성 있음

    # 면제 목록 확인
    if subagent_type in EXEMPT_TYPES:
        return False

    # 면제 목록에 없는 모든 에이전트는 실행형으로 간주
    return True


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "approve"}))
            return

        data = json.loads(input_data)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        # Agent 도구만 검증
        if tool_name != "Agent":
            print(json.dumps({"decision": "approve"}))
            return

        subagent_type = tool_input.get("subagent_type", "")
        team_name = tool_input.get("team_name", "")
        name = tool_input.get("name", "")
        description = tool_input.get("description", "")

        # 면제 에이전트는 통과
        if not is_execution_agent(subagent_type):
            print(json.dumps({"decision": "approve"}))
            return

        # 실행형 에이전트: team_name 필수
        missing = []
        if not team_name:
            missing.append("team_name")
        if not name:
            missing.append("name")
        if not description:
            missing.append("description")

        if missing:
            missing_str = ", ".join(missing)
            print(
                json.dumps(
                    {
                        "decision": "block",
                        "reason": f"Agent Teams 프로토콜 위반 차단\n\n"
                        f"에이전트: {subagent_type or '(미지정)'}\n"
                        f"누락 파라미터: {missing_str}\n\n"
                        f"실행형 에이전트는 Agent Teams 라이프사이클 필수:\n"
                        f"TeamCreate → Agent(team_name+name+description) → SendMessage → TeamDelete\n\n"
                        f"단순 조회는 Explore, Plan, general-purpose 사용.",
                    }
                )
            )
            return

        print(json.dumps({"decision": "approve"}))

    except Exception as e:
        # 에러 시 허용 (Hook 실패로 작업 차단 방지)
        print(json.dumps({"decision": "approve", "error": str(e)}))


if __name__ == "__main__":
    main()
