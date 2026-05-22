#!/usr/bin/env python3
"""doc-discovery Layer 0 hook installer (idempotent).

Installs:
  1. Git pre-commit hook chain into <repo>/.git/hooks/pre-commit
  2. PreToolUse Edit/Write hook into ~/.claude/settings.json

Both operations are safe to re-run. Existing hooks are preserved via
chaining (pre-commit) or matcher dedup (settings.json).

Usage:
    python install_hooks.py [--repo PATH] [--user-settings PATH] [--dry-run]
    python install_hooks.py --uninstall

Exit codes:
    0  success or no-op
    1  recoverable error (already installed in unsafe form)
    2  fatal error (cannot read/write settings)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
PRE_COMMIT_HOOK = SKILL_ROOT / "hooks" / "pre_commit_check.py"
PRETOOL_HOOK = SKILL_ROOT / "hooks" / "pretool_md_check.py"

MARKER = "# doc-discovery-layer0"
PRECOMMIT_TEMPLATE = f"""#!/bin/sh
{MARKER}
# Auto-installed by ~/.claude/skills/doc-discovery/scripts/install_hooks.py
# Soft guard: warns about downstream impact, never blocks the commit.
python "{PRE_COMMIT_HOOK.as_posix()}" || true
"""

DEFAULT_USER_SETTINGS = Path.home() / ".claude" / "settings.json"


def _install_git_hook(repo_root: Path, dry_run: bool) -> tuple[bool, str]:
    git_dir = repo_root / ".git"
    if not git_dir.exists():
        return (False, f"skip — {repo_root} is not a git repo")

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    target = hooks_dir / "pre-commit"

    if target.exists():
        existing = target.read_text(encoding="utf-8", errors="ignore")
        if MARKER in existing:
            return (True, f"already installed: {target}")
        if dry_run:
            return (
                False,
                f"would refuse: {target} already exists (manual chain required)",
            )
        return (
            False,
            f"refuse — {target} already exists. Manual chain required "
            f"(append: python \"{PRE_COMMIT_HOOK.as_posix()}\" || true)",
        )

    if dry_run:
        return (True, f"would create: {target}")
    target.write_text(PRECOMMIT_TEMPLATE, encoding="utf-8", newline="\n")
    try:
        target.chmod(0o755)
    except (OSError, NotImplementedError):
        pass
    return (True, f"created: {target}")


def _uninstall_git_hook(repo_root: Path, dry_run: bool) -> tuple[bool, str]:
    target = repo_root / ".git" / "hooks" / "pre-commit"
    if not target.exists():
        return (True, "not installed")
    existing = target.read_text(encoding="utf-8", errors="ignore")
    if MARKER not in existing:
        return (False, f"refuse — {target} is not ours (no marker)")
    if dry_run:
        return (True, f"would remove: {target}")
    target.unlink()
    return (True, f"removed: {target}")


def _load_settings(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"ERROR  cannot parse {path}: {exc}")


def _save_settings(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _install_pretool_hook(settings_path: Path, dry_run: bool) -> tuple[bool, str]:
    settings = _load_settings(settings_path)
    hooks = settings.setdefault("hooks", {})
    pretool = hooks.setdefault("PreToolUse", [])

    desired_command = (
        f'python "{PRETOOL_HOOK.as_posix()}"'
    )
    desired_matcher = "Edit|Write|MultiEdit"

    for entry in pretool:
        if entry.get("matcher") != desired_matcher:
            continue
        for h in entry.get("hooks", []):
            if h.get("command") == desired_command:
                return (True, "already installed in user settings")

    new_entry = {
        "matcher": desired_matcher,
        "hooks": [
            {
                "type": "command",
                "command": desired_command,
                "timeout": 15,
            }
        ],
    }
    pretool.append(new_entry)

    if dry_run:
        return (True, f"would update: {settings_path}")
    _save_settings(settings_path, settings)
    return (True, f"updated: {settings_path}")


def _uninstall_pretool_hook(settings_path: Path, dry_run: bool) -> tuple[bool, str]:
    if not settings_path.exists():
        return (True, "settings file not found, nothing to do")

    settings = _load_settings(settings_path)
    hooks = settings.get("hooks", {})
    pretool = hooks.get("PreToolUse", [])

    needle = PRETOOL_HOOK.as_posix()
    new_pretool = []
    removed = 0
    for entry in pretool:
        kept_hooks = [h for h in entry.get("hooks", []) if needle not in h.get("command", "")]
        if not kept_hooks:
            removed += 1
            continue
        if len(kept_hooks) != len(entry.get("hooks", [])):
            removed += 1
        new_entry = dict(entry)
        new_entry["hooks"] = kept_hooks
        new_pretool.append(new_entry)

    if removed == 0:
        return (True, "not installed in user settings")

    if dry_run:
        return (True, f"would remove {removed} entry from {settings_path}")
    hooks["PreToolUse"] = new_pretool
    settings["hooks"] = hooks
    _save_settings(settings_path, settings)
    return (True, f"removed {removed} entry from {settings_path}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="install_hooks.py")
    p.add_argument("--repo", default=".", help="git repo path (default: cwd)")
    p.add_argument(
        "--user-settings",
        default=str(DEFAULT_USER_SETTINGS),
        help=f"user settings.json (default: {DEFAULT_USER_SETTINGS})",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument(
        "--skip-git", action="store_true", help="skip git pre-commit setup"
    )
    p.add_argument(
        "--skip-pretool", action="store_true", help="skip user settings PreToolUse setup"
    )
    args = p.parse_args(argv)

    repo_root = Path(args.repo).resolve()
    settings_path = Path(args.user_settings).resolve()

    print(f"doc-discovery Layer 0 installer ({'uninstall' if args.uninstall else 'install'})")
    print(f"  repo:      {repo_root}")
    print(f"  settings:  {settings_path}")
    print(f"  dry-run:   {args.dry_run}")
    print()

    rc = 0

    if not args.skip_git:
        op = _uninstall_git_hook if args.uninstall else _install_git_hook
        ok, msg = op(repo_root, args.dry_run)
        prefix = "OK   " if ok else "WARN "
        print(f"  [git pre-commit] {prefix}{msg}")
        if not ok:
            rc = max(rc, 1)

    if not args.skip_pretool:
        op = _uninstall_pretool_hook if args.uninstall else _install_pretool_hook
        ok, msg = op(settings_path, args.dry_run)
        prefix = "OK   " if ok else "WARN "
        print(f"  [pretool hook]   {prefix}{msg}")
        if not ok:
            rc = max(rc, 1)

    return rc


if __name__ == "__main__":
    sys.exit(main())
