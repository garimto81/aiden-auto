#!/usr/bin/env python
"""
도구 사용 검증 Hook - 위험 명령 차단 및 민감 파일 보호

PreToolUse 이벤트에서 실행됩니다.
"""

import json
import re
import sys

# 위험 Bash 명령 패턴
DANGEROUS_BASH_PATTERNS = [
    r"rm\s+-rf\s+/",  # rm -rf /
    r"rm\s+-rf\s+\*",  # rm -rf *
    r"format\s+[a-zA-Z]:",  # format C:
    r"mkfs\.",  # mkfs.ext4
    r"dd\s+if=.*of=/dev",  # dd to device
    r">\s*/dev/sda",  # write to device
    r"chmod\s+-R\s+777\s+/",  # chmod 777 /
    r"chown\s+-R.*\s+/",  # chown /
    r"shutdown",  # shutdown
    r"reboot",  # reboot
    r"init\s+0",  # init 0
    r"rm\s+(-[a-zA-Z]+\s+)*(\.git|[^\s]+[/\\]\.git)(\s|/|$)",  # rm .git (정확한 .git 디렉토리만)
    r"git\s+push.*--force\s+.*main",  # force push to main
    r"git\s+push.*-f\s+.*main",  # force push to main
    r"taskkill\s+/[fF]\s+/[iI][mM]\s+node",  # taskkill /F /IM node.exe
    r"stop-process\s+-name\s+node",  # Stop-Process -Name node
]

# 민감 파일 패턴 (Write 차단)
SENSITIVE_FILE_PATTERNS = [
    r"\.env$",  # .env
    r"\.env\.",  # .env.local, .env.production
    r"credentials\.json$",  # credentials.json
    r"secrets?\.json$",  # secret.json, secrets.json
    r"\.pem$",  # private keys
    r"\.key$",  # private keys
    r"id_rsa",  # SSH keys
    r"\.ssh/",  # SSH directory
    r"password",  # password files
    r"token\.json$",  # token files
]

# 민감 파일 예외 (허용)
SENSITIVE_FILE_EXCEPTIONS = [
    r"\.env\.template$",  # .env.template
    r"\.env\.example$",  # .env.example
    r"\.env\.sample$",  # .env.sample
]


def extract_commands(command: str) -> list[str]:
    """명령어에서 실제 실행되는 부분만 추출 (heredoc, 문자열 리터럴 제외)"""
    # heredoc 제거 (<<EOF ... EOF, <<'EOF' ... EOF 등)
    command = re.sub(r"<<-?\s*['\"]?(\w+)['\"]?.*?\1", "", command, flags=re.DOTALL)

    # 따옴표 내 문자열 제거 (python -c "..." 등)
    command = re.sub(r'"[^"]*"', '""', command)
    command = re.sub(r"'[^']*'", "''", command)

    # 명령어 분리 (&&, ||, ;, |)
    commands = re.split(r"\s*(?:&&|\|\||;|\|)\s*", command)

    return [cmd.strip() for cmd in commands if cmd.strip()]


def is_dangerous_bash(command: str) -> tuple[bool, str]:
    """위험한 Bash 명령인지 확인"""
    # 실제 실행되는 명령어만 추출
    commands = extract_commands(command)

    for cmd in commands:
        cmd_lower = cmd.lower()

        # rm -rf ~ 계열은 safe path 예외 처리
        if re.match(r"rm\s+-rf\s+~", cmd_lower):
            # ~/.claude/teams/ 또는 ~/.claude/tasks/ 경로는 허용
            if re.match(r"rm\s+-rf\s+~/\.claude/(teams|tasks)/", cmd_lower):
                continue  # safe — agent teams cleanup
            # 그 외 rm -rf ~/ 는 차단
            return True, r"rm\s+-rf\s+~"

        for pattern in DANGEROUS_BASH_PATTERNS:
            # 패턴이 명령어 시작 부분에서 매칭되는지 확인
            if re.match(pattern, cmd_lower) or re.search(
                r"(^|/)\s*" + pattern, cmd_lower
            ):
                return True, pattern
    return False, ""


def is_sensitive_file(file_path: str) -> tuple[bool, str]:
    """민감 파일인지 확인"""
    # 예외 먼저 확인
    for pattern in SENSITIVE_FILE_EXCEPTIONS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return False, ""

    # 민감 파일 확인
    for pattern in SENSITIVE_FILE_PATTERNS:
        if re.search(pattern, file_path, re.IGNORECASE):
            return True, pattern
    return False, ""


def main():
    try:
        input_data = sys.stdin.read()
        if not input_data.strip():
            print(json.dumps({"decision": "approve"}))
            return

        data = json.loads(input_data)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})

        # Bash 명령 검증
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            is_dangerous, pattern = is_dangerous_bash(command)
            if is_dangerous:
                print(
                    json.dumps(
                        {
                            "decision": "block",
                            "reason": f"🚫 위험한 명령 차단\n\n"
                            f"📌 패턴: {pattern}\n"
                            f"💡 명령어: {command[:100]}...\n\n"
                            f"이 명령은 시스템에 치명적 영향을 줄 수 있습니다.\n"
                            f"bypass가 필요하면 사용자에게 확인하세요.",
                        }
                    )
                )
                return

        # Write/Edit 파일 검증
        if tool_name in ["Write", "Edit"]:
            file_path = tool_input.get("file_path", "")
            is_sensitive, pattern = is_sensitive_file(file_path)
            if is_sensitive:
                print(
                    json.dumps(
                        {
                            "decision": "block",
                            "reason": f"🚫 민감 파일 보호\n\n"
                            f"📁 파일: {file_path}\n"
                            f"📌 패턴: {pattern}\n\n"
                            f"민감 정보가 포함된 파일입니다.\n"
                            f"수정이 필요하면 사용자에게 확인하세요.",
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
