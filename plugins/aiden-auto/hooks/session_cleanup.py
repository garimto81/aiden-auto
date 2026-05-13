#!/usr/bin/env python3
"""
세션 종료 Hook - 미완료 작업 저장, 세션 요약, 임시 파일 정리

SessionEnd 이벤트에서 실행됩니다.
"""

import json
import os
import glob
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_DIR = os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())
SESSION_FILE = Path(PROJECT_DIR) / ".claude" / "session_state.json"
TEMP_PATTERNS = [
    "temp_*.py",
    "temp_*.txt",
    "temp_*.md",
    "*.tmp",
    "*.bak",
    "tmpclaude-*",
    # v21.0: ralph/ultrawork state 파일은 Agent Teams lifecycle으로 대체됨
]


def load_session_state() -> dict:
    """현재 세션 상태 로드"""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_session_state(state: dict):
    """세션 상태 저장"""
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    state["last_end"] = datetime.now().isoformat()
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def find_temp_files() -> list:
    """임시 파일 목록 찾기"""
    temp_files = []
    for pattern in TEMP_PATTERNS:
        matches = glob.glob(os.path.join(PROJECT_DIR, pattern))
        temp_files.extend(matches)
        # 하위 디렉토리도 검색 (1단계만)
        matches = glob.glob(os.path.join(PROJECT_DIR, "*", pattern))
        temp_files.extend(matches)
    return temp_files


def cleanup_temp_files(files: list) -> int:
    """임시 파일 즉시 삭제"""
    cleaned = 0
    for f in files:
        try:
            os.remove(f)
            cleaned += 1
        except Exception:
            pass
    return cleaned


def cleanup_stale_agent_teams(ttl_hours: float = 10 / 60) -> dict:  # 기본값: 10분
    """Agent Teams/Tasks 디렉토리 중 TTL 초과한 항목 삭제"""
    home = Path.home()
    teams_dir = home / ".claude" / "teams"
    tasks_dir = home / ".claude" / "tasks"
    result = {"teams_deleted": 0, "tasks_deleted": 0, "errors": []}

    # Teams 정리 (config.json의 createdAt 기준)
    if teams_dir.exists():
        for entry in teams_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                config_file = entry / "config.json"
                if config_file.exists():
                    with open(config_file, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    created = config.get("createdAt")
                    if created is not None and created != "":
                        created_dt = None
                        if isinstance(created, (int, float)) and created > 0:
                            ts = created / 1000 if created >= 1e12 else float(created)
                            created_dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                        elif isinstance(created, str) and created:
                            created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        else:
                            print(
                                f"[session_cleanup] createdAt 타입 미지원: "
                                f"{type(created).__name__}={created}",
                                file=sys.stderr,
                            )

                        if created_dt is not None:
                            age_hours = (datetime.now(timezone.utc) - created_dt).total_seconds() / 3600
                            if age_hours < ttl_hours:
                                continue
                shutil.rmtree(entry)
                result["teams_deleted"] += 1
            except Exception as e:
                result["errors"].append(f"team/{entry.name}: {e}")

    # Tasks 정리 (mtime 기준)
    if tasks_dir.exists():
        for entry in tasks_dir.iterdir():
            if not entry.is_dir():
                continue
            try:
                mtime = entry.stat().st_mtime
                age_hours = (datetime.now().timestamp() - mtime) / 3600
                if age_hours >= ttl_hours:
                    shutil.rmtree(entry)
                    result["tasks_deleted"] += 1
            except Exception as e:
                result["errors"].append(f"task/{entry.name}: {e}")

    return result


def generate_mcp_report() -> list[str]:
    """MCP 프로파일링 로그에서 세션 요약 리포트 생성"""
    messages = []
    mcp_log = Path(PROJECT_DIR) / ".claude" / "logs" / "mcp_profile.jsonl"
    if not mcp_log.exists():
        return messages
    try:
        lines = mcp_log.read_text(encoding="utf-8").strip().split("\n")
        entries = []
        for line in lines:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue
        if not entries:
            return messages
        # 도구별 호출 수
        tool_counts: dict[str, int] = {}
        for e in entries:
            tool = e.get("tool", "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        total = len(entries)
        top_tools = sorted(tool_counts.items(), key=lambda x: -x[1])[:3]
        top_str = ", ".join(f"{t}({c})" for t, c in top_tools)
        messages.append(f"MCP profile: {total} calls. Top: {top_str}")
        # 로그 파일 아카이브 (새 세션을 위해 비우기)
        archive_path = mcp_log.with_suffix(
            f".{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.jsonl"
        )
        mcp_log.rename(archive_path)
    except Exception:
        pass
    return messages


def main():
    try:
        # 현재 세션 상태 로드
        state = load_session_state()

        # 세션 종료 정보 수집
        session_info = []

        # 세션 시작 시간
        if state.get("last_start"):
            start_time = state["last_start"][:16]
            session_info.append(f"📍 세션 시작: {start_time}")

        # 미완료 작업 확인 (TodoWrite에서 관리하는 작업)
        pending_tasks = state.get("pending_tasks", [])
        if pending_tasks:
            session_info.append(f"📋 미완료 작업: {len(pending_tasks)}개")
            for task in pending_tasks[:3]:
                session_info.append(f"   - {task}")

        # Agent Teams/Tasks stale 리소스 정리
        teams_result = cleanup_stale_agent_teams(ttl_hours=10 / 60)  # 10분
        if teams_result["teams_deleted"] or teams_result["tasks_deleted"]:
            session_info.append(
                f"🧹 Teams: {teams_result['teams_deleted']}개, Tasks: {teams_result['tasks_deleted']}개 정리"
            )

        # 임시 파일 찾기 및 즉시 삭제
        temp_files = find_temp_files()
        if temp_files:
            cleaned = cleanup_temp_files(temp_files)
            session_info.append(f"🗑️ 임시 파일: {cleaned}개 삭제 완료")

        # MCP 프로파일링 리포트
        session_info.extend(generate_mcp_report())

        # 세션 상태 저장
        save_session_state(
            {
                "branch": state.get("branch", "unknown"),
                "pending_tasks": pending_tasks,
                "temp_files": [os.path.basename(f) for f in temp_files],
                "last_start": state.get("last_start"),
            }
        )

        # 결과 출력
        if session_info:
            message = "\n".join(session_info)
            print(
                json.dumps({"continue": True, "message": f"📍 세션 종료\n\n{message}"})
            )
        else:
            print(json.dumps({"continue": True}))

    except Exception as e:
        print(json.dumps({"continue": True, "error": str(e)}))


if __name__ == "__main__":
    main()
