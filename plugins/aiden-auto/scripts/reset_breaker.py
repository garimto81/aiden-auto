#!/usr/bin/env python3
"""Circuit Breaker 수동 리셋 — /reset-breaker 명령의 본체 (v28.3 FR-005).

state/circuit-breaker.json 을 atomic write 로 다음 값으로 덮어쓴다:
    {"state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1}

이전 상태와 변경 사항을 stdout 으로 출력.

Exit code:
  0 = 성공 (state file 갱신 완료)
  1 = 실패 (디렉토리 권한 / 디스크 가득 등)
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path


DEFAULT_STATE = {"state": "CLOSED", "failures": 0, "last_failure": 0, "backoff": 1}


def _resolve_state_file() -> str:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if plugin_root:
        return str(Path(plugin_root) / "state" / "circuit-breaker.json")
    # Fallback: __file__ 기반 — scripts/ 의 부모 = plugin root
    return str(Path(__file__).resolve().parent.parent / "state" / "circuit-breaker.json")


def load_state(state_file: str) -> dict | None:
    """이전 상태 읽기. 파일 없거나 무효 JSON 이면 None 반환."""
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def atomic_save(state_file: str, state: dict) -> None:
    """unique tmp + os.replace + retry (circuit_breaker.py 와 동일 패턴)."""
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    tmp_path = f"{state_file}.{os.getpid()}.{threading.get_ident()}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(state, f)
    for attempt in range(5):
        try:
            os.replace(tmp_path, state_file)
            return
        except PermissionError:
            if attempt == 4:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
                raise
            time.sleep(0.005 * (attempt + 1))


def main() -> int:
    state_file = _resolve_state_file()
    prev = load_state(state_file)

    try:
        atomic_save(state_file, DEFAULT_STATE)
    except (PermissionError, OSError) as e:
        print(f"[reset-breaker] FAIL — {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    # 결과 출력
    print("=== Circuit Breaker Reset ===")
    print(f"file:   {state_file}")
    if prev is None:
        print("before: <none or invalid>")
    else:
        print(f"before: state={prev.get('state','?')} failures={prev.get('failures',0)} backoff={prev.get('backoff',1)}s")
    print(f"after:  state=CLOSED failures=0 backoff=1s")
    print("=============================")
    return 0


if __name__ == "__main__":
    sys.exit(main())
