#!/usr/bin/env python3
"""
Claude Code Context Monitor
Real-time context usage monitoring with visual indicators and session analytics
"""

import json
import sys
import os
import re
import io

# Windows UTF-8 출력 설정
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path
import subprocess


def get_claude_version():
    """Get Claude Code version"""
    try:
        # Windows에서 claude.cmd 실행을 위해 shell=True 필요
        result = subprocess.run(
            "claude --version", capture_output=True, text=True, timeout=5, shell=True
        )
        if result.returncode == 0:
            # 출력에서 버전 추출 (예: "2.1.2 (Claude Code)" -> "2.1.2")
            parts = result.stdout.strip().split()
            return parts[0] if parts else "?"
        return "?"
    except Exception:
        return "?"


def find_git_dir(project_dir):
    """Find .git directory by traversing up the directory tree (monorepo support)."""
    try:
        # Normalize path for Windows (convert /d/path to D:/path)
        if sys.platform == "win32" and project_dir.startswith("/"):
            parts = project_dir.split("/")
            if len(parts) > 1 and len(parts[1]) == 1:  # /d/... format
                project_dir = f"{parts[1].upper()}:/{'/'.join(parts[2:])}"

        current = Path(project_dir).resolve()
        # Traverse up to find .git directory
        while current != current.parent:
            git_dir = current / ".git"
            if git_dir.exists():
                return git_dir
            current = current.parent
        # Check root as well
        git_dir = current / ".git"
        if git_dir.exists():
            return git_dir
        return None
    except Exception:
        return None


def get_git_remote(project_dir):
    """Get GitHub remote repository (repo only, without owner)"""
    try:
        git_dir = find_git_dir(project_dir)
        if git_dir:
            config_file = git_dir / "config"
            if config_file.exists():
                content = config_file.read_text(encoding="utf-8")
                lines = content.split("\n")
                in_remote_origin = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == '[remote "origin"]':
                        in_remote_origin = True
                        continue
                    if in_remote_origin and stripped.startswith("["):
                        break
                    if in_remote_origin and stripped.startswith("url = "):
                        url = stripped.split("url = ", 1)[1].strip()
                        if "github.com" in url:
                            repo = url.split("github.com")[1]
                            repo = repo.replace(":", "/").replace(".git", "").strip("/")
                            # Return only repo name (remove owner)
                            if "/" in repo:
                                return repo.split("/")[-1]
                            return repo
        return ""
    except Exception:
        return ""


def get_git_branch(project_dir):
    """Get current git branch name"""
    try:
        git_dir = find_git_dir(project_dir)
        if git_dir:
            head_file = git_dir / "HEAD"
            if head_file.exists():
                content = head_file.read_text(encoding="utf-8").strip()
                if content.startswith("ref: refs/heads/"):
                    return content.replace("ref: refs/heads/", "")
                # Detached HEAD - return short hash
                return content[:7]
        return ""
    except Exception:
        return ""


def parse_context_from_json(data):
    """Parse context usage directly from Claude Code JSON input (primary method)."""
    try:
        context_window = data.get("context_window", {})
        if not context_window:
            return None

        window_size = context_window.get("context_window_size", 200000)
        current_usage = context_window.get("current_usage", {})

        if not current_usage:
            return None

        input_tokens = current_usage.get("input_tokens", 0)
        cache_read = current_usage.get("cache_read_input_tokens", 0)
        cache_creation = current_usage.get("cache_creation_input_tokens", 0)

        total_tokens = input_tokens + cache_read + cache_creation
        if total_tokens > 0:
            percent_used = min(100, (total_tokens / window_size) * 100)
            return {
                "percent": percent_used,
                "tokens": total_tokens,
                "window_size": window_size,
                "method": "context_window",
            }

        return None
    except Exception:
        return None


