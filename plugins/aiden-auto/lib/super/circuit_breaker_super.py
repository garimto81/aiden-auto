"""Circuit Breaker for super-evolve.

임계:
  - 하루 동일 카테고리 evolve 시도 5회 초과 → halt
  - 누적 LOW 자동 적용 ≥ 100건 → "consolidation 필요" 알림
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path


class CircuitBreakerSuper:
    DAILY_PER_CATEGORY_LIMIT = 5
    CONSOLIDATION_THRESHOLD = 100

    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root
        self.state_path = plugin_root / "audit" / "circuit-breaker-super.json"

    def can_evolve(self, category: str) -> tuple[bool, str]:
        """(허용 여부, 사유). 허용 시 사유는 빈 문자열."""
        state = self._read_state()
        today = date.today().isoformat()
        daily = state.get("daily", {}).get(today, {}).get(category, 0)
        if daily >= self.DAILY_PER_CATEGORY_LIMIT:
            return False, f"daily limit reached ({daily}/{self.DAILY_PER_CATEGORY_LIMIT})"
        return True, ""

    def record_attempt(self, category: str, *, applied: bool, tier: str) -> None:
        state = self._read_state()
        today = date.today().isoformat()
        daily = state.setdefault("daily", {})
        per_day = daily.setdefault(today, {})
        per_day[category] = per_day.get(category, 0) + 1

        if applied and tier == "LOW":
            state["cumulative_low_applied"] = state.get("cumulative_low_applied", 0) + 1

        state["last_updated"] = datetime.now(timezone.utc).isoformat()
        self._prune_old_days(state)
        self._write_state(state)

    def needs_consolidation(self) -> bool:
        state = self._read_state()
        return state.get("cumulative_low_applied", 0) >= self.CONSOLIDATION_THRESHOLD

    def reset_consolidation(self) -> None:
        state = self._read_state()
        state["cumulative_low_applied"] = 0
        self._write_state(state)

    # ---- internals ----

    def _read_state(self) -> dict:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_state(self, state: dict) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _prune_old_days(self, state: dict, keep_days: int = 7) -> None:
        """7일 이상 지난 daily 통계 삭제."""
        from datetime import timedelta
        if "daily" not in state:
            return
        cutoff = (date.today() - timedelta(days=keep_days)).isoformat()
        state["daily"] = {d: v for d, v in state["daily"].items() if d >= cutoff}
