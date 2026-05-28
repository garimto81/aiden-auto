#!/usr/bin/env python3
"""
커맨드 사용 로깅 스크립트
Usage: python command-logger.py <command-name> [subcommand]
"""

import json
import sys
from datetime import datetime
from pathlib import Path

LOG_FILE = Path(__file__).parent.parent / "logs" / "command-usage.json"


def load_usage_data() -> dict:
    """기존 사용 데이터 로드"""
    if LOG_FILE.exists():
        try:
            return json.loads(LOG_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"commands": {}, "daily": {}, "total_calls": 0}
    return {"commands": {}, "daily": {}, "total_calls": 0}


def save_usage_data(data: dict) -> None:
    """사용 데이터 저장"""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOG_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def log_command(command: str, subcommand: str = None) -> None:
    """커맨드 사용 기록"""
    data = load_usage_data()
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().isoformat()

    # 전체 커맨드명 구성
    full_command = f"/{command}"
    if subcommand:
        full_command = f"/{command} {subcommand}"

    # 커맨드별 통계
    if full_command not in data["commands"]:
        data["commands"][full_command] = {
            "count": 0,
            "first_used": timestamp,
            "last_used": timestamp,
        }

    data["commands"][full_command]["count"] += 1
    data["commands"][full_command]["last_used"] = timestamp

    # 일별 통계
    if today not in data["daily"]:
        data["daily"][today] = {}

    if full_command not in data["daily"][today]:
        data["daily"][today][full_command] = 0

    data["daily"][today][full_command] += 1
    data["total_calls"] += 1

    save_usage_data(data)
    print(f"Logged: {full_command} (total: {data['commands'][full_command]['count']})")


def show_stats() -> None:
    """사용 통계 출력"""
    data = load_usage_data()

    print("\n=== 커맨드 사용 통계 ===\n")
    print(f"총 호출 횟수: {data['total_calls']}\n")

    # 사용 빈도순 정렬
    sorted_commands = sorted(
        data["commands"].items(), key=lambda x: x[1]["count"], reverse=True
    )

    print("커맨드별 사용 횟수:")
    print("-" * 50)
    for cmd, stats in sorted_commands:
        print(f"  {cmd:<30} {stats['count']:>5}회")

    # 최근 7일 통계
    print("\n최근 7일 일별 사용:")
    print("-" * 50)
    recent_days = sorted(data["daily"].keys(), reverse=True)[:7]
    for day in recent_days:
        total = sum(data["daily"][day].values())
        print(f"  {day}: {total}회")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python command-logger.py <command> [subcommand]")
        print("       python command-logger.py --stats")
        sys.exit(1)

    if sys.argv[1] == "--stats":
        show_stats()
    else:
        command = sys.argv[1].lstrip("/")
        subcommand = sys.argv[2] if len(sys.argv) > 2 else None
        log_command(command, subcommand)
