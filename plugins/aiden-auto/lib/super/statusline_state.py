"""Statusline State — line buffer FIFO (push/update/complete/pop) API.

상태 파일: aiden-auto/state/statusline.json
  - max 5 line (active 1 + history 4)
  - completed line은 history_ttl(30s) 후 자동 pop

atomic write: tempfile + rename (lock 없이 동시성 안전).
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent  # plugins/aiden-auto
STATE_DIR = PLUGIN_ROOT / "state"
STATE_PATH = STATE_DIR / "statusline.json"

MAX_LINES = 5
HISTORY_TTL_SECONDS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"lines": [], "max_lines": MAX_LINES, "history_ttl_seconds": HISTORY_TTL_SECONDS}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"lines": [], "max_lines": MAX_LINES, "history_ttl_seconds": HISTORY_TTL_SECONDS}


def _save_state(state: dict) -> None:
    """atomic write — tempfile + rename."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="statusline-", suffix=".json", dir=str(STATE_DIR))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(STATE_PATH))
    except Exception:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise


def _expire_old(state: dict) -> dict:
    """TTL 만료된 completed entries 제거."""
    now = _now()
    kept = []
    for line in state.get("lines", []):
        if line.get("status") == "complete":
            expires_at_str = line.get("expires_at")
            if expires_at_str:
                try:
                    expires_at = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                    if now >= expires_at:
                        continue  # expired, drop
                except Exception:
                    pass
        kept.append(line)
    state["lines"] = kept
    return state


def push_workflow(workflow_id: str, skill_chain: list[str], summary: str | None = None) -> None:
    """신규 workflow 시작 — line 1에 추가, 기존 lines는 push down."""
    state = _expire_old(_load_state())
    n_steps = len(skill_chain)
    if summary is None:
        first = skill_chain[0].split(":", 1)[-1] if skill_chain else "?"
        summary = f"[auto] {first} 시작 (1/{n_steps})"

    new_line = {
        "workflow_id": workflow_id,
        "started_at": _now_iso(),
        "updated_at": _now_iso(),
        "completed_at": None,
        "status": "running",
        "summary": summary,
        "skill_chain": skill_chain,
        "current_step": 1,
        "current_tool": None,
    }

    # active line 중복 워크플로우 ID 제거
    state["lines"] = [l for l in state.get("lines", []) if l.get("workflow_id") != workflow_id]

    # 새 line을 맨 앞에 push
    state["lines"].insert(0, new_line)

    # max_lines 초과 시 가장 오래된 (마지막) 제거
    max_n = state.get("max_lines", MAX_LINES)
    if len(state["lines"]) > max_n:
        state["lines"] = state["lines"][:max_n]

    _save_state(state)


def update_current(workflow_id: str | None = None, *, step: int | None = None, tool: str | None = None, summary: str | None = None) -> None:
    """현재 active workflow의 line 1 갱신.

    workflow_id 미지정 시 가장 최근 running line 갱신.
    """
    state = _expire_old(_load_state())
    target = None
    for line in state.get("lines", []):
        if workflow_id and line.get("workflow_id") != workflow_id:
            continue
        if line.get("status") != "running":
            continue
        target = line
        break
    if target is None:
        return  # 활성 workflow 없음 — silent

    target["updated_at"] = _now_iso()
    if step is not None:
        target["current_step"] = step
    if tool is not None:
        target["current_tool"] = tool

    if summary is None:
        chain = target.get("skill_chain", [])
        n = len(chain)
        cur = target.get("current_step", 1)
        skill_name = chain[min(cur - 1, n - 1)].split(":", 1)[-1] if chain else "?"
        tool_str = f" ⚙ {target['current_tool']}" if target.get("current_tool") else ""
        target["summary"] = f"[auto] {skill_name} 진행 중 ({cur}/{n}){tool_str}"
    else:
        target["summary"] = summary

    _save_state(state)


def complete_workflow(workflow_id: str | None = None, *, success: bool = True, elapsed_ms: int | None = None) -> None:
    """workflow 완료 — status: complete, expires_at 설정.

    workflow_id 지정 → 해당 워크플로우만
    workflow_id 미지정 → **모든** running 워크플로우 일괄 complete (Stop hook용 cleanup)
    """
    state = _expire_old(_load_state())
    targets: list[dict] = []
    for line in state.get("lines", []):
        if line.get("status") != "running":
            continue
        if workflow_id and line.get("workflow_id") != workflow_id:
            continue
        targets.append(line)
        if workflow_id:
            break  # 특정 ID면 첫 매치만

    if not targets:
        return

    now = _now()
    ttl = state.get("history_ttl_seconds", HISTORY_TTL_SECONDS)

    for target in targets:
        target["completed_at"] = now.isoformat()
        target["status"] = "complete" if success else "failed"
        target["expires_at"] = (now + timedelta(seconds=ttl)).isoformat()

        line_elapsed_ms = elapsed_ms
        if line_elapsed_ms is None:
            try:
                started_at = datetime.fromisoformat(target.get("started_at", "").replace("Z", "+00:00"))
                line_elapsed_ms = int((now - started_at).total_seconds() * 1000)
            except Exception:
                line_elapsed_ms = 0
        target["elapsed_ms"] = line_elapsed_ms

        chain = target.get("skill_chain", [])
        skill_name = chain[0].split(":", 1)[-1] if chain else "?"
        elapsed_s = line_elapsed_ms / 1000
        icon = "✓" if success else "✗"
        target["summary"] = f"[auto] {skill_name} {'완료' if success else '실패'} ({elapsed_s:.1f}s) {icon}"

    _save_state(state)


def get_lines_for_render() -> list[dict]:
    """renderer가 호출 — TTL 만료 적용 후 line 리스트 반환."""
    state = _expire_old(_load_state())
    _save_state(state)
    return state.get("lines", [])
