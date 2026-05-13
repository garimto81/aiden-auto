#!/usr/bin/env python3
"""
subagent_zombie_detector.py — SubagentStop Hook
teammate 프로세스 종료 감지, JSONL 기록, Lead 알림, 팀 레지스트리 정리

요구사항:
- F-02: SubagentStop 이벤트 시 teammate 정보 수집
- F-03: zombie-alerts.jsonl JSONL 기록
- F-04: stderr 경고 출력
- F-05: 팀 전원 종료 시 레지스트리 자동 정리
"""
import json
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path


def get_unix_ms():
    """현재 시각을 Unix ms로 반환"""
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def load_config(config_path):
    """config.json 로드. 실패 시 None 반환"""
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def find_teammate(teams_dir, session_id):
    """
    teams_dir에서 session_id와 매칭되는 teammate 탐색
    반환: (team_dir, team_name, teammate_name, config) 또는 None
    """
    if not teams_dir.exists():
        return None

    for team_dir in teams_dir.iterdir():
        if not team_dir.is_dir():
            continue
        config_path = team_dir / "config.json"
        config = load_config(config_path)
        if config is None:
            continue

        lead_id = config.get("leadSessionId", "")
        # Lead 세션은 제외
        if lead_id == session_id:
            continue

        members = config.get("members", [])
        for member in members:
            agent_id = member.get("agentId", "")
            if agent_id == session_id or session_id in agent_id:
                team_name = config.get("teamName", team_dir.name)
                teammate_name = member.get("name", "unknown")
                return (team_dir, team_name, teammate_name, config)

    return None


def check_all_stopped(config, stopped_session_id):
    """
    팀 전원 종료 여부 판정
    현재 이벤트가 마지막 teammate인지 확인
    Note: agent_type으로 teammate/subagent 구분 가능 (v25.3)
    """
    lead_id = config.get("leadSessionId", "")
    members = config.get("members", [])
    teammates = [m for m in members if m.get("agentId", "") != lead_id]

    if not teammates:
        return False

    # 마지막 1명의 teammate이고, 그게 현재 종료된 세션인 경우
    return len(teammates) == 1 and teammates[0].get("agentId", "") == stopped_session_id


def append_alert(alerts_path, record):
    """zombie-alerts.jsonl에 레코드 추가"""
    try:
        with open(alerts_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[zombie-detector] JSONL 쓰기 실패: {e}", file=sys.stderr)


def main():
    try:
        # stdin JSON 파싱
        raw = sys.stdin.read().strip()
        if not raw:
            return

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        session_id = data.get("session_id", "")
        exit_code = int(data.get("exit_code", 0))
        agent_type = data.get("agent_type", "unknown")

        if not session_id:
            return

        # teams 디렉토리에서 teammate 탐색
        teams_dir = Path.home() / ".claude" / "teams"
        result = find_teammate(teams_dir, session_id)

        if result is None:
            return

        team_dir, team_name, teammate_name, config = result

        # JSONL 레코드 기록
        alert_type = "crash" if exit_code != 0 else "normal"
        record = {
            "ts": get_unix_ms(),
            "team": team_name,
            "teammate": teammate_name,
            "exit_code": exit_code,
            "type": alert_type,
            "agent_type": agent_type,
            "session_id": session_id,
        }
        alerts_path = Path.home() / ".claude" / "zombie-alerts.jsonl"
        append_alert(alerts_path, record)

        # 에이전트 실행 이력 기록 (Persistent Memory)
        try:
            history_dir = Path.home() / ".claude" / "logs"
            history_dir.mkdir(parents=True, exist_ok=True)
            history_path = history_dir / "agent_history.jsonl"
            history_record = {
                "ts": get_unix_ms(),
                "agent_type": data.get("agent_type", "unknown"),
                "name": teammate_name,
                "team": team_name,
                "exit_code": exit_code,
                "status": "success" if exit_code == 0 else "failure",
            }
            with open(history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(history_record) + "\n")
        except Exception:
            pass

        # stderr 경고 출력 (F-04)
        print(
            f"[ZOMBIE-ALERT] {agent_type} '{teammate_name}' in team '{team_name}' "
            f"has exited (code={exit_code})",
            file=sys.stderr,
        )

        # 팀 전원 종료 시 레지스트리 정리 (F-05)
        if check_all_stopped(config, session_id):
            try:
                shutil.rmtree(team_dir, ignore_errors=True)
                print(
                    f"[zombie-detector] team '{team_name}' registry cleaned up",
                    file=sys.stderr,
                )
            except Exception as e:
                print(
                    f"[zombie-detector] 팀 레지스트리 삭제 실패: {e}",
                    file=sys.stderr,
                )

    except Exception as e:
        try:
            print(f"[zombie-detector] error: {e}", file=sys.stderr)
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
