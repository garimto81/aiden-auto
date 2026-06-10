#!/usr/bin/env python
"""State-file based Circuit Breaker hook.

States: CLOSED (normal) -> OPEN (blocked) -> HALF_OPEN (testing)
- CLOSED: failures >= 3 -> OPEN
- OPEN: after 30s -> HALF_OPEN
- HALF_OPEN: success -> CLOSED / failure -> OPEN
Exponential backoff: 1s, 2s, 4s recorded in state file.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path


def _resolve_state_file() -> str:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return str(Path(plugin_root) / "state" / "circuit-breaker.json")
    # Fallback: __file__ 기반 — hooks/ 의 부모 = plugin root
    return str(Path(__file__).resolve().parent.parent / "state" / "circuit-breaker.json")


STATE_FILE = _resolve_state_file()
FAILURE_THRESHOLD = 3
OPEN_TIMEOUT = 30  # seconds
_SIMPLE_KEYS = ("state", "failures", "last_failure", "backoff")
_DEFAULT_STATE = {"state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1}

# load_state 가 발견한 원본 컨테이너 + 스키마 모드를 save_state 가 재사용.
#   "flat"   : 파일이 곧 단순 상태 (v1.0 스키마)
#   "nested" : 단순 상태가 raw["_legacy"] 안에 있음 (rule 17 다중 카운터 스키마)
_RAW = None
_MODE = "flat"


def load_state():
    """단순 v1.0 스키마와 rule 17 다중 카운터 스키마(단순 상태가 '_legacy' 안)
    둘 다 허용. 과거엔 top-level cb["state"] 직접 접근이 rule 17 파일에서
    KeyError 로 죽었음 → 매 Bash/Edit/Write/Agent 호출마다 hook crash."""
    global _RAW, _MODE
    _RAW, _MODE = None, "flat"
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                if "state" in raw:  # flat v1.0 스키마
                    _RAW, _MODE = raw, "flat"
                    return {**_DEFAULT_STATE, **raw}
                # rule 17 다중 카운터 스키마 — 단순 상태는 _legacy 에
                _RAW, _MODE = raw, "nested"
                leg = raw.get("_legacy")
                if isinstance(leg, dict):
                    return {**_DEFAULT_STATE, **leg}
                return dict(_DEFAULT_STATE)
        except (json.JSONDecodeError, OSError):
            pass
    return dict(_DEFAULT_STATE)


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    # rule 17 형식으로 읽었으면 단순 상태를 다시 _legacy 안에 써서
    # 다른 카운터(architect_reject/pdca_iterator 등) 손실 방지.
    if _MODE == "nested" and isinstance(_RAW, dict):
        leg = _RAW.get("_legacy")
        if not isinstance(leg, dict):
            leg = {}
        for k in _SIMPLE_KEYS:
            leg[k] = state.get(k)
        leg.setdefault("_note", "단순 failure threshold 호환성 보존 (rule 17 v1.0 형식)")
        _RAW["_legacy"] = leg
        out = _RAW
    else:
        out = state
    # Unique tmp per (pid, thread) — Windows shared-tmp PermissionError 방지
    tmp_path = f"{STATE_FILE}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False)
    # Windows os.replace 는 target 잠금 시 PermissionError — 짧은 retry 로 흡수
    for attempt in range(5):
        try:
            os.replace(tmp_path, STATE_FILE)
            return
        except PermissionError:
            if attempt == 4:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
            time.sleep(0.005 * (attempt + 1))


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        return

    cb = load_state()
    now = time.time()
    error = data.get("error", "") or ""

    # Troubleshooting guide (v28.3 FR-005)
    _TROUBLESHOOT = (
        " — 해결책: 1) /reset-breaker 로 즉시 리셋 / 2) 24h 후 자동 HALF_OPEN / "
        "3) 근본 원인 미해결 시 실패 로그 확인. 상세: commands/reset-breaker.md"
    )

    # State transitions (모든 접근은 .get 으로 방어 — KeyError 영구 차단)
    if cb.get("state") == "OPEN":
        if now - cb.get("last_failure", 0) >= OPEN_TIMEOUT:
            cb["state"] = "HALF_OPEN"
        else:
            save_state(cb)
            json.dump(
                {"decision": "block", "reason": f"Circuit breaker OPEN (backoff {cb.get('backoff', 1)}s)" + _TROUBLESHOOT},
                sys.stdout,
            )
            return

    if error:
        cb["failures"] = cb.get("failures", 0) + 1
        cb["last_failure"] = now
        if cb.get("state") == "HALF_OPEN" or cb["failures"] >= FAILURE_THRESHOLD:
            cb["state"] = "OPEN"
            cb["backoff"] = min(cb.get("backoff", 1) * 2, 4)
            save_state(cb)
            json.dump(
                {"decision": "block", "reason": f"Circuit breaker OPEN after {cb['failures']} failures" + _TROUBLESHOOT},
                sys.stdout,
            )
            return
    else:
        if cb.get("state") == "HALF_OPEN":
            cb["state"] = "CLOSED"
            cb["failures"] = 0
            cb["backoff"] = 1

    save_state(cb)


if __name__ == "__main__":
    main()
