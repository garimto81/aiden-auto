#!/usr/bin/env python3
"""Statusline Renderer — CC `statusLine.command` 진입점.

stdin: CC가 제공하는 metadata JSON (model, cwd 등)
stdout: multi-line text (max 5줄)

빠른 응답 필요 (CC가 매 prompt cycle마다 호출). < 50ms 목표.

settings.json 등록:
  "statusLine": {
    "type": "command",
    "command": "python ${CLAUDE_PROJECT_DIR}/plugins/aiden-auto/lib/super/statusline_renderer.py"
  }
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Phase I-6 활성화 시에만 statusline 표시 — env 미설정 시 빈 출력
ENABLED_ENV = "AIDEN_AUTO_STATUSLINE"

# ANSI codes
GRAY = "\033[90m"        # 완료된 step / 미래 step / hud
BRIGHT_CYAN = "\033[1;36m"  # 현재 진행 step (강조)
GREEN = "\033[32m"       # ✓ checkmark
RESET = "\033[0m"


def _enabled() -> bool:
    return os.environ.get(ENABLED_ENV) == "1"


def _read_lines() -> list[dict]:
    try:
        plugin_root = Path(__file__).resolve().parent.parent.parent
        sys.path.insert(0, str(plugin_root / "lib"))
        from super.statusline_state import get_lines_for_render  # noqa: E402
        return get_lines_for_render()
    except Exception:
        return []


def _git_branch(cwd: str | None = None) -> str:
    """git branch 이름만 (있으면)."""
    try:
        r = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=cwd or os.environ.get("CLAUDE_PROJECT_DIR", "."),
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def _short_path(path: str) -> str:
    """경로 단축 — home은 ~, project root 기준 상대 경로 등."""
    try:
        p = Path(path)
        home = str(Path.home()).replace("\\", "/")
        s = str(p).replace("\\", "/")
        if s.startswith(home):
            return "~" + s[len(home):]
        return s
    except Exception:
        return path


def _cc_default_line(stdin_data: str) -> str:
    """CC default statusline 흉내 — model · dir · branch.

    CC가 hook stdin으로 전달하는 metadata 활용:
      {
        "model": {"id": "...", "display_name": "..."},
        "workspace": {"current_dir": "...", "project_dir": "..."},
        "cwd": "...",
        ...
      }
    """
    try:
        data = json.loads(stdin_data) if stdin_data else {}
    except Exception:
        data = {}

    parts: list[str] = []

    # model display name
    model = data.get("model")
    if isinstance(model, dict):
        name = model.get("display_name") or model.get("id", "")
        if name:
            parts.append(str(name))

    # working directory (short)
    cwd = None
    workspace = data.get("workspace")
    if isinstance(workspace, dict):
        cwd = workspace.get("current_dir") or workspace.get("project_dir")
    if not cwd:
        cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR")
    if cwd:
        parts.append(_short_path(cwd))

    # git branch
    branch = _git_branch(cwd)
    if branch:
        parts.append(branch)

    return " · ".join(parts) if parts else ""


def _read_statusline_cmd(settings_path: Path) -> str:
    """settings.json에서 statusLine.command 추출. UTF-8/cp949 fallback.

    self-reference 방지: 우리 renderer 자신을 가리키는 command는 빈 문자열로 반환.
    (global statusline이 우리 renderer로 교체된 경우 무한 루프 차단)
    """
    if not settings_path.exists():
        return ""
    raw_bytes = settings_path.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    for enc in ("utf-8", "cp949", "utf-16"):
        try:
            data = json.loads(raw_bytes.decode(enc))
            sl = data.get("statusLine")
            if not isinstance(sl, dict):
                return ""
            cmd = sl.get("command", "") or ""
            # self-reference 차단 — 우리 renderer 자신은 호출 안 함
            if "statusline_renderer.py" in cmd:
                return ""
            return cmd
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            continue
    return ""


def _run_chain(cmd: str, stdin_data: str, cwd: str | None = None) -> str:
    """chain 명령 실행 — 2초 timeout, silent fallback."""
    try:
        r = subprocess.run(
            cmd,
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=2,  # CC statusline 응답성 보장
            shell=True,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
        )
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.rstrip("\n")
    except Exception:
        pass  # silent fallback
    return ""


def _chained_statusline(stdin_data: str) -> str:
    """기존 사용자 statusLine.command를 chain 호출.

    우선순위 (Phase K — global statusline 지원):
      1. project backup (.claude/settings.json.aiden-backup)
      2. global backup (~/.claude/settings.json.aiden-backup)  ← NEW
      3. project current (.claude/settings.json) — 우리 renderer 자체 제외
      4. global current (~/.claude/settings.json) — 우리 renderer 자체 제외
      5. (없음 — caller가 _cc_default_line으로 fallback)
    """
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    home = Path.home()

    candidates: list[tuple[Path, str | None]] = []
    if project_dir:
        candidates.append((Path(project_dir) / ".claude" / "settings.json.aiden-backup", project_dir))
    candidates.append((home / ".claude" / "settings.json.aiden-backup", project_dir or str(Path.cwd())))
    if project_dir:
        candidates.append((Path(project_dir) / ".claude" / "settings.json", project_dir))
    candidates.append((home / ".claude" / "settings.json", project_dir or str(Path.cwd())))

    for path, cwd in candidates:
        cmd = _read_statusline_cmd(path)
        if not cmd:
            continue
        result = _run_chain(cmd, stdin_data, cwd=cwd)
        if result:
            return result

    return ""


def _supports_color() -> bool:
    """terminal이 ANSI color 지원하는지 추정."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("AIDEN_AUTO_STATUSLINE_NOCOLOR") == "1":
        return False
    # CC는 보통 ANSI 지원
    return True