def parse_context_from_transcript(transcript_path):
    """Parse context usage from transcript file (fallback method)."""
    if not transcript_path or not os.path.exists(transcript_path):
        return None

    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        # Check last 15 lines for context information
        recent_lines = lines[-15:] if len(lines) > 15 else lines

        for line in reversed(recent_lines):
            try:
                data = json.loads(line.strip())

                # Method 1: Parse usage tokens from assistant messages
                if data.get("type") == "assistant":
                    message = data.get("message", {})
                    usage = message.get("usage", {})

                    if usage:
                        input_tokens = usage.get("input_tokens", 0)
                        cache_read = usage.get("cache_read_input_tokens", 0)
                        cache_creation = usage.get("cache_creation_input_tokens", 0)

                        # Estimate context usage (assume 200k context for Claude Sonnet)
                        total_tokens = input_tokens + cache_read + cache_creation
                        if total_tokens > 0:
                            percent_used = min(100, (total_tokens / 200000) * 100)
                            return {
                                "percent": percent_used,
                                "tokens": total_tokens,
                                "method": "usage",
                            }

                # Method 2: Parse system context warnings
                elif data.get("type") == "system_message":
                    content = data.get("content", "")

                    # "Context left until auto-compact: X%"
                    match = re.search(
                        r"Context left until auto-compact: (\d+)%", content
                    )
                    if match:
                        percent_left = int(match.group(1))
                        return {
                            "percent": 100 - percent_left,
                            "warning": "auto-compact",
                            "method": "system",
                        }

                    # "Context low (X% remaining)"
                    match = re.search(r"Context low \((\d+)% remaining\)", content)
                    if match:
                        percent_left = int(match.group(1))
                        return {
                            "percent": 100 - percent_left,
                            "warning": "low",
                            "method": "system",
                        }

            except (json.JSONDecodeError, KeyError, ValueError):
                continue

        return None

    except (FileNotFoundError, PermissionError):
        return None


def get_context_display(context_info):
    """Generate context display with progress bar only (no icons)."""
    if not context_info:
        return "\033[90m▁▁▁▁▁▁▁▁\033[0m ???"

    percent = context_info.get("percent", 0)

    # Context usage thresholds (conservative - warnings start at 80%)
    if percent >= 95:
        color = "\033[31;1m"  # Red - Critical (95-100%)
    elif percent >= 90:
        color = "\033[91m"  # Orange - Warning (90-95%)
    elif percent >= 80:
        color = "\033[33m"  # Yellow - Caution (80-90%)
    else:
        color = "\033[32m"  # Green - Safe (0-80%)

    # Create progress bar
    segments = 8
    filled = int((percent / 100) * segments)
    bar = "█" * filled + "▁" * (segments - filled)

    reset = "\033[0m"

    return f"{color}{bar}{reset} {percent:.0f}%"


def get_directory_display(workspace_data):
    """Get directory display name."""
    current_dir = workspace_data.get("current_dir", "")
    project_dir = workspace_data.get("project_dir", "")

    if current_dir and project_dir:
        if current_dir.startswith(project_dir):
            rel_path = current_dir[len(project_dir) :].lstrip("/")
            return rel_path or os.path.basename(project_dir)
        else:
            return os.path.basename(current_dir)
    elif project_dir:
        return os.path.basename(project_dir)
    elif current_dir:
        return os.path.basename(current_dir)
    else:
        return "unknown"


def main():
    try:
        # Read JSON input from Claude Code
        data = json.load(sys.stdin)

        # Extract information
        workspace = data.get("workspace", {})
        transcript_path = data.get("transcript_path", "")
        project_dir = workspace.get("project_dir", os.getcwd())

        # Parse context usage (priority: context_window > transcript)
        context_info = parse_context_from_json(data)
        if not context_info:
            context_info = parse_context_from_transcript(transcript_path)

        # Build status components
        context_display = get_context_display(context_info)
        version = get_claude_version()
        git_remote = get_git_remote(project_dir)
        git_branch = get_git_branch(project_dir)

        # GitHub remote display (no icon)
        github_display = f"  \033[36m{git_remote}\033[0m" if git_remote else ""

        # Git branch display (no icon)
        branch_display = f"  \033[35m{git_branch}\033[0m" if git_branch else ""

        # Combine all components (version instead of directory, no icons)
        status_line = f"\033[93m{version}\033[0m{github_display}{branch_display}  {context_display}"

        print(status_line)

    except Exception as e:
        # Fallback display on any error
        print(f"\033[93m?\033[0m \033[31m[Error: {str(e)[:20]}]\033[0m")


if __name__ == "__main__":
    main()
