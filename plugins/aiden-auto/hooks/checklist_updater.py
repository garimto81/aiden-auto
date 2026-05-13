#!/usr/bin/env python3
"""
Checklist Auto-Updater Hook
서브 에이전트(Task tool) 완료 시 체크리스트 자동 업데이트
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


def find_checklist_yaml(start_path: Path) -> Path | None:
    """현재 디렉토리부터 상위로 checklist.yaml 검색"""
    current = start_path
    while current != current.parent:
        checklist = current / "checklist.yaml"
        if checklist.exists():
            return checklist
        current = current.parent
    return None


def update_checklist(checklist_path: Path, task_result: dict) -> bool:
    """체크리스트 YAML 업데이트"""
    try:
        with open(checklist_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        now = datetime.now().isoformat()
        data["updated_at"] = now

        # current_task가 있으면 completed로 이동
        current = data.get("current_task")
        if current and current.get("id"):
            completed_task = {
                "id": current["id"],
                "title": current.get("title", ""),
                "completed_at": now,
                "agent": current.get("agent", "unknown"),
                "result": {
                    "success": task_result.get("success", True),
                    "files_changed": task_result.get("files_changed", []),
                    "notes": task_result.get("notes", "자동 완료 처리됨"),
                },
            }

            if "completed" not in data:
                data["completed"] = []
            data["completed"].insert(0, completed_task)

            # agent_logs에 로그 추가
            if "agent_logs" not in data:
                data["agent_logs"] = []
            data["agent_logs"].append(
                {
                    "timestamp": now,
                    "agent": current.get("agent", "unknown"),
                    "task_id": current["id"],
                    "action": "작업 완료",
                    "status": (
                        "success" if task_result.get("success", True) else "failed"
                    ),
                }
            )

            # current_task 클리어
            data["current_task"] = None

            # stats 업데이트
            if "stats" in data:
                data["stats"]["completed"] = data["stats"].get("completed", 0) + 1
                data["stats"]["in_progress"] = max(
                    0, data["stats"].get("in_progress", 1) - 1
                )

        with open(checklist_path, "w", encoding="utf-8") as f:
            yaml.dump(
                data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
            )

        return True
    except Exception as e:
        print(f"체크리스트 업데이트 실패: {e}", file=sys.stderr)
        return False


def main():
    """메인 함수 - Hook에서 호출됨"""
    # stdin에서 hook 데이터 읽기
    try:
        input_data = sys.stdin.read()
        if not input_data:
            sys.exit(0)

        hook_data = json.loads(input_data)
    except json.JSONDecodeError:
        sys.exit(0)

    # Task tool 완료 확인
    tool_name = hook_data.get("tool_name", "")
    if tool_name != "Task":
        sys.exit(0)

    # 결과 파싱
    tool_result = hook_data.get("tool_result", {})

    # 성공 여부 판단 (에러가 없으면 성공)
    is_success = "error" not in str(tool_result).lower()

    task_result = {
        "success": is_success,
        "files_changed": [],  # PostToolUse에서는 파일 변경 추적 어려움
        "notes": "서브 에이전트 작업 완료",
    }

    # yaml 미설치 시 스킵
    if yaml is None:
        print(json.dumps({"continue": True}))
        return

    # 체크리스트 찾기 및 업데이트
    cwd = Path(hook_data.get("cwd", os.getcwd()))
    checklist_path = find_checklist_yaml(cwd)

    if checklist_path:
        if update_checklist(checklist_path, task_result):
            print(f"✅ 체크리스트 업데이트: {checklist_path.name}", file=sys.stderr)

    # Hook은 항상 성공 반환 (차단하지 않음)
    print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