def _format_active_workflow(line: dict, *, color: bool = True) -> str:
    """Active workflow single-line — all steps with chevron.

    Color:
      - 완료된 step: gray + green ✓
      - 현재 진행 step: bright cyan (강조)
      - 미래 step: gray
    """
    chain = line.get("skill_chain", [])
    current_step = line.get("current_step", 1)
    total = len(chain)
    if total == 0:
        return line.get("summary", "")

    parts = []
    for i, full_id in enumerate(chain, 1):
        name = full_id.split(":", 1)[-1] if ":" in full_id else full_id
        if i < current_step:
            seg = f"{name} ✓"
            parts.append(f"{GRAY}{name}{RESET} {GREEN}✓{RESET}" if color else seg)
        elif i == current_step:
            seg = f"{name} running ({i}/{total})"
            parts.append(f"{BRIGHT_CYAN}{seg}{RESET}" if color else seg)
        else:
            parts.append(f"{GRAY}{name}{RESET}" if color else name)
    sep = f"{GRAY} → {RESET}" if color else " → "
    return sep.join(parts)


def _format_completed_workflow(line: dict) -> str:
    """Completed workflow — shown briefly during TTL."""
    chain = line.get("skill_chain", [])
    name = chain[0].split(":", 1)[-1] if chain else "?"
    elapsed_s = (line.get("elapsed_ms", 0) or 0) / 1000
    icon = "✓" if line.get("status") == "complete" else "✗"
    return f"{name} done ({elapsed_s:.1f}s) {icon}"


def _format_idle() -> str:
    """No active workflow — waiting for user input."""
    return "idle · waiting for input"


def render(stdin_data: str = "") -> str:
    """Render statusline:
      - Line 1 (workflow): active chain / done summary / idle
      - Line 2-N: chained existing statusline (hud) preserved
    """
    base_line = _chained_statusline(stdin_data)
    if not base_line:
        base_line = _cc_default_line(stdin_data)

    if not _enabled():
        return base_line

    lines = _read_lines()
    active = next((l for l in lines if l.get("status") == "running"), None)
    completed = next((l for l in lines if l.get("status") in ("complete", "failed")), None)

    use_color = _supports_color()

    # Always emit a workflow status line (idle if nothing active)
    if active is not None:
        workflow_line = _format_active_workflow(active, color=use_color)
    elif completed is not None:
        base = _format_completed_workflow(completed)
        workflow_line = f"{GRAY}{base}{RESET}" if use_color else base
    else:
        idle_text = _format_idle()
        workflow_line = f"{GRAY}{idle_text}{RESET}" if use_color else idle_text

    if base_line:
        return workflow_line + "\n" + base_line
    return workflow_line


def main() -> int:
    # stdin 보존 — chain 호출에 사용 (CC metadata를 기존 statusline에 전달)
    try:
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    try:
        stdin_data = sys.stdin.read()
    except Exception:
        stdin_data = ""

    try:
        text = render(stdin_data)
    except Exception:
        text = ""

    if text:
        # CRLF 방지 — Windows에서 print()가 \n → \r\n 자동 변환하면 CC multi-line 파싱 깨짐
        # binary mode write로 raw \n 보장
        try:
            data = text.rstrip("\r\n").encode("utf-8") + b"\n"
            sys.stdout.flush()
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except Exception:
            # fallback
            sys.stdout.write(text.rstrip("\r\n") + "\n")
            sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
