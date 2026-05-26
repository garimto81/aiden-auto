#!/usr/bin/env python
"""
Agent Teams 프로토콜 강제 Hook — DEPRECATED 2026-05-26.

폐기 사유: 글로벌 CLAUDE.md (2026-05-07) 에서 TeamCreate / SendMessage /
shutdown_request / team_name / TeamDelete 모두 폐기 선언. 신규 표준:
Agent(subagent_type, description, prompt) 단일 호출.

본 hook 는 옛 protocol 을 12 self-critic cycle 동안 강제하여
critic agent 위임을 차단했음 (G3 갭, 2026-05-26 평가 확인).

"Removal isn't the answer" 정책 — 파일 + 변수 보존, 강제 로직만 무효화.
2026-05-26 R3 자율 정정.
"""

import json
import sys

# (보존) team_name 없이도 허용되는 에이전트 타입 — 옛 protocol 흔적
EXEMPT_TYPES = {
    "Explore",
    "Plan",
    "general-purpose",
    "statusline-setup",
}

# (보존) 옛 실행형 에이전트 접두사 — 현재는 의미 없음, 참조 목적만
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
    """DEPRECATED 2026-05-26 — 항상 False 반환 (모든 agent 면제).

    옛 Agent Teams 강제 폐기. 신규 protocol 에서는 subagent_type +
    description + prompt 만으로 충분. team_name / name 강제 없음.
    """
    return False


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
