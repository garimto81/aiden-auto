#!/usr/bin/env python3
"""doc-discovery PreToolUse hook (Layer 0).

Fires before every Edit / Write tool call. If the target file is a .md
that already exists in the repo, runs `doc_discovery --impact-of` and
emits a one-line warning to stderr when downstream files would go stale.

NEVER blocks the tool call (always exits 0). Layer 0 = awareness, not
gate. Rule 20 is the actual gate.

Wire-up in settings.json:
    "PreToolUse": [{
      "matcher": "Edit|Write|MultiEdit",
      "hooks": [{
        "type": "command",
        "command": "python C:/Users/AidenKim/.claude/skills/doc-discovery/hooks/pretool_md_check.py",
        "timeout": 15
      }]
    }]
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DOC_DISCOVERY = SKILL_ROOT / "scripts" / "doc_discovery.py"


def _read_event() -> dict:
    """Read hook event JSON from stdin (Claude Code hook protocol)."""
    try:
        raw = sys.stdin.read()
    except (OSError, ValueError):
        return {}
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


def _extract_md_target(event: dict) -> Path | None:
    """Pull the .md file path from a PreToolUse event, if applicable."""
    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if not file_path or not isinstance(file_path, str):
        return None
    candidate = Path(file_path)
    if candidate.suffix.lower() != ".md":
        return None
    return candidate


def _find_repo_root(file_path: Path) -> Path | None:
    """Walk up looking for .git. Skip non-repo edits silently."""
    for parent in [file_path.parent] + list(file_path.parent.parents):
        if (parent / ".git").exists():
            return parent
    return None


def _check_impact(repo_root: Path, md_path: Path) -> str:
    """Run doc_discovery and return a one-line summary, or empty string."""
    try:
        rel = str(md_path.resolve().relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return ""

    try:
        result = subprocess.run(
            [
                sys.executable,
                str(DOC_DISCOVERY),
                "--impact-of",
                rel,
                "--root",
                str(repo_root),
                "--format",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(repo_root),
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""

    if result.returncode != 1:
        return ""

    for line in result.stdout.splitlines():
        line = line.strip()
        if line:
            return line
    return ""


def main() -> int:
    if os.environ.get("DOC_DISCOVERY_HOOK_DISABLE") == "1":
        return 0
    if not DOC_DISCOVERY.exists():
        return 0

    event = _read_event()
    md_target = _extract_md_target(event)
    if md_target is None:
        return 0
    if not md_target.exists():
        return 0

    repo_root = _find_repo_root(md_target.resolve())
    if repo_root is None:
        return 0

    summary = _check_impact(repo_root, md_target)
    if summary:
        print(
            f"[doc-discovery] WARN  editing {md_target.name} → {summary}",
            file=sys.stderr,
        )
        print(
            f"  hint: python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py "
            f"--impact-of {md_target.name} --with-rank",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
