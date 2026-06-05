#!/usr/bin/env python3
"""doc-discovery git pre-commit hook (Layer 0) — skill/doc freshness gate.

For every staged .md file, runs `doc_discovery --impact-of` and warns about
the impacted *paired* files (downstream docs/skills/code) that were LEFT
UNTOUCHED in this same commit — i.e. you edited a source but did not update
its derivatives. Files you DID stage alongside are treated as the paired
update and produce no warning.

This is the "paired-update gate" (skill-freshness = system-freshness): the
2026-06 Anthropic self-service-analytics write-up reported offline accuracy
drifting 95%->65% in one month when skill/doc updates lagged model changes;
their fix flags any model change shipped without its paired skill update.
Earlier versions of this hook warned on ALL downstream impact regardless of
whether the derivatives were also updated (pure detection + alert fatigue);
this version warns only on the genuinely-untouched paired files.

NEVER blocks the commit (soft guard) — Layer 0 is awareness, not enforcement.
If impact analysis is unavailable for a file (graph miss, parse failure), it
degrades silently to no warning — strictly never noisier-on-failure than the
old behavior. Layer 1 is enforcement (rule 20).

Exit codes:
    0  always (warnings go to stderr, commit always proceeds)

Wire-up:
    .git/hooks/pre-commit -> python pre_commit_check.py
    Use scripts/install_hooks.py for safe installation.
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

# Cap how many untouched paired files we list per source, to avoid flooding
# stderr for hub documents with large fan-out (e.g. CLAUDE.md).
_MAX_LISTED = 8


def _norm(path: str) -> str:
    """Normalize a repo-relative path for set membership (POSIX, no leading ./)."""
    p = (path or "").strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    return p


def _staged_files() -> list[str]:
    """Return ALL files in the current staged diff (not just .md), POSIX-relative.

    The full staged set is needed so we can tell whether an impacted paired
    file was *also* updated in this commit (paired update) or left untouched.
    """
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
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _impacted_files(repo_root: Path, md_path: str) -> list[str] | None:
    """Return repo-relative paths impacted by md_path, or None if unavailable.

    None signals "could not analyze" (subprocess/parse failure) -> caller skips
    silently. [] signals "analyzed, no impact". Both produce no warning.
    """
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
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(repo_root),
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

    try:
        data = json.loads(result.stdout)
    except (ValueError, json.JSONDecodeError):
        return None

    if not isinstance(data, dict) or not data.get("exists"):
        return []

    impacted: list[str] = list(data.get("direct") or [])
    transitive = data.get("transitive") or {}
    if isinstance(transitive, dict):
        for depth_list in transitive.values():
            if isinstance(depth_list, list):
                impacted.extend(depth_list)
    return impacted


def main() -> int:
    if os.environ.get("DOC_DISCOVERY_HOOK_DISABLE") == "1":
        return 0

    if not DOC_DISCOVERY.exists():
        return 0

    staged_all = _staged_files()
    staged_md = [f for f in staged_all if f.endswith(".md")]
    if not staged_md:
        return 0

    repo_root = Path.cwd().resolve()
    staged_set = {_norm(f) for f in staged_all}

    warnings: list[str] = []
    for md in staged_md:
        impacted = _impacted_files(repo_root, md)
        if not impacted:
            continue
        untouched = [f for f in impacted if _norm(f) not in staged_set]
        if not untouched:
            continue  # all derivatives updated in same commit -> paired update done
        shown = untouched[:_MAX_LISTED]
        more = len(untouched) - len(shown)
        tail = f" (+{more} more)" if more > 0 else ""
        warnings.append(
            f"  - {md}: {len(untouched)} paired file(s) NOT updated here: "
            + ", ".join(shown)
            + tail
        )

    if warnings:
        print(
            "[doc-discovery] WARN — edited source(s) whose paired derivatives "
            "were left untouched in this commit:",
            file=sys.stderr,
        )
        for w in warnings:
            print(w, file=sys.stderr)
        print(
            "  (skill-freshness gate: update the paired doc/skill in the same "
            "commit, or confirm it is intentionally unchanged)",
            file=sys.stderr,
        )
        print(
            "  hint: run `python ~/.claude/skills/doc-discovery/scripts/doc_discovery.py "
            "--impact-of <file> --with-rank` for details.",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
