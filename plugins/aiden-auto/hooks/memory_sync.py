#!/usr/bin/env python3
"""
Memory 자동화 Hook — MEMORY.md 인덱스 건강도 검증

SessionEnd 이벤트에서 실행됩니다.
- MEMORY.md 라인 수 초과 감지 (200줄 제한)
- 고아 메모리 파일 (MEMORY.md에 없는 .md) 감지 경고
- 빈 메모리 파일 감지
"""

import json
import os
import sys
from pathlib import Path

MEMORY_DIR = Path(os.path.expanduser("~")) / ".claude" / "projects" / "C--claude" / "memory"
MEMORY_INDEX = MEMORY_DIR / "MEMORY.md"
MAX_LINES = 200


def check_memory_health():
    warnings = []

    if not MEMORY_INDEX.exists():
        return json.dumps({"status": "skip", "message": "MEMORY.md not found"})

    # 1. 라인 수 초과 검사
    lines = MEMORY_INDEX.read_text(encoding="utf-8").splitlines()
    if len(lines) > MAX_LINES:
        warnings.append(
            f"MEMORY.md {len(lines)}줄 (제한 {MAX_LINES}줄 초과). 정리 필요."
        )

    # 2. 인덱스에서 참조된 파일 추출
    referenced = set()
    for line in lines:
        if "](" in line and ".md)" in line:
            start = line.index("](") + 2
            end = line.index(".md)") + 3
            fname = line[start:end]
            referenced.add(fname)

    # 3. 실제 메모리 파일 목록
    actual_files = {
        f.name for f in MEMORY_DIR.glob("*.md") if f.name != "MEMORY.md"
    }

    # 4. 고아 파일 감지 (실제 존재하나 인덱스에 없음)
    orphans = actual_files - referenced
    if orphans:
        warnings.append(
            f"고아 메모리 파일 {len(orphans)}개: {', '.join(sorted(orphans))}"
        )

    # 5. 깨진 참조 감지 (인덱스에 있으나 실제 없음)
    broken = referenced - actual_files
    if broken:
        warnings.append(
            f"깨진 참조 {len(broken)}개: {', '.join(sorted(broken))}"
        )

    # 6. 빈 파일 감지
    empty = []
    for f in MEMORY_DIR.glob("*.md"):
        if f.name == "MEMORY.md":
            continue
        content = f.read_text(encoding="utf-8").strip()
        if len(content) < 10:
            empty.append(f.name)
    if empty:
        warnings.append(f"빈 메모리 파일 {len(empty)}개: {', '.join(empty)}")

    if warnings:
        result = {
            "status": "warn",
            "warnings": warnings,
            "stats": {
                "index_lines": len(lines),
                "referenced": len(referenced),
                "actual_files": len(actual_files),
                "orphans": len(orphans),
                "broken_refs": len(broken),
            },
        }
    else:
        result = {
            "status": "ok",
            "message": f"Memory 건강: {len(actual_files)}개 파일, {len(lines)}줄 인덱스",
        }

    return json.dumps(result, ensure_ascii=False)


if __name__ == "__main__":
    print(check_memory_health())
