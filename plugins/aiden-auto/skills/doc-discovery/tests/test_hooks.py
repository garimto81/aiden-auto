"""Layer 0 hook regression tests (Week 4-5).

Covers:
  1. pre_commit_check.py — staged .md detection + impact warning
  2. pretool_md_check.py — JSON event parsing + .md filter + non-existent skip
  3. install_hooks.py — idempotent install + clean uninstall
  4. /auto Phase 0 dry-run helper

Hooks must be soft (exit 0) and must never crash on malformed input.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
HOOK_DIR = SKILL_ROOT / "hooks"
SCRIPTS_DIR = SKILL_ROOT / "scripts"

PRE_COMMIT = HOOK_DIR / "pre_commit_check.py"
PRETOOL = HOOK_DIR / "pretool_md_check.py"
INSTALLER = SCRIPTS_DIR / "install_hooks.py"


# -- helpers ----------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git in the given repo with deterministic identity."""
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_CONFIG_GLOBAL": "/dev/null",
    }
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


def _setup_repo(tmp: Path) -> Path:
    """Create a tiny git repo whose docs live under a corpus path
    that doc_discovery actually scans (docs/00-prd/)."""
    repo = tmp / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "test")

    prd_dir = repo / "docs" / "00-prd"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "Overview.md").write_text(
        "---\ntitle: Overview\n---\n\nRoot doc.\n", encoding="utf-8"
    )
    (prd_dir / "Derived.md").write_text(
        "---\ntitle: Derived\nderivative-of: Overview.md\n---\n\nDerived.\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "init")
    return repo


# -- pre_commit_check.py ----------------------------------------------------


def test_pre_commit_silent_on_no_staged_md():
    with tempfile.TemporaryDirectory() as td:
        repo = _setup_repo(Path(td))
        # nothing staged
        result = subprocess.run(
            [sys.executable, str(PRE_COMMIT)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert result.stderr.strip() == ""


def test_pre_commit_warns_when_overview_changes():
    with tempfile.TemporaryDirectory() as td:
        repo = _setup_repo(Path(td))
        overview = repo / "docs" / "00-prd" / "Overview.md"
        overview.write_text(overview.read_text() + "\nMore content.\n", encoding="utf-8")
        _git(repo, "add", "docs/00-prd/Overview.md")

        result = subprocess.run(
            [sys.executable, str(PRE_COMMIT)],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=30,
        )
        # MUST exit 0 (soft guard) — never blocks the commit
        assert result.returncode == 0
        # MUST emit a warning to stderr about the impact
        assert "doc-discovery" in result.stderr
        assert "Overview.md" in result.stderr


def test_pre_commit_handles_missing_doc_discovery_gracefully(tmp_path, monkeypatch):
    """Even if the underlying CLI is broken, never block a commit."""
    # Run with DOC_DISCOVERY_HOOK_DISABLE=1 — must short-circuit
    repo = _setup_repo(tmp_path)
    env = {**os.environ, "DOC_DISCOVERY_HOOK_DISABLE": "1"}
    result = subprocess.run(
        [sys.executable, str(PRE_COMMIT)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stderr == ""


# -- pretool_md_check.py ----------------------------------------------------


def _run_pretool(event: dict, cwd: Path | None = None) -> subprocess.CompletedProcess:
    payload = json.dumps(event)
    return subprocess.run(
        [sys.executable, str(PRETOOL)],
        input=payload,
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
        timeout=20,
    )


def test_pretool_silent_on_non_md_file(tmp_path):
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(tmp_path / "not_md.py")},
    }
    result = _run_pretool(event)
    assert result.returncode == 0
    assert result.stderr == ""


def test_pretool_silent_on_empty_event():
    result = _run_pretool({})
    assert result.returncode == 0
    assert result.stderr == ""


def test_pretool_silent_on_malformed_event():
    """Non-JSON stdin must not crash."""
    result = subprocess.run(
        [sys.executable, str(PRETOOL)],
        input="this is not json {{{",
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_pretool_warns_when_overview_edited():
    with tempfile.TemporaryDirectory() as td:
        repo = _setup_repo(Path(td))
        overview = repo / "docs" / "00-prd" / "Overview.md"
        event = {
            "tool_name": "Edit",
            "tool_input": {"file_path": str(overview)},
        }
        result = _run_pretool(event, cwd=repo)
        assert result.returncode == 0
        assert "doc-discovery" in result.stderr
        assert "Overview.md" in result.stderr


def test_pretool_silent_on_md_outside_repo(tmp_path):
    """File exists but isn't inside a git repo — skip silently."""
    md = tmp_path / "loose.md"
    md.write_text("---\ntitle: x\n---\n", encoding="utf-8")
    event = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(md)},
    }
    result = _run_pretool(event)
    assert result.returncode == 0
    assert result.stderr == ""


# -- install_hooks.py -------------------------------------------------------


def test_installer_creates_pre_commit_hook(tmp_path):
    repo = tmp_path / "fresh"
    repo.mkdir()
    (repo / ".git").mkdir()  # minimal git repo for hook installation
    settings = tmp_path / "settings.json"

    result = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--repo",
            str(repo),
            "--user-settings",
            str(settings),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0
    hook = repo / ".git" / "hooks" / "pre-commit"
    assert hook.exists()
    body = hook.read_text(encoding="utf-8")
    assert "doc-discovery-layer0" in body

    # idempotent — second run is no-op
    result2 = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--repo",
            str(repo),
            "--user-settings",
            str(settings),
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result2.returncode == 0
    assert "already installed" in result2.stdout


def test_installer_refuses_to_overwrite_foreign_hook(tmp_path):
    repo = tmp_path / "occupied"
    repo.mkdir()
    (repo / ".git" / "hooks").mkdir(parents=True)
    target = repo / ".git" / "hooks" / "pre-commit"
    target.write_text("#!/bin/sh\necho user hook\n", encoding="utf-8")
    settings = tmp_path / "settings.json"

    result = subprocess.run(
        [
            sys.executable,
            str(INSTALLER),
            "--repo",
            str(repo),
            "--user-settings",
            str(settings),
            "--skip-pretool",
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 1  # WARN exit
    assert "refuse" in result.stdout.lower() or "manual chain" in result.stdout.lower()
    # original hook untouched
    assert "user hook" in target.read_text()


def test_installer_pretool_idempotent(tmp_path):
    settings = tmp_path / "settings.json"
    repo = tmp_path / "norepo"
    repo.mkdir()  # no .git on purpose — git step skips, pretool still runs

    common = [
        sys.executable, str(INSTALLER),
        "--repo", str(repo),
        "--user-settings", str(settings),
    ]
    r1 = subprocess.run(common, capture_output=True, text=True, timeout=20)
    r2 = subprocess.run(common, capture_output=True, text=True, timeout=20)
    assert r1.returncode in (0, 1)  # git step warns, pretool succeeds
    assert "updated" in r1.stdout
    assert "already installed" in r2.stdout

    # only one entry created
    data = json.loads(settings.read_text(encoding="utf-8"))
    matches = [
        e for e in data.get("hooks", {}).get("PreToolUse", [])
        if "pretool_md_check.py" in str(e)
    ]
    assert len(matches) == 1


def test_installer_uninstall_cleans_both_sides(tmp_path):
    repo = tmp_path / "full"
    repo.mkdir()
    (repo / ".git").mkdir()
    settings = tmp_path / "settings.json"

    install_args = [
        sys.executable, str(INSTALLER),
        "--repo", str(repo),
        "--user-settings", str(settings),
    ]
    subprocess.run(install_args, capture_output=True, text=True, timeout=20)
    assert (repo / ".git" / "hooks" / "pre-commit").exists()

    uninstall = subprocess.run(
        install_args + ["--uninstall"],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert uninstall.returncode == 0
    assert not (repo / ".git" / "hooks" / "pre-commit").exists()

    data = json.loads(settings.read_text(encoding="utf-8"))
    leftover = [
        e for entry in data.get("hooks", {}).get("PreToolUse", [])
        for e in entry.get("hooks", []) if "pretool_md_check.py" in e.get("command", "")
    ]
    assert leftover == []
