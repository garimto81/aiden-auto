#!/usr/bin/env python3
"""team_commit_msg.py — /team Phase 6: Conventional commit 메시지 자동 생성.

Usage:
  python team_commit_msg.py --task "<task>" --team TEAM_ID [--notify TEAM_ID]

Output: stdout 에 완성 메시지 (Co-Authored-By 포함).

Inference 규칙:
  feat   — 추가/신규/구현/implement/add
  fix    — 수정/버그/오류/fix
  docs   — 문서/doc
  refactor — 리팩터링/정리/refactor
  test   — 테스트/test
  chore  — 그 외
"""
from __future__ import annotations

import argparse
import sys


KW_MAP = [
    ("feat", ["추가", "신규", "구현", "add", "implement", "introduce", "create"]),
    ("fix", ["수정", "버그", "오류", "fix", "bug", "error", "해소"]),
    ("docs", ["문서", "doc", "기획", "readme", "comment"]),
    ("refactor", ["리팩", "정리", "refactor", "cleanup", "재구성", "이관"]),
    ("test", ["테스트", "test", "spec", "coverage"]),
]


def infer_prefix(task: str) -> str:
    lower = task.lower()
    for prefix, keywords in KW_MAP:
        if any(k in lower for k in keywords):
            return prefix
    return "chore"


def build_message(task: str, team: str | None, notify: str | None) -> str:
    prefix = infer_prefix(task)
    scope = team or "conductor"
    short = task.strip()[:72]
    if len(task) > 72:
        short = short.rstrip() + "..."

    header = f"{prefix}({scope}): {short}"

    body_lines = []
    if notify:
        body_lines.append(f"notify: {notify}")
    body_lines.append(
        "Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
    )

    body = "\n\n" + "\n".join(body_lines) if body_lines else ""
    return header + body


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True)
    ap.add_argument("--team", default=None)
    ap.add_argument("--notify", default=None)
    args = ap.parse_args()

    msg = build_message(args.task, args.team, args.notify)
    print(msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
