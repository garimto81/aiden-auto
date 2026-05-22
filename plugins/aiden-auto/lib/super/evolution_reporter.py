"""Evolution Reporter: daily/weekly/monthly 마크다운 보고서 생성.

NDJSON 로그(`audit/super-evolution.ndjson`)를 읽어 기간별 요약 markdown을 생성.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


@dataclass
class ReportSummary:
    period_label: str
    period_start: str
    period_end: str
    total_events: int
    by_event: Counter
    by_category: Counter
    by_tier: Counter


class EvolutionReporter:
    def __init__(self, plugin_root: Path) -> None:
        self.plugin_root = plugin_root
        self.log_path = plugin_root / "audit" / "super-evolution.ndjson"

    def daily_report(self, on_date: date | None = None) -> str:
        on_date = on_date or date.today()
        start = datetime.combine(on_date, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        return self._render(self._summarize("daily", start, end))

    def weekly_report(self, week_end: date | None = None) -> str:
        week_end = week_end or date.today()
        start = datetime.combine(week_end - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(week_end, datetime.max.time(), tzinfo=timezone.utc)
        return self._render(self._summarize("weekly", start, end))

    def monthly_report(self, ref_date: date | None = None) -> str:
        ref_date = ref_date or date.today()
        start = datetime.combine(ref_date.replace(day=1), datetime.min.time(), tzinfo=timezone.utc)
        end = datetime.combine(ref_date, datetime.max.time(), tzinfo=timezone.utc)
        return self._render(self._summarize("monthly", start, end))

    # ---- internals ----

    def _summarize(self, label: str, start: datetime, end: datetime) -> ReportSummary:
        by_event: Counter = Counter()
        by_category: Counter = Counter()
        by_tier: Counter = Counter()
        total = 0
        if self.log_path.exists():
            with self.log_path.open("r", encoding="utf-8") as f:
                for line in f:
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    ts_str = ev.get("ts", "")
                    try:
                        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    except Exception:
                        continue
                    if not (start <= ts <= end):
                        continue
                    total += 1
                    by_event[ev.get("event", "?")] += 1
                    if "category" in ev:
                        by_category[ev["category"]] += 1
                    if "tier" in ev:
                        by_tier[ev["tier"]] += 1

        return ReportSummary(
            period_label=label,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            total_events=total,
            by_event=by_event,
            by_category=by_category,
            by_tier=by_tier,
        )

    def _render(self, s: ReportSummary) -> str:
        lines = [
            f"# Super Evolution Report — {s.period_label}",
            "",
            f"- Period: {s.period_start} → {s.period_end}",
            f"- Total events: {s.total_events}",
            "",
        ]
        if s.total_events == 0:
            lines.append("> 이 기간 evolution 이벤트 없음.")
            return "\n".join(lines)

        lines.append("## Event 분포")
        lines.append("")
        lines.append("| Event | Count |")
        lines.append("|-------|------:|")
        for ev, cnt in s.by_event.most_common():
            lines.append(f"| {ev} | {cnt} |")
        lines.append("")

        if s.by_category:
            lines.append("## 카테고리별")
            lines.append("")
            lines.append("| Category | Count |")
            lines.append("|----------|------:|")
            for cat, cnt in s.by_category.most_common():
                lines.append(f"| {cat} | {cnt} |")
            lines.append("")

        if s.by_tier:
            lines.append("## Tier 분포")
            lines.append("")
            lines.append("| Tier | Count |")
            lines.append("|------|------:|")
            for tier, cnt in s.by_tier.most_common():
                lines.append(f"| {tier} | {cnt} |")

        return "\n".join(lines)
