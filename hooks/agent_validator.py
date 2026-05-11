#!/usr/bin/env python3
"""
에이전트 정의 파일 YAML Frontmatter 검증기

SessionStart hook으로 실행되어 .claude/agents/*.md 파일의
frontmatter 무결성을 검증합니다.

검증 항목:
- 바이트 0에서 `---` 시작 (BOM/공백 없음)
- name, description 필수 필드 존재
- model 값 유효성 (opus/sonnet/haiku)
- tools 필드 형식 검증
"""

import json
import os
import sys
from pathlib import Path

VALID_MODELS = {"opus", "sonnet", "haiku"}

VALID_TOOLS = {
    "Read", "Write", "Edit", "Bash", "Grep", "Glob",
    "WebSearch", "WebFetch", "Agent", "TodoWrite",
    "NotebookRead", "NotebookEdit", "KillShell",
    "BashOutput", "LSP", "Task", "TaskOutput",
    "python_repl",
}


def _get_agents_dir() -> Path:
    if os.name == "nt":
        return Path("C:/claude/.claude/agents")
    wsl = Path("/mnt/c/claude/.claude/agents")
    if wsl.exists():
        return wsl
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd())) / ".claude" / "agents"


def parse_frontmatter(content: str) -> dict | None:
    """YAML frontmatter를 간단히 파싱 (외부 의존성 없이)"""
    if not content.startswith("---"):
        return None

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None

    fm_text = content[3:end_idx].strip()
    result = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result


def validate_agent_file(filepath: Path) -> list[str]:
    """단일 에이전트 파일 검증. 위반 사항 목록 반환."""
    warnings = []
    name = filepath.stem

    try:
        raw_bytes = filepath.read_bytes()
    except Exception as e:
        return [f"{name}: 파일 읽기 실패 ({e})"]

    # BOM 검사
    if raw_bytes[:3] == b"\xef\xbb\xbf":
        warnings.append(f"{name}: UTF-8 BOM 감지 — 바이트 0에서 --- 시작 불가")

    # 공백/개행 선행 검사
    if raw_bytes and raw_bytes[0:3] != b"---":
        if not any(w.endswith("BOM 감지") for w in warnings):
            warnings.append(f"{name}: 바이트 0에서 --- 미시작 (선행 공백/개행 존재)")

    try:
        content = raw_bytes.decode("utf-8-sig")  # BOM 자동 제거하여 파싱 시도
    except UnicodeDecodeError:
        warnings.append(f"{name}: UTF-8 디코딩 실패")
        return warnings

    fm = parse_frontmatter(content.lstrip("\ufeff"))
    if fm is None:
        warnings.append(f"{name}: YAML frontmatter 파싱 실패 (--- 블록 없음)")
        return warnings

    # 필수 필드 검증
    if "name" not in fm:
        warnings.append(f"{name}: 필수 필드 'name' 누락")
    if "description" not in fm:
        warnings.append(f"{name}: 필수 필드 'description' 누락")

    # model 값 검증
    if "model" in fm:
        model_val = fm["model"].strip().lower()
        if model_val not in VALID_MODELS:
            warnings.append(f"{name}: 잘못된 model 값 '{fm['model']}' (허용: {', '.join(VALID_MODELS)})")

    # tools 형식 검증 (쉼표 구분 목록)
    if "tools" in fm:
        tools_str = fm["tools"]
        tools_list = [t.strip() for t in tools_str.split(",") if t.strip()]
        invalid = [t for t in tools_list if t not in VALID_TOOLS and not t.startswith("mcp__")]
        if invalid:
            warnings.append(f"{name}: 알 수 없는 도구 {invalid}")

    return warnings


def main():
    agents_dir = _get_agents_dir()

    if not agents_dir.exists():
        print(json.dumps({"continue": True, "message": "⚠️ 에이전트 디렉토리 없음: " + str(agents_dir)}))
        return

    agent_files = sorted(agents_dir.glob("*.md"))
    total = len(agent_files)

    all_warnings = []
    for f in agent_files:
        all_warnings.extend(validate_agent_file(f))

    if all_warnings:
        warning_text = "\n".join(f"  ⚠️ {w}" for w in all_warnings)
        msg = f"🔍 에이전트 검증: {total}개 파일, {len(all_warnings)}건 경고\n{warning_text}"
        print(json.dumps({"continue": True, "message": msg}))
    else:
        print(json.dumps({"continue": True}))


if __name__ == "__main__":
    main()
