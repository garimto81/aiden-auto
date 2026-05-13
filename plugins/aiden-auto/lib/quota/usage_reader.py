"""usage_reader.py — .usage-cache.json 파서 (v28.2 Section 4 statusline)

Reads `~/.claude/.usage-cache.json` (refreshed by `hud/usage-refresh.mjs` on SessionStart).
Returns dataclass with percentages + reset times + staleness flag.

Schema version: 1.0 (aiden-auto v28.2)
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = "1.0"

CACHE_PATH = Path.home() / ".claude" / ".usage-cache.json"
STALENESS_THRESHOLD_SECONDS = 600  # 10 minutes


@dataclass
class UsageSnapshot:
    schema_version: str
    five_h_pct: int
    weekly_pct: int
    five_h_resets_at: str  # ISO 8601
    weekly_resets_at: str
    staleness_seconds: int
    is_stale: bool
    source_mtime: str

    def quota_band(self) -> str:
        """Return one of: OK / WATCH / DOWNGRADE / DEFER / STALE.

        Used by statusline_compose.py and quota_pretool_gate.py.
        """
        if self.is_stale:
            return "STALE"
        peak = max(self.five_h_pct, self.weekly_pct)
        if peak >= 95:
            return "DEFER"
        if peak >= 85:
            return "DOWNGRADE"
        if peak >= 70:
            return "WATCH"
        return "OK"


def read_usage_cache(path: Path = CACHE_PATH) -> UsageSnapshot | None:
    """Read .usage-cache.json. Returns None if not present or unreadable.

    Never raises — statusline must keep working even on cache miss.
    """
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    now = datetime.now(timezone.utc)
    age = int((now - mtime).total_seconds())

    return UsageSnapshot(
        schema_version=SCHEMA_VERSION,
        five_h_pct=int(raw.get("fiveHourPercent", 0)),
        weekly_pct=int(raw.get("weeklyPercent", 0)),
        five_h_resets_at=str(raw.get("fiveHourResetsAt", "")),
        weekly_resets_at=str(raw.get("weeklyResetsAt", "")),
        staleness_seconds=age,
        is_stale=(age > STALENESS_THRESHOLD_SECONDS),
        source_mtime=mtime.isoformat(),
    )


def format_reset_short(iso_str: str) -> str:
    """ISO 8601 → HH:MMZ for statusline display."""
    if not iso_str:
        return "??:??Z"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%H:%MZ")
    except ValueError:
        return "??:??Z"


if __name__ == "__main__":
    # CLI smoke test
    snap = read_usage_cache()
    if snap is None:
        print("usage_reader: cache not found at", CACHE_PATH)
    else:
        print(f"5h={snap.five_h_pct}% wk={snap.weekly_pct}% band={snap.quota_band()} stale={snap.is_stale}")
