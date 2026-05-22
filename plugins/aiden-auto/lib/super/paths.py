"""Cross-platform path resolution helpers for aiden-auto plugin.

SSOT for project/plugin/home root detection. All hooks and scripts that need
to know "where is the repo root?" should call `find_project_root()` instead
of hardcoding paths like `Path("C:/claude")`.

Design:
  - find_project_root(): 4-stage fallback chain
      1. CLAUDE_PROJECT_DIR env var (set by Claude Code)
      2. `git rev-parse --show-toplevel` from cwd
      3. Walk up from plugin_root looking for .git
      4. cwd as last resort
  - find_plugin_root(): always derives from __file__ (PC-independent)
  - find_user_home(): Path.home() (cross-platform)
  - create_directory_link(): symlink with Windows junction fallback

Debug:
  - Set AIDEN_AUTO_DEBUG_PATHS=1 to log resolution to stderr
  - Each call cached per-process for consistency

Public API:
  find_project_root() -> Path
  find_plugin_root() -> Path
  find_user_home() -> Path
  can_create_symlink(target_dir: Path) -> bool
  create_directory_link(src: Path, dst: Path) -> tuple[bool, str]
"""
from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path


_DEBUG = os.environ.get("AIDEN_AUTO_DEBUG_PATHS") == "1"


def _log(msg: str) -> None:
    if _DEBUG:
        sys.stderr.write(f"[paths] {msg}\n")


@lru_cache(maxsize=1)
def find_plugin_root() -> Path:
    """Return plugins/aiden-auto/ regardless of installation location.

    This file is at plugins/aiden-auto/lib/super/paths.py, so parents[2]
    is the plugin root.
    """
    root = Path(__file__).resolve().parents[2]
    _log(f"plugin_root={root}")
    return root


@lru_cache(maxsize=1)
def find_user_home() -> Path:
    """Cross-platform user home directory."""
    home = Path.home()
    _log(f"user_home={home}")
    return home


def _try_env_root() -> Path | None:
    val = os.environ.get("CLAUDE_PROJECT_DIR")
    if not val:
        return None
    p = Path(val)
    if p.exists() and p.is_dir():
        return p.resolve()
    return None


def _try_git_root(cwd: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            p = Path(result.stdout.strip())
            if p.exists():
                return p.resolve()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None


def _try_walkup_for_git(start: Path, max_depth: int = 6) -> Path | None:
    cur = start.resolve()
    for _ in range(max_depth):
        if (cur / ".git").exists():
            return cur
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


@lru_cache(maxsize=1)
def find_project_root() -> Path:
    """Detect repository root via 4-stage fallback chain.

    Order:
        1. CLAUDE_PROJECT_DIR env var (Claude Code sets this)
        2. git rev-parse --show-toplevel (from cwd)
        3. Walk up from plugin_root searching for .git
        4. cwd (last resort)

    Cached per-process — first call result wins.
    """
    # Stage 1: env var
    p = _try_env_root()
    if p:
        _log(f"root={p} via=env")
        return p

    # Stage 2: git from cwd
    cwd = Path(os.getcwd())
    p = _try_git_root(cwd)
    if p:
        _log(f"root={p} via=git")
        return p

    # Stage 3: walk up from plugin root
    p = _try_walkup_for_git(find_plugin_root())
    if p:
        _log(f"root={p} via=walkup")
        return p

    # Stage 4: cwd
    _log(f"root={cwd} via=cwd")
    return cwd


@lru_cache(maxsize=1)
def find_python_executable() -> str:
    """Cross-platform Python interpreter detection.

    Returns absolute path to a working python interpreter. Used by hooks/
    statusline command resolution so settings.json `command` strings work
    regardless of `python` vs `python3` PATH availability.

    Detection order:
        1. sys.executable — current process interpreter (most reliable)
        2. shutil.which("python") — Windows-friendly default
        3. shutil.which("python3") — Linux/macOS standard
        4. "python" string fallback (defer to OS PATH resolution)

    Why this matters:
        - Windows: `python3.exe` in PATH is often the Microsoft Store stub
          (exits 49 with non-blocking error). Use `python.exe` instead.
        - macOS 13+: `python` is alias for python3 (after Apple removed python2).
        - Linux: `python3` standard, `python` may be missing or python2.
        Returning sys.executable from a known-good Python process avoids all
        the above ambiguities.
    """
    import shutil
    # Stage 1: current interpreter (always works inside a Python process)
    if sys.executable and Path(sys.executable).exists():
        _log(f"python_executable={sys.executable} via=sys.executable")
        return sys.executable
    # Stage 2-3: PATH search
    for candidate in ("python", "python3"):
        path = shutil.which(candidate)
        if path:
            _log(f"python_executable={path} via=which({candidate})")
            return path
    # Stage 4: bare name fallback
    _log("python_executable=python via=fallback")
    return "python"


def can_create_symlink(target_dir: Path) -> bool:
    """Check if symlinks can be created in target_dir.

    On POSIX: always True (assuming write permission).
    On Windows: requires Developer Mode or admin. Tests by creating a
    throwaway symlink.
    """
    if os.name != "nt":
        return True
    if not target_dir.exists() or not target_dir.is_dir():
        return False
    test_link = target_dir / f".__aiden_symlink_test_{os.getpid()}"
    test_target = target_dir
    try:
        os.symlink(str(test_target), str(test_link), target_is_directory=True)
        test_link.unlink()
        return True
    except (OSError, NotImplementedError):
        return False


def create_directory_link(src: Path, dst: Path) -> tuple[bool, str]:
    """Create a directory link from `dst` pointing to `src`.

    Strategy:
        1. Try os.symlink (works on Mac/Linux/Windows-DevMode)
        2. On Windows fallback: cmd.exe mklink /J (junction)
        3. On failure: graceful return with reason

    Returns:
        (success, message) — success=True on link creation, False otherwise.
        message is human-readable status / reason.
    """
    src = src.resolve()
    if not src.exists() or not src.is_dir():
        return False, f"source dir missing: {src}"
    if dst.exists():
        return False, f"destination exists: {dst}"

    # Stage 1: native symlink (cross-platform)
    try:
        os.symlink(str(src), str(dst), target_is_directory=True)
        if dst.exists():
            return True, f"symlink created: {dst} -> {src}"
    except (OSError, NotImplementedError) as e:
        symlink_err = str(e)
    else:
        symlink_err = "unknown"

    # Stage 2: Windows junction fallback
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["cmd.exe", "/c", "mklink", "/J", str(dst), str(src)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0 and dst.exists():
                return True, f"junction created: {dst} -> {src}"
            return False, f"junction failed: {result.stderr.strip()[:100]}"
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            return False, f"junction error: {e}"

    return False, f"symlink failed: {symlink_err}"


def report_environment() -> dict:
    """Return cross-platform environment snapshot for debug/audit."""
    return {
        "os": sys.platform,
        "os_name": os.name,
        "python": sys.version.split()[0],
        "python_executable": find_python_executable(),
        "project_root": str(find_project_root()),
        "plugin_root": str(find_plugin_root()),
        "user_home": str(find_user_home()),
        "cwd": os.getcwd(),
        "claude_project_dir_env": os.environ.get("CLAUDE_PROJECT_DIR", ""),
    }


if __name__ == "__main__":
    import json
    print(json.dumps(report_environment(), indent=2, ensure_ascii=False))
