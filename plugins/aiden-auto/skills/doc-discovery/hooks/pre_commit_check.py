#!/usr/bin/env python3
"""doc-discovery git pre-commit hook (Layer 0).

Runs `doc_discovery --impact-of` against every staged .md file and
prints a one-line warning per file that would leave external-tier PRDs
stale. NEVER blocks the commit (soft guard) — Layer 0 is awareness, not
enforcement. Layer 1 is enforcement (rule 20).

Exit codes:
    0  always (warnings go to stderr, commit always proceeds)

Wire-up:
    .git/hooks/pre-commit -> python pre_commit_check.py
    Use scripts/install_hooks.py for safe installation.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DOC_DISCOVERY = SKILL_ROOT / "scripts" / "doc_discovery.py"


def _staged_md_files() -> list[str]:
    """Return list of .md files in the current staged diff."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return []
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip().endswith(".md")
    ]


def _check_impact(repo_root: Path, md_path: str) -> tuple[int, str]:
    """Run doc_discovery for one file. Return (exit_code, first_summary_line)."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(DOC_DISCOVERY),
                "--impact-of",
                md_path,
                "--root",
                str(repo_root),
                "--format",
                "text",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root),
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return (0, "")

    if result.returncode == 0:
        return (0, "")

    first_line = ""
    for line in result.stdout.splitlines():
        if line.strip():
            first_line = line.strip()
            break
    return (result.returncode, first_line)


def main() -> int:
    if os.environ.get("DOC_DISCOVERY_HOOK_DISABLE") == "1":
        return 0

    if not DOC_DISCOVERY.exists():
        return 0

    staged = _staged_md_files()
    if not staged:
        return 0

    repo_root = Path.cwd().resolve()

    warnings: list[str] = []
    for md in staged:
        code, summary = _check_impact(repo_root, md)
        if code == 1 and summary:
            warnings.append(f"  - {md}: {summary}")

    if warnings:
        print(
            "[doc-discovery] WARN — the following staged .md files have downstream impact:",
            file=sys.stderr,
        )
        for w in warnings:
            print(w, file=sys.stderr)
        print(
            "  hint: run `python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py "
            "--impact-of <file> --with-rank` for details.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
